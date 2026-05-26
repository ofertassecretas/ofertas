import asyncio
import requests
import logging
import random
import hashlib
import time
import json
import os
import html
import re
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

# ==========================================
# CONFIGURAÇÕES BÁSICAS
# ==========================================
print("VERSAO SHOPEE V16 - VARIEDADE TOTAL & ANTI-REPETIÇÃO")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Intervalo entre ciclos (em segundos) - 5400s = 1h30
CHECK_INTERVAL = 5400

# Filtros de Qualidade
PRECO_MIN = 25.0
PRECO_MAX = 15000.0
COMISSAO_MIN = 0.07
VENDAS_MIN = 50
RATING_MIN = 4.5

# Memória do Bot (Anti-Repetição)
ULTIMOS_PRODUTOS_ENVIADOS = [] 
ULTIMOS_TITULOS_ENVIADOS = []  

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# NICHOS E SUBCATEGORIAS (PARA GARANTIR VARIEDADE)
# ==========================================
# Agora os nichos são divididos em subcategorias. 
# O bot vai escolher 2 subcategorias DIFERENTES por ciclo para cada nicho.

KEYWORDS_ESTRUTURADAS = {
    "Casa e Eletro": {
        "TV": ["Smart TV 50 polegadas", "TV 4K Samsung", "TV LG ThinQ"],
        "Celulares": ["iPhone 14", "iPhone 13", "Samsung S23 Ultra", "Xiaomi Redmi Note"],
        "Eletrodomesticos": ["Geladeira Frost Free", "Fogão 4 bocas", "Máquina de Lavar", "Micro-ondas"],
        "Cozinha": ["Air Fryer Philips", "Batedeira Planetária", "Cafeteira Dolce Gusto"],
        "Tecnologia": ["Notebook Gamer", "Playstation 5", "Caixa JBL Original", "Alexa Echo Dot"]
    },
    "Moda Feminina": {
        "Roupas": ["Vestido Midi", "Conjunto Canelado", "Calça Pantalona", "Blusa Feminina"],
        "Calcados": ["Tênis Feminino Casual", "Sandália Salto Bloco", "Rasteirinha"],
        "Acessorios": ["Bolsa de Couro Feminina", "Relógio Feminino Dourado", "Óculos de Sol"]
    },
    "Moda Masculina": {
        "Roupas": ["Camisa Polo Premium", "Camiseta Algodão Egípcio", "Calça Jeans Masculina"],
        "Calcados": ["Tênis Masculino Esportivo", "Sapato Social Couro", "Sapatênis"],
        "Acessorios": ["Relógio Masculino Luxo", "Mochila Impermeável", "Carteira de Couro"]
    },
    "Maternidade": {
        "Moveis": ["Carrinho de Bebê Reclinável", "Berço Portátil", "Cadeira de Alimentação"],
        "Seguranca": ["Babá Eletrônica com Câmera", "Grade de Proteção"],
        "Higiene": ["Fralda Pampers Atacado", "Kit Enxoval Completo", "Mochila Maternidade"]
    },
    "Motocicleta": {
        "Seguranca": ["Capacete LS2 FF358", "Capacete Norisk", "Capa de Chuva Moto"],
        "Pecas": ["Pneu Pirelli Moto", "Kit Relação DID", "Amortecedor Pro Link", "Escapamento Fortuna"],
        "Acessorios": ["Intercomunicador Moto", "Baú Givi", "Suporte Celular Alumínio", "Guidão Esportivo"]
    }
}

PALAVRAS_BLOQUEIO = ["teste", "amostra", "não compre", "dummy", "fake", "usado", "defeito", "viseira"] # Adicionei viseira no bloqueio temporário se estiver vindo muito

# ==========================================
# UTILITÁRIOS
# ==========================================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(6, 0) <= agora <= dt_time(23, 59)

def normalizar_texto(txt):
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt

def eh_repetido(titulo, link, lista_ciclo_atual):
    # 1. Verifica se o link já foi enviado recentemente
    if link in ULTIMOS_PRODUTOS_ENVIADOS:
        return True
    
    t_novo = normalizar_texto(titulo)
    
    # 2. Verifica similaridade com o histórico
    for t_antigo in ULTIMOS_TITULOS_ENVIADOS:
        if SequenceMatcher(None, t_novo, t_antigo).ratio() > 0.60:
            return True
            
    # 3. Verifica similaridade com o que já foi escolhido NESTE ciclo (evita 2 iguais no mesmo envio)
    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        # Se compartilhar palavras muito comuns como "viseira", "capinha", "película" no mesmo ciclo, bloqueia
        palavras_comuns = ["viseira", "capinha", "película", "filtro", "adesivo", "suporte"]
        for pc in palavras_comuns:
            if pc in t_novo and pc in t_atual:
                return True
        
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.45: # Threshold mais baixo para o mesmo ciclo
            return True
            
    return False

def registrar_envio(titulo, link):
    ULTIMOS_PRODUTOS_ENVIADOS.append(link)
    ULTIMOS_TITULOS_ENVIADOS.append(normalizar_texto(titulo))
    if len(ULTIMOS_PRODUTOS_ENVIADOS) > 300:
        ULTIMOS_PRODUTOS_ENVIADOS.pop(0)
    if len(ULTIMOS_TITULOS_ENVIADOS) > 300:
        ULTIMOS_TITULOS_ENVIADOS.pop(0)

# ==========================================
# LÓGICA DE CÓPIA E MENSAGENS
# ==========================================

def gerar_copy_base(nome, preco, vendas, avaliacao, comissao, link, for_whatsapp=False):
    aberturas = [
        "🤯 Sério… olha esse achado!", "🚨 Isso aqui não aparece toda hora!", 
        "👀 Achei agora e vim correndo postar!", "🔥 OPORTUNIDADE QUENTE!",
        "💥 Esse aqui tá com um preço absurdo!", "🛑 PARA TUDO e olha esse desconto!",
        "⚠️ Alerta de estoque baixo!", "🚀 Esse aqui vai voar rápido!"
    ]
    
    gatilhos = [
        "Preço muito abaixo do mercado", "Avaliações excelentes dos compradores",
        "Campeão de vendas na categoria", "Custo-benefício imbatível",
        "Qualidade premium garantida", "O queridinho do momento"
    ]
    
    chamadas_acao = [
        "⚡ CLIQUE ANTES QUE O PREÇO SUBA!", "🔥 ESTOQUE LIMITADO - APROVEITE!",
        "🚀 COMPRE AGORA COM DESCONTO!", "🎯 GARANTA O SEU ANTES QUE ACABE!",
        "💰 ECONOMIA REAL SÓ HOJE!"
    ]

    abertura = random.choice(aberturas)
    gatilho = random.choice(gatilhos)
    chamada = random.choice(chamadas_acao)

    if for_whatsapp:
        return f"""{abertura}

*🔥 {nome}*

📌 {gatilho}

{chamada}

💰 *R$ {preco}*
⭐ *{avaliacao}* | 🛒 *{vendas} vendas*

⚠️ *Pode subir de preço a qualquer momento*

🛒 *COMPRAR AGORA:*
{link}

━━━━━━━━━━━━━━━
📢 *Quer mais ofertas assim?*
{LINK_GRUPO_OFERTAS}"""

    # Para o Telegram (HTML)
    zap_msg = gerar_copy_base(nome, preco, vendas, avaliacao, comissao, link, for_whatsapp=True)
    zap_link = f"https://wa.me/?text={quote(zap_msg)}"

    return f"""{abertura}

🔥 <b>{nome}</b>

📌 {gatilho}

{chamada}

💰 <b>R$ {preco}</b>
⭐ <b>{avaliacao} | {vendas} vendas</b>
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>

<a href="{LINK_GRUPO_OFERTAS}">📲 Entrar no grupo de ofertas</a>

<a href="{zap_link}">📲 Compartilhar no WhatsApp</a>

━━━━━━━━━━━━━━━
📢 <b>Ofertas Secretas</b>"""

# ==========================================
# INTEGRAÇÃO SHOPEE
# ==========================================

def buscar_shopee(keyword):
    timestamp = int(time.time())
    query_body = f'''
    query {{
        productOfferV2(sortType: 2, limit: 40, keyword: "{keyword}", isAMSOffer: true) {{
            nodes {{
                productName
                priceMin
                commissionRate
                sales
                ratingStar
                productLink
                offerLink
                imageUrl
            }}
        }}
    }}
    '''
    payload = json.dumps({"query": query_body})
    base_str = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base_str.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        res = r.json()
        return res.get("data", {}).get("productOfferV2", {}).get("nodes", [])
    except Exception as e:
        logging.error(f"Erro na busca Shopee ({keyword}): {e}")
        return []

def aplicar_afiliado(link):
    try:
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        query["af_siteid"] = AFILIADO_ID
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    except:
        return link

def get_melhores_ofertas():
    ofertas_finais = []
    
    # Embaralha os nichos para não mandar sempre na mesma ordem
    nichos = list(KEYWORDS_ESTRUTURADAS.keys())
    random.shuffle(nichos)
    
    for nicho in nichos:
        logging.info(f"Processando nicho: {nicho}")
        
        # Pega as subcategorias deste nicho
        subs = list(KEYWORDS_ESTRUTURADAS[nicho].keys())
        # Escolhe 2 subcategorias DIFERENTES
        subs_escolhidas = random.sample(subs, k=2)
        
        for sub in subs_escolhidas:
            # Pega uma keyword aleatória dentro da subcategoria
            kw = random.choice(KEYWORDS_ESTRUTURADAS[nicho][sub])
            produtos = buscar_shopee(kw)
            
            candidatos_sub = []
            for p in produtos:
                nome = p.get("productName", "")
                link = p.get("offerLink") or p.get("productLink")
                preco = float(p.get("priceMin", 0))
                vendas = int(p.get("sales", 0))
                rating = float(p.get("ratingStar", 0))
                comissao = float(p.get("commissionRate", 0))

                if not nome or not link: continue
                if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO): continue
                if preco < PRECO_MIN or preco > PRECO_MAX: continue
                if vendas < VENDAS_MIN: continue
                if rating < RATING_MIN: continue
                if comissao < COMISSAO_MIN: continue
                
                # Validação de repetição (histórico + ciclo atual)
                if eh_repetido(nome, link, ofertas_finais): continue
                
                # Score de qualidade
                score = (vendas / 50) + (rating * 10) + (comissao * 100)
                # Boost para palavras-chave de desejo
                palavras_quentes = ["tv", "iphone", "geladeira", "fogão", "moto", "ls2", "jbl", "ps5"]
                if any(pq in nome.lower() for pq in palavras_quentes):
                    score += 30
                
                p["score"] = score
                candidatos_sub.append(p)
            
            # Se achou algo na subcategoria, pega o melhor
            if candidatos_sub:
                candidatos_sub.sort(key=lambda x: x["score"], reverse=True)
                ofertas_finais.append(candidatos_sub[0])
                logging.info(f"Selecionado: {candidatos_sub[0]['productName']} (Sub: {sub})")
                
    return ofertas_finais

# ==========================================
# EXECUÇÃO DO BOT
# ==========================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    if not dentro_do_horario():
        logging.info("Fora do horário de funcionamento.")
        return

    logging.info("Iniciando ciclo de envio...")
    ofertas = get_melhores_ofertas()
    
    if not ofertas:
        logging.warning("Nenhuma oferta qualificada encontrada neste ciclo.")
        return

    # Mensagem de introdução do ciclo
    await context.bot.send_message(
        chat_id=CHAT_ID_DESTINO,
        text="🚨 <b>AS MELHORES OFERTAS DE AGORA!</b>\n<i>Variedade e preço baixo garantidos!</i>",
        parse_mode="HTML"
    )
    await asyncio.sleep(3)

    for item in ofertas:
        try:
            nome = html.escape(item["productName"])
            link_original = item.get("offerLink") or item.get("productLink")
            link_afiliado = aplicar_afiliado(link_original)
            preco = f"{float(item['priceMin']):.2f}".replace(".", ",")
            vendas = f"{int(item['sales']):,}".replace(",", ".")
            rating = item.get("ratingStar", 5.0)
            comissao = round(float(item.get("commissionRate", 0)) * 100, 1)
            img = item.get("imageUrl")

            msg = gerar_copy_base(nome, preco, vendas, rating, comissao, link_afiliado)
            
            await context.bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=img,
                caption=msg,
                parse_mode="HTML"
            )
            
            # Registrar para evitar repetição futura
            registrar_envio(nome, link_original)
            
            # Espera entre produtos para evitar spam e respeitar limites do Telegram
            await asyncio.sleep(45)
            
        except Exception as e:
            logging.error(f"Erro ao enviar produto: {e}")

async def post_init(app):
    # Executa a primeira vez após 10 segundos, depois a cada CHECK_INTERVAL
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V16 Inicializado com Sucesso!")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("ERRO: TELEGRAM_TOKEN não configurado!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        app.run_polling()


        


