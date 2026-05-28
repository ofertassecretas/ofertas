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
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

# ==========================================
# CONFIGURAÇÕES BÁSICAS
# ==========================================
print("VERSAO SHOPEE V18 - ESTABILIDADE & VARIEDADE")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Caminho para o arquivo de memória (Salva mesmo se o bot reiniciar)
HISTORICO_FILE = "historico_envios.json"

# Intervalo entre ciclos (em segundos) - 5400s = 1h30
CHECK_INTERVAL = 5400

# Filtros de Qualidade (Ajustados para garantir que o bot encontre produtos)
PRECO_MIN = 25.0 
PRECO_MAX = 15000.0
COMISSAO_MIN = 0.07 # Reduzi um pouco para aumentar a chance de encontrar produtos quentes
VENDAS_MIN = 50     # Reduzi de 100 para 50 para dar mais margem ao bot
RATING_MIN = 4.5    # Reduzi de 4.6 para 4.5 para ser mais flexível

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# NICHOS E SUBCATEGORIAS (TURBINADOS)
# ==========================================

KEYWORDS_ESTRUTURADAS = {
    "Casa e Eletro": {
        "TV": ["Smart TV 50", "TV Samsung", "TV LG", "Monitor Gamer"],
        "Celulares": ["iPhone 14", "Samsung S23", "Xiaomi Redmi", "iPhone 13"],
        "Eletrodomesticos": ["Geladeira", "Fogão", "Máquina Lavar", "Ar Condicionado"],
        "Cozinha": ["Air Fryer", "Cafeteira", "Micro-ondas", "Liquidificador"],
        "Tecnologia": ["Notebook", "Playstation 5", "JBL", "Tablet"]
    },
    "Moda Feminina": {
        "Roupas": ["Vestido", "Conjunto Feminino", "Calça Jeans Feminina", "Blusa"],
        "Calcados": ["Tênis Feminino", "Bota Feminina", "Sandália"],
        "Acessorios": ["Bolsa Feminina", "Relógio Feminino", "Maquiagem"]
    },
    "Moda Masculina": {
        "Roupas": ["Camisa Masculina", "Calça Masculina", "Cueca Box"],
        "Calcados": ["Tênis Masculino", "Sapato Masculino", "Bota Masculina"],
        "Acessorios": ["Relógio Masculino", "Mochila Masculina", "Perfume Masculino"]
    },
    "Maternidade": {
        "Moveis": ["Carrinho Bebê", "Berço", "Cadeira Alimentação"],
        "Seguranca": ["Babá Eletrônica", "Câmera Wi-Fi"],
        "Utilidades": ["Fralda", "Kit Enxoval", "Mochila Maternidade"]
    },
    "Motocicleta": {
        "Capacetes": ["Capacete LS2", "Capacete Norisk", "Capacete MT", "Capacete Pro Tork"],
        "Pecas_Pesadas": ["Kit Relação", "Pneu Moto", "Amortecedor Moto"],
        "Performance": ["Escapamento Moto", "Vela Iridium", "Filtro Ar Moto"],
        "Acessorios_Top": ["Intercomunicador", "Baú Moto", "Suporte Celular Moto", "Luva Moto"]
    }
}

PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "não compre", "dummy", "adesivo", "película", 
    "case", "filtro de papel", "brinde", "usado", "defeito"
]

# ==========================================
# GESTÃO DE MEMÓRIA PERSISTENTE
# ==========================================

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Erro ao carregar histórico: {e}")
            return {}
    return {}

def salvar_historico(historico):
    try:
        with open(HISTORICO_FILE, 'w') as f:
            json.dump(historico, f, indent=4)
    except Exception as e:
        logging.error(f"Erro ao salvar histórico: {e}")

def limpar_historico_antigo():
    historico = carregar_historico()
    agora = datetime.now()
    novo_historico = {}
    
    for link, data_str in historico.items():
        try:
            data_envio = datetime.fromisoformat(data_str)
            if agora - data_envio < timedelta(days=10):
                novo_historico[link] = data_str
        except Exception as e:
            logging.warning(f"Erro ao processar item no histórico: {link} - {e}")
            continue
            
    salvar_historico(novo_historico)
    return novo_historico

def eh_repetido_persistente(titulo, link, historico, lista_ciclo_atual):
    if link in historico:
        logging.info(f"Produto '{titulo}' bloqueado por estar no histórico persistente.")
        return True
    
    t_novo = normalizar_texto(titulo)
    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.45:
            logging.info(f"Produto '{titulo}' bloqueado por similaridade com '{p_atual.get('productName', '')}' no ciclo atual.")
            return True
    return False

# ==========================================
# UTILITÁRIOS
# ==========================================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    # Horário ajustado conforme solicitado: 05:30 às 21:00
    return dt_time(5, 30) <= agora <= dt_time(21, 0)

def normalizar_texto(txt):
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt

# ==========================================
# LÓGICA DE MENSAGENS
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
    except Exception as e:
        logging.error(f"Erro ao aplicar ID de afiliado ao link {link}: {e}")
        return link

def get_melhores_ofertas():
    historico = limpar_historico_antigo()
    ofertas_finais = []
    
    nichos = list(KEYWORDS_ESTRUTURADAS.keys())
    random.shuffle(nichos)
    
    for nicho in nichos:
        logging.info(f"Processando nicho: {nicho}")
        subs = list(KEYWORDS_ESTRUTURADAS[nicho].keys())
        # Garante que não vai tentar pegar mais subcategorias do que existem
        subs_escolhidas = random.sample(subs, k=min(2, len(subs)))
        
        for sub in subs_escolhidas:
            kw = random.choice(KEYWORDS_ESTRUTURADAS[nicho][sub])
            logging.info(f"Buscando em '{nicho}' -> Subcategoria '{sub}' com palavra-chave: '{kw}'")
            produtos = buscar_shopee(kw)
            logging.info(f"Encontrados {len(produtos)} produtos brutos para '{kw}'.")
            
            if not produtos:
                logging.warning(f"Nenhum produto encontrado para: {kw}")
                continue

            candidatos_sub = []
            for p in produtos:
                nome = p.get("productName", "")
                link = p.get("offerLink") or p.get("productLink")
                preco = float(p.get("priceMin", 0))
                vendas = int(p.get("sales", 0))
                rating = float(p.get("ratingStar", 0))
                comissao = float(p.get("commissionRate", 0))

                if not nome or not link:
                    logging.debug(f"Produto ignorado (nome ou link ausente): {p}")
                    continue
                if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO):
                    logging.debug(f"Produto '{nome}' bloqueado por palavra-chave de bloqueio.")
                    continue
                if preco < PRECO_MIN or preco > PRECO_MAX:
                    logging.debug(f"Produto '{nome}' bloqueado por preço ({preco}). Min: {PRECO_MIN}, Max: {PRECO_MAX}")
                    continue
                if vendas < VENDAS_MIN:
                    logging.debug(f"Produto '{nome}' bloqueado por vendas ({vendas}). Min: {VENDAS_MIN}")
                    continue
                if rating < RATING_MIN:
                    logging.debug(f"Produto '{nome}' bloqueado por avaliação ({rating}). Min: {RATING_MIN}")
                    continue
                if comissao < COMISSAO_MIN:
                    logging.debug(f"Produto '{nome}' bloqueado por comissão ({comissao}). Min: {COMISSAO_MIN}")
                    continue
                
                if eh_repetido_persistente(nome, link, historico, ofertas_finais):
                    continue
                
                score = (vendas / 50) + (rating * 15) + (comissao * 100)
                palavras_premium = ["iphone", "brastemp", "lg", "samsung", "ls2", "pirelli", "did", "givi", "jbl", "ps5"]
                if any(pp in nome.lower() for pp in palavras_premium):
                    score += 50
                
                p["score"] = score
                candidatos_sub.append(p)
            
            if candidatos_sub:
                candidatos_sub.sort(key=lambda x: x["score"], reverse=True)
                ofertas_finais.append(candidatos_sub[0])
                logging.info(f"Selecionado: {candidatos_sub[0]['productName']} (Sub: {sub}, Score: {candidatos_sub[0]['score']:.2f})")
            else:
                logging.info(f"Nenhum produto da busca '{kw}' passou nos filtros ou foi considerado único.")
                
    logging.info(f"Total de {len(ofertas_finais)} ofertas qualificadas para envio neste ciclo.")
    return ofertas_finais

# ==========================================
# EXECUÇÃO DO BOT
# ==========================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Verificando horário...")
    if not dentro_do_horario():
        logging.info("Fora do horário de envio.")
        return

    logging.info("Iniciando ciclo de busca de ofertas...")
    ofertas = get_melhores_ofertas()
    
    if not ofertas:
        logging.warning("Nenhuma oferta qualificada encontrada neste ciclo.")
        return

    logging.info(f"Enviando {len(ofertas)} ofertas...")
    await context.bot.send_message(
        chat_id=CHAT_ID_DESTINO,
        text="🚨 <b>OFERTAS SELECIONADAS DE HOJE!</b>\n<i>Produtos de alta qualidade e com o melhor preço.</i>",
        parse_mode="HTML"
    )
    await asyncio.sleep(3)

    historico = carregar_historico()
    
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
            
            historico[link_original] = datetime.now().isoformat()
            salvar_historico(historico)
            
            await asyncio.sleep(45)
            
        except Exception as e:
            logging.error(f"Erro no envio do item: {e}")

async def post_init(app):
    # Garante que o histórico é limpo ao iniciar o bot, caso tenha ficado algum lixo
    limpar_historico_antigo()
    # Executa a primeira vez após 10 segundos, depois a cada CHECK_INTERVAL
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V18 Inicializado e Agendado!")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("ERRO: TELEGRAM_TOKEN ausente!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        app.run_polling()



        


