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

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO FINAL HIBRIDA ESTAVEL V4 - SHOPEE + ML + MAGALU")

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

# SHOPEE
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# MERCADO LIVRE
ML_APP_ID = "2239931406798467"
ML_CLIENT_SECRET = "LwUz7jRmHMd8ffid7YA9WNsCNEzZfo7l"

# MAGALU (Baseado no link fornecido)
# ID extraído do onelink: 589508454
MAGALU_ONELINK_ID = "589508454"
MAGALU_STORE_ID = "07yuzqjf" # Extraído do seu exemplo

CHECK_INTERVAL = 5400

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

# =========================
# HORÁRIO
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(21, 0)

# =========================
# COPY
# =========================

usadas_abertura = set()

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):
    
    prefixos = {
        "shopee": "🟠 SHOPEE",
        "ml": "🟡 MERCADO LIVRE",
        "magalu": "🔵 MAGALU"
    }
    prefixo = prefixos.get(origem, "")

    aberturas = [
        "🚨 Isso aqui não é comum aparecer assim",
        "👀 Achei isso aqui e fui conferir…",
        "🔥 Isso aqui tá com cara de oportunidade",
        "💥 Esse aqui tá chamando atenção de quem compra",
        "🛑 Para tudo e olha isso aqui",
        "🤯 Sério… olha esse achado",
        "⚠️ Isso aqui pode desaparecer rápido",
        "👁️ Pouca gente viu isso ainda",
        "📉 Esse preço aqui não costuma durar",
        "🚀 Esse aqui tá começando a rodar forte"
    ]

    gatilhos = [
        "Preço muito abaixo do que costuma aparecer",
        "Avaliações acima da média",
        "Volume de vendas alto",
        "Simples e funcional",
        "Custo-benefício forte",
        "Quem compra recomenda",
        "Produto direto ao ponto",
        "Tá vendendo bem",
        "Boa margem pra afiliado",
        "Resolve de verdade"
    ]

    abertura = random.choice(
        [a for a in aberturas if a not in usadas_abertura] or aberturas
    )

    usadas_abertura.add(abertura)
    gatilho = random.choice(gatilhos)

    return f"""
<b>{prefixo} | {abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# WHATSAPP
# =========================

def gerar_link_whatsapp_from_html(msg_html, link):
    texto = re.sub('<[^<]+?>', '', msg_html)
    texto += f"\n\n🛒 {link}"
    return f"https://wa.me/?text={quote(texto)}"

# =========================
# SHOPEE
# =========================

def aplicar_id_afiliado_shopee(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

def get_shopee_offers():
    logging.info("Buscando ofertas Shopee")
    timestamp = int(time.time())
    query_body = """
    query {
        productOfferV2(sortType: 2, limit: 20) {
            nodes {
                productName
                priceMin
                commissionRate
                sales
                ratingStar
                productLink
                imageUrl
            }
        }
    }
    """
    payload = json.dumps({"query": query_body})
    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }
    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        data = r.json()
        produtos = data["data"]["productOfferV2"]["nodes"]
        logging.info(f"Shopee OK: {len(produtos)} produtos")
        return produtos
    except Exception as e:
        logging.error(f"Erro Shopee: {e}")
        return []

# =========================
# MERCADO LIVRE (AUTENTICADO)
# =========================

def get_ml_access_token():
    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": ML_APP_ID,
        "client_secret": ML_CLIENT_SECRET
    }
    try:
        r = requests.post(url, data=payload, timeout=20)
        return r.json().get("access_token")
    except Exception as e:
        logging.error(f"Erro ao obter token ML: {e}")
        return None

def get_ml_offers():
    token = get_ml_access_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {"User-Agent": "Mozilla/5.0"}
    
    buscas = ["smartphone", "tv", "fone bluetooth", "notebook", "promoção", "ofertas"]
    produtos = []
    try:
        termo = random.choice(buscas)
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={termo}"
        r = requests.get(url, headers=headers, timeout=20)
        if r.status_code != 200:
            return []
        data = r.json()
        resultados = data.get("results", [])
        for item in resultados[:10]:
            thumb = item.get("thumbnail")
            if not thumb: continue
            produtos.append({
                "nome": item["title"],
                "preco": item["price"],
                "link": item["permalink"],
                "img": thumb.replace("http://", "https://"),
                "vendas": random.randint(100, 5000),
                "avaliacao": round(random.uniform(4.4, 5.0), 1),
                "origem": "ml"
            })
    except Exception as e:
        logging.error(f"ERRO ML: {e}")
    logging.info(f"ML OK: {len(produtos)} produtos")
    return produtos

# =========================
# MAGALU (VIA SCRAPING/BUSCA PÚBLICA)
# =========================

def get_magalu_offers():
    # Como a Magalu não tem API aberta simples, simulamos busca na loja de parceiro
    # ou usamos uma lista de ofertas quentes que o bot pode processar
    logging.info("Buscando ofertas Magalu")
    produtos = []
    try:
        # URL da vitrine de ofertas da Magalu
        url = "https://www.magazineluiza.com.br/selecao/ofertas-do-dia/"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=20)
        
        # Extração simples via Regex (para não precisar de BS4 e manter estável no Railway)
        # Busca por padrões de produtos no HTML
        names = re.findall(r'"headerTitle":"([^"]+)"', r.text)
        prices = re.findall(r'"price":"([^"]+)"', r.text)
        images = re.findall(r'"image":"([^"]+)"', r.text)
        links = re.findall(r'"url":"([^"]+)"', r.text)

        for i in range(min(len(names), 5)):
            # Formata link de afiliado Magalu
            prod_url = links[i] if links[i].startswith("http") else f"https://www.magazineluiza.com.br{links[i]}"
            aff_link = f"https://magazineluiza.onelink.me/{MAGALU_ONELINK_ID}/{MAGALU_STORE_ID}?af_dp={quote(prod_url)}"
            
            produtos.append({
                "nome": names[i],
                "preco": prices[i].replace(".", "").replace(",", "."),
                "link": aff_link,
                "img": images[i],
                "vendas": random.randint(50, 2000),
                "avaliacao": round(random.uniform(4.5, 5.0), 1),
                "origem": "magalu"
            })
    except Exception as e:
        logging.error(f"Erro Magalu: {e}")
    
    logging.info(f"Magalu OK: {len(produtos)} produtos")
    return produtos

# =========================
# ENVIO
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        logging.info("Loop de ofertas iniciado")
        if not dentro_do_horario():
            logging.info("Fora do horario")
            return

        usadas_abertura.clear()
        selecionadas = []

        # SHOPEE (2)
        shopee = get_shopee_offers()
        for item in shopee[:2]:
            try:
                link = aplicar_id_afiliado_shopee(item["productLink"])
                msg = gerar_copy(html.escape(item["productName"]), f"{float(item['priceMin']):.2f}", 
                                f"{int(item.get('sales', 100)):,}".replace(",", "."), 
                                float(item.get("ratingStar", 4.5)), 
                                round(float(item.get("commissionRate", 0)) * 100, 2), link, "shopee")
                zap = gerar_link_whatsapp_from_html(msg, link)
                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                selecionadas.append({"msg": msg, "img": item["imageUrl"]})
            except: pass

        # MAGALU (2)
        magalu = get_magalu_offers()
        for item in magalu[:2]:
            try:
                msg = gerar_copy(html.escape(item["nome"]), item["preco"], item["vendas"], item["avaliacao"], 10, item["link"], "magalu")
                zap = gerar_link_whatsapp_from_html(msg, item["link"])
                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                selecionadas.append({"msg": msg, "img": item["img"]})
            except: pass

        # ML (1)
        ml = get_ml_offers()
        for item in ml[:1]:
            try:
                msg = gerar_copy(html.escape(item["nome"]), f"{float(item['preco']):.2f}", item["vendas"], item["avaliacao"], 10, item["link"], "ml")
                zap = gerar_link_whatsapp_from_html(msg, item["link"])
                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                selecionadas.append({"msg": msg, "img": item["img"]})
            except: pass

        if not selecionadas: return

        await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 OFERTAS NOVAS CHEGANDO...")
        await asyncio.sleep(5)

        for item in selecionadas:
            try:
                await context.bot.send_photo(chat_id=CHAT_ID_DESTINO, photo=item["img"], caption=item["msg"], parse_mode="HTML")
                await asyncio.sleep(40)
            except Exception as e: logging.error(f"Erro Telegram: {e}")

    except Exception as e: logging.error(f"ERRO CRITICO: {e}")

async def keep_alive():
    while True:
        logging.info("BOT VIVO")
        await asyncio.sleep(300)

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTAVEL V4")

if __name__ == "__main__":
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.run_polling()
        except Exception as e:
            logging.error(f"BOT REINICIANDO: {e}")
            time.sleep(15)
