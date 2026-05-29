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
print("VERSAO SHOPEE V19 - DE-DUPLICAÇÃO TOTAL")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Caminho para o arquivo de memória
HISTORICO_FILE = "historico_envios.json"

# Intervalo entre ciclos (em segundos) - 5400s = 1h30
CHECK_INTERVAL = 5400

# Filtros de Qualidade
PRECO_MIN = 25.0 
PRECO_MAX = 15000.0
COMISSAO_MIN = 0.05
VENDAS_MIN = 50
RATING_MIN = 4.5

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# NICHOS E SUBCATEGORIAS
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
# GESTÃO DE MEMÓRIA PERSISTENTE (REFORMULADA)
# ==========================================

def extrair_id_produto(url):
    """Extrai o ID do produto ou o caminho base para evitar repetição por links diferentes."""
    try:
        parsed = urlparse(url)
        # Tenta pegar o caminho sem parâmetros de rastreio
        path = parsed.path
        if not path or path == "/":
            # Se for um link encurtado ou estranho, usa o link todo sem query
            return urlunparse(parsed._replace(query=""))
        return path
    except:
        return url

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, 'r') as f:
                data = json.load(f)
                # Garante que as chaves antigas (links) sejam tratadas ou limpamos se estiver bagunçado
                return data
        except:
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
    
    for key, info in historico.items():
        try:
            # Suporta formato antigo (string) e novo (dicionário)
            data_str = info if isinstance(info, str) else info.get("data")
            data_envio = datetime.fromisoformat(data_str)
            if agora - data_envio < timedelta(days=10):
                novo_historico[key] = info
        except:
            continue
            
    salvar_historico(novo_historico)
    return novo_historico

def eh_repetido_persistente(titulo, link, historico, lista_ciclo_atual):
    # 1. Normalização para comparação
    id_prod = extrair_id_produto(link)
    t_novo = normalizar_texto(titulo)
    
    # 2. Verifica no histórico de 10 dias (por ID/Link e por Título similar)
    if id_prod in historico:
        logging.info(f"BLOQUEADO (Histórico Link): {titulo}")
        return True
    
    for key, info in historico.items():
        t_hist = normalizar_texto(info.get("titulo", "")) if isinstance(info, dict) else ""
        if t_hist and SequenceMatcher(None, t_novo, t_hist).ratio() > 0.75: # Aumentado rigor
            logging.info(f"BLOQUEADO (Histórico Título Similar): {titulo} vs {info.get('titulo')}")
            return True

    # 3. Verifica no ciclo atual
    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.60:
            logging.info(f"BLOQUEADO (Ciclo Atual Similar): {titulo}")
            return True
            
    return False

# ==========================================
# UTILITÁRIOS
# ==========================================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
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
    except:
        return link

def get_melhores_ofertas():
    historico = limpar_historico_antigo()
    ofertas_finais = []
    
    nichos = list(KEYWORDS_ESTRUTURADAS.keys())
    random.shuffle(nichos)
    
    for nicho in nichos:
        logging.info(f"Processando nicho: {nicho}")
        subs = list(KEYWORDS_ESTRUTURADAS[nicho].keys())
        subs_escolhidas = random.sample(subs, k=min(2, len(subs)))
        
        for sub in subs_escolhidas:
            kw = random.choice(KEYWORDS_ESTRUTURADAS[nicho][sub])
            produtos = buscar_shopee(kw)
            
            if not produtos: continue

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
                logging.info(f"Selecionado: {candidatos_sub[0]['productName']} (Sub: {sub})")
                
    return ofertas_finais

# ==========================================
# EXECUÇÃO DO BOT
# ==========================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    if not dentro_do_horario():
        logging.info("Fora do horário de envio.")
        return

    logging.info("Iniciando ciclo de busca de ofertas...")
    ofertas = get_melhores_ofertas()
    
    if not ofertas:
        logging.warning("Nenhuma oferta qualificada encontrada.")
        return

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
            
            # Registrar no histórico com título para comparação de similaridade
            id_prod = extrair_id_produto(link_original)
            historico[id_prod] = {
                "data": datetime.now().isoformat(),
                "titulo": item["productName"],
                "link": link_original
            }
            salvar_historico(historico)
            
            await asyncio.sleep(45)
            
        except Exception as e:
            logging.error(f"Erro no envio: {e}")

async def post_init(app):
    limpar_historico_antigo()
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V19 Ativo!")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("ERRO: TELEGRAM_TOKEN ausente!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        app.run_polling()




        


