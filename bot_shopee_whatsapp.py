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
print("VERSAO SHOPEE V15 - PREMIUM & ANTI-REPETIÇÃO")

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
ULTIMOS_PRODUTOS_ENVIADOS = [] # Armazena links
ULTIMOS_TITULOS_ENVIADOS = []  # Armazena nomes normalizados

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# NICHOS E PALAVRAS-CHAVE (MELHORADOS)
# ==========================================
NICHOS_CICLO = ["Casa e Eletro", "Moda Feminina", "Moda Masculina", "Maternidade", "Motocicleta"]

KEYWORDS = {
    "Casa e Eletro": [
        "Smart TV 50", "iPhone 13", "iPhone 14", "Samsung Galaxy S23", "Xiaomi Redmi", 
        "Air Fryer Philips", "Geladeira Frost Free", "Ar Condicionado Inverter",
        "Notebook Gamer", "Playstation 5", "Nintendo Switch", "Caixa JBL Original",
        "Robô Aspirador", "Máquina de Lavar", "Micro-ondas Espelhado"
    ],
    "Moda Feminina": [
        "Vestido Midi Elegante", "Conjunto Canelado", "Tênis Feminino Casual", 
        "Bolsa de Couro Feminina", "Sandália Salto Bloco", "Kit Maquiagem Profissional",
        "Relógio Feminino Dourado", "Óculos de Sol Feminino"
    ],
    "Moda Masculina": [
        "Tênis Masculino Esportivo", "Camisa Polo Premium", "Relógio Masculino Luxo", 
        "Mochila Impermeável", "Perfume Importado Masculino", "Camiseta Algodão Egípcio",
        "Sapato Social Couro", "Kit Cueca Box"
    ],
    "Maternidade": [
        "Carrinho de Bebê Reclinável", "Babá Eletrônica com Câmera", "Berço Portátil", 
        "Cadeira de Alimentação", "Kit Enxoval Completo", "Fralda Pampers Atacado",
        "Mochila Maternidade Térmica", "Brinquedo Educativo Fisher Price"
    ],
    "Motocicleta": [
        "Capacete LS2 FF358", "Capacete Norisk", "Escapamento Fortuna CG", 
        "Pneu Pirelli Moto", "Kit Relação DID", "Intercomunicador Moto",
        "Luva de Couro Moto", "Jaqueta de Proteção Moto", "Baú Bauleto Givi",
        "Suporte Celular Alumínio Moto", "Farol LED Moto Forte"
    ]
}

PALAVRAS_BLOQUEIO = ["teste", "amostra", "não compre", "dummy", "fake", "usado", "defeito"]

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

def eh_repetido(titulo, link):
    if link in ULTIMOS_PRODUTOS_ENVIADOS:
        return True
    
    t_novo = normalizar_texto(titulo)
    for t_antigo in ULTIMOS_TITULOS_ENVIADOS:
        # Se a similaridade for maior que 65%, consideramos repetido (evita variações do mesmo item)
        if SequenceMatcher(None, t_novo, t_antigo).ratio() > 0.65:
            return True
    return False

def registrar_envio(titulo, link):
    ULTIMOS_PRODUTOS_ENVIADOS.append(link)
    ULTIMOS_TITULOS_ENVIADOS.append(normalizar_texto(titulo))
    if len(ULTIMOS_PRODUTOS_ENVIADOS) > 200:
        ULTIMOS_PRODUTOS_ENVIADOS.pop(0)
    if len(ULTIMOS_TITULOS_ENVIADOS) > 200:
        ULTIMOS_TITULOS_ENVIADOS.pop(0)

# ==========================================
# LÓGICA DE CÓPIA E MENSAGENS
# ==========================================

def gerar_copy_base(nome, preco, vendas, avaliacao, comissao, link, for_whatsapp=False):
    aberturas = [
        "🤯 Sério… olha esse achado!",
        "🚨 Isso aqui não aparece toda hora!",
        "👀 Achei agora e vim correndo postar!",
        "🔥 OPORTUNIDADE QUENTE!",
        "💥 Esse aqui tá com um preço absurdo!",
        "🛑 PARA TUDO e olha esse desconto!",
        "⚠️ Alerta de estoque baixo!",
        "🚀 Esse aqui vai voar rápido!"
    ]
    
    gatilhos = [
        "Preço muito abaixo do mercado",
        "Avaliações excelentes dos compradores",
        "Campeão de vendas na categoria",
        "Custo-benefício imbatível",
        "Qualidade premium garantida",
        "O queridinho do momento"
    ]
    
    chamadas_acao = [
        "⚡ CLIQUE ANTES QUE O PREÇO SUBA!",
        "🔥 ESTOQUE LIMITADO - APROVEITE!",
        "🚀 COMPRE AGORA COM DESCONTO!",
        "🎯 GARANTA O SEU ANTES QUE ACABE!",
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
        productOfferV2(sortType: 2, limit: 50, keyword: "{keyword}", isAMSOffer: true) {{
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
    
    for nicho in NICHOS_CICLO:
        logging.info(f"Processando nicho: {nicho}")
        candidatos_nicho = []
        
        # Tenta buscar com 2 keywords diferentes para garantir variedade
        keywords_selecionadas = random.sample(KEYWORDS[nicho], k=2)
        
        for kw in keywords_selecionadas:
            produtos = buscar_shopee(kw)
            for p in produtos:
                nome = p.get("productName", "")
                link = p.get("offerLink") or p.get("productLink")
                preco = float(p.get("priceMin", 0))
                vendas = int(p.get("sales", 0))
                rating = float(p.get("ratingStar", 0))
                comissao = float(p.get("commissionRate", 0))

                # Validações
                if not nome or not link: continue
                if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO): continue
                if preco < PRECO_MIN or preco > PRECO_MAX: continue
                if vendas < VENDAS_MIN: continue
                if rating < RATING_MIN: continue
                if comissao < COMISSAO_MIN: continue
                if eh_repetido(nome, link): continue
                
                # Pontuação de "Calor" da oferta
                score = (vendas / 100) + (rating * 5) + (comissao * 100)
                if any(q in nome.lower() for q in ["tv", "iphone", "samsung", "moto", "capacete", "geladeira"]):
                    score += 20 # Boost para produtos quentes
                
                p["score"] = score
                candidatos_nicho.append(p)
        
        # Ordena por score e pega os 2 melhores do nicho
        candidatos_nicho.sort(key=lambda x: x["score"], reverse=True)
        
        contagem = 0
        for cand in candidatos_nicho:
            if contagem >= 2: break
            
            # Verifica novamente se não é similar aos que já escolhemos neste ciclo
            if not any(SequenceMatcher(None, normalizar_texto(cand["productName"]), normalizar_texto(f["productName"])).ratio() > 0.60 for f in ofertas_finais):
                ofertas_finais.append(cand)
                contagem += 1
                
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
        text="🚨 <b>AS MELHORES OFERTAS DE AGORA!</b>\n<i>Preparem o dedo, os estoques são limitados!</i>",
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
            
            # Espera entre produtos para evitar spam
            await asyncio.sleep(45)
            
        except Exception as e:
            logging.error(f"Erro ao enviar produto: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V15 Inicializado com Sucesso!")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("ERRO: TELEGRAM_TOKEN não configurado!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        app.run_polling()


        


