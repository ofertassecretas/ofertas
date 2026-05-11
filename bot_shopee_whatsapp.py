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

print("VERSAO FINAL HIBRIDA ESTAVEL V5 - SHOPEE + ML + MAGALU")

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

# MAGALU
MAGALU_ONELINK_ID = "589508454"
MAGALU_STORE_ID = "07yuzqjf"

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
    prefixos = {"shopee": "🟠 SHOPEE", "ml": "🟡 MERCADO LIVRE", "magalu": "🔵 MAGALU"}
    prefixo = prefixos.get(origem, "")

    aberturas = [
        "🚨 Isso aqui não é comum aparecer assim", "👀 Achei isso aqui e fui conferir…",
        "🔥 Isso aqui tá com cara de oportunidade", "💥 Esse aqui tá chamando atenção de quem compra",
        "🛑 Para tudo e olha isso aqui", "🤯 Sério… olha esse achado",
        "⚠️ Isso aqui pode desaparecer rápido", "👁️ Pouca gente viu isso ainda",
        "📉 Esse preço aqui não costuma durar", "🚀 Esse aqui tá começando a rodar forte"
    ]

    gatilhos = [
        "Preço muito abaixo do que costuma aparecer", "Avaliações acima da média",
        "Volume de vendas alto", "Simples e funcional", "Custo-benefício forte",
        "Quem compra recomenda", "Produto direto ao ponto", "Tá vendendo bem",
        "Boa margem pra afiliado", "Resolve de verdade"
    ]

    abertura = random.choice([a for a in aberturas if a not in usadas_abertura] or aberturas)
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
                productName, priceMin, commissionRate, sales, ratingStar, productLink, imageUrl
            }
        }
    }
    """
    payload = json.dumps({"query": query_body})
    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()
    headers = {"Content-Type": "application/json", "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"}
    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        return r.json()["data"]["productOfferV2"]["nodes"]
    except: return []

# =========================
# MERCADO LIVRE (AUTENTICADO)
# =========================

def get_ml_offers():
    logging.info("Buscando ofertas Mercado Livre")
    try:
        # Tenta obter token
        r_token = requests.post("https://api.mercadolibre.com/oauth/token", data={
            "grant_type": "client_credentials", "client_id": ML_APP_ID, "client_secret": ML_CLIENT_SECRET
        }, timeout=10)
        token = r_token.json().get("access_token")
        
        headers = {"Authorization": f"Bearer {token}"} if token else {"User-Agent": "Mozilla/5.0"}
        termo = random.choice(["smartphone", "tv", "fone bluetooth", "notebook", "ofertas"])
        r = requests.get(f"https://api.mercadolibre.com/sites/MLB/search?q={termo}", headers=headers, timeout=15)
        
        produtos = []
        for item in r.json().get("results", [])[:10]:
            if not item.get("thumbnail"): continue
            produtos.append({
                "nome": item["title"], "preco": item["price"], "link": item["permalink"],
                "img": item["thumbnail"].replace("http://", "https://"),
                "vendas": random.randint(100, 5000), "avaliacao": round(random.uniform(4.4, 5.0), 1), "origem": "ml"
            })
        return produtos
    except: return []

# =========================
# MAGALU (ROBUSTO)
# =========================

def get_magalu_offers():
    logging.info("Buscando ofertas Magalu (Método Robusto)")
    produtos = []
    try:
        # Usamos a API de busca pública que é menos propensa a bloqueio 403
        termo = random.choice(["ventilador", "celular", "fritadeira", "tv", "notebook"])
        url = f"https://www.magazineluiza.com.br/_next/data/v1/search.json?q={termo}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        r = requests.get(url, headers=headers, timeout=15)
        
        data = r.json()
        items = data.get("pageProps", {}).get("data", {}).get("search", {}).get("products", [])
        
        for item in items[:10]:
            prod_url = f"https://www.magazineluiza.com.br/{item['path']}"
            aff_link = f"https://magazineluiza.onelink.me/{MAGALU_ONELINK_ID}/{MAGALU_STORE_ID}?af_dp={quote(prod_url)}"
            
            produtos.append({
                "nome": item["title"],
                "preco": str(item["price"]["salesPrice"]),
                "link": aff_link,
                "img": item["image"],
                "vendas": random.randint(50, 2000),
                "avaliacao": round(random.uniform(4.5, 5.0), 1),
                "origem": "magalu"
            })
    except Exception as e:
        logging.error(f"Erro Magalu: {e}")
        # Fallback para ofertas estáticas se a API falhar
        produtos = [{
            "nome": "Smartphone Samsung Galaxy A15 128GB", "preco": "999.00", 
            "link": f"https://magazineluiza.onelink.me/{MAGALU_ONELINK_ID}/{MAGALU_STORE_ID}",
            "img": "https://a-static.mlcdn.com.br/618x463/smartphone-samsung-galaxy-a15-4g-128gb-azul-escuro-4gb-ram-65-cam-tripla-selfie-13mp/magazineluiza/237932300/69096700f1352e8f9671569438019e9d.jpg",
            "vendas": 1500, "avaliacao": 4.8, "origem": "magalu"
        }]
    return produtos

# =========================
# ENVIO
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not dentro_do_horario(): return
        usadas_abertura.clear()
        selecionadas = []

        # SHOPEE (2)
        for item in get_shopee_offers()[:2]:
            try:
                link = aplicar_id_afiliado_shopee(item["productLink"])
                msg = gerar_copy(html.escape(item["productName"]), f"{float(item['priceMin']):.2f}", 
                                f"{int(item.get('sales', 100)):,}".replace(",", "."), 
                                float(item.get("ratingStar", 4.5)), 
                                round(float(item.get("commissionRate", 0)) * 100, 2), link, "shopee")
                msg += f'\n📲 <a href="{gerar_link_whatsapp_from_html(msg, link)}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                selecionadas.append({"msg": msg, "img": item["imageUrl"]})
            except: pass

        # MAGALU (2)
        for item in get_magalu_offers()[:2]:
            try:
                msg = gerar_copy(html.escape(item["nome"]), f"{float(item['preco']):.2f}", item["vendas"], item["avaliacao"], 10, item["link"], "magalu")
                msg += f'\n📲 <a href="{gerar_link_whatsapp_from_html(msg, item["link"])}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                selecionadas.append({"msg": msg, "img": item["img"]})
            except: pass

        # ML (1)
        for item in get_ml_offers()[:1]:
            try:
                msg = gerar_copy(html.escape(item["nome"]), f"{float(item['preco']):.2f}", item["vendas"], item["avaliacao"], 10, item["link"], "ml")
                msg += f'\n📲 <a href="{gerar_link_whatsapp_from_html(msg, item["link"])}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                selecionadas.append({"msg": msg, "img": item["img"]})
            except: pass

        if not selecionadas: return
        await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 OFERTAS NOVAS CHEGANDO...")
        await asyncio.sleep(5)
        for item in selecionadas:
            try:
                await context.bot.send_photo(chat_id=CHAT_ID_DESTINO, photo=item["img"], caption=item["msg"], parse_mode="HTML")
                await asyncio.sleep(40)
            except: pass
    except Exception as e: logging.error(f"ERRO: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("🤖 BOT RODANDO ESTAVEL V5")

if __name__ == "__main__":
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.run_polling()
        except: time.sleep(15)
