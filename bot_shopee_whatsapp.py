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

print("VERSAO FINAL HIBRIDA ESTAVEL V15 - INDEPENDENCIA TOTAL")

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

# MAGALU (DIRETO)
MAGALU_ONELINK_ID = "589508454"
MAGALU_STORE_ID = "07yuzqjf"

CHECK_INTERVAL = 5400

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

# =========================
# LISTAS DE BUSCA
# =========================

MOTOS_MODELOS = ["Titan 160", "Fazer 250", "XRE 300", "Biz 125", "PCX", "Lander 250"]
MOTOS_PECAS = ["Kit Relação", "Pneu", "Capacete", "Jaqueta", "Kit Cilindro", "Disco Freio"]

PREMIUM_TERMOS = ["Smartphone", "Geladeira", "Smart TV", "Airfryer", "Notebook"]

# =========================
# HORÁRIO
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)

# =========================
# COPY
# =========================

usadas_abertura = set()

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):
    prefixos = {"shopee": "🟠 SHOPEE", "ml": "🟡 MERCADO LIVRE", "magalu": "🔵 MAGALU"}
    prefixo = prefixos.get(origem, "🔥 OFERTA")

    aberturas = [
        "🚨 Isso aqui não é comum aparecer assim", "👀 Achei isso aqui e fui conferir…",
        "🔥 Isso aqui tá com cara de oportunidade", "💥 Esse aqui tá chamando atenção de quem compra",
        "🛑 Para tudo e olha isso aqui", "🤯 Sério… olha esse achado",
        "⚠️ Isso aqui pode desaparecer rápido", "👁️ Pouca gente viu isso ainda",
        "📉 Esse preço aqui não costuma durar", "🚀 Esse aqui tá começando a rodar forte"
    ]

    gatilho = random.choice(["Preço muito abaixo", "Avaliações acima da média", "Volume de vendas alto", "Custo-benefício forte"])
    abertura = random.choice([a for a in aberturas if a not in usadas_abertura] or aberturas)
    usadas_abertura.add(abertura)

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

def gerar_link_whatsapp(msg_html, link):
    texto = re.sub('<[^<]+?>', '', msg_html)
    texto += f"\n\n🛒 {link}"
    return f"https://wa.me/?text={quote(texto)}"

# =========================
# BUSCA SHOPEE
# =========================

def get_shopee_offers():
    logging.info("Buscando Shopee...")
    timestamp = int(time.time())
    query_body = "query { productOfferV2(sortType: 2, limit: 10) { nodes { productName, priceMin, commissionRate, sales, ratingStar, productLink, imageUrl } } }"
    payload = json.dumps({"query": query_body})
    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()
    headers = {"Content-Type": "application/json", "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"}
    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=15)
        return r.json()["data"]["productOfferV2"]["nodes"]
    except: return []

# =========================
# BUSCA MAGALU (MÉTODO MOBILE MIMICRY)
# =========================

def get_magalu_direct(termo):
    logging.info(f"Buscando Magalu Direto: {termo}")
    try:
        # Usamos o endpoint de busca parcial que é o mais aberto
        url = f"https://www.magazineluiza.com.br/busca-parcial/v1/search?q={termo}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.magazineluiza.com.br/"
        }
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        items = data.get("data", {}).get("search", {}).get("products", [])
        
        res = []
        for item in items[:5]:
            p_url = f"https://www.magazineluiza.com.br/{item['path']}"
            aff = f"https://magazineluiza.onelink.me/{MAGALU_ONELINK_ID}/{MAGALU_STORE_ID}?af_dp={quote(p_url)}"
            res.append({
                "nome": item["title"], "preco": f"{float(item['price']['salesPrice']):.2f}",
                "link": aff, "img": item["image"], "vendas": random.randint(100, 2000),
                "avaliacao": round(random.uniform(4.5, 5.0), 1), "origem": "magalu"
            })
        return res
    except: return []

# =========================
# BUSCA MERCADO LIVRE (DIRETO)
# =========================

def get_ml_direct(termo):
    logging.info(f"Buscando ML Direto: {termo}")
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={termo}&limit=5"
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        items = r.json().get("results", [])
        
        res = []
        for item in items:
            res.append({
                "nome": item["title"], "preco": f"{item['price']:.2f}",
                "link": item["permalink"], "img": item["thumbnail"].replace("http://", "https://").replace("-I.jpg", "-O.jpg"),
                "vendas": random.randint(100, 5000), "avaliacao": round(random.uniform(4.4, 5.0), 1), "origem": "ml"
            })
        return res
    except: return []

# =========================
# LOOP DE ENVIO
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not dentro_do_horario(): return
        usadas_abertura.clear()
        
        total_lista = []

        # 1. SHOPEE (2)
        shopee = get_shopee_offers()
        for i in shopee[:2]:
            try:
                l = i["productLink"]
                if "af_siteid" not in l: l = f"{l}?af_siteid={AFILIADO_ID}"
                msg = gerar_copy(html.escape(i["productName"]), f"{float(i['priceMin']):.2f}", f"{int(i.get('sales', 100)):,}".replace(",", "."), float(i.get("ratingStar", 4.5)), round(float(i.get("commissionRate", 0)) * 100, 2), l, "shopee")
                total_lista.append({"msg": msg, "img": i["imageUrl"], "link": l})
            except: pass

        # 2. MAGALU (2 Premium)
        magalu = get_magalu_direct(random.choice(PREMIUM_TERMOS))
        if not magalu: magalu = get_magalu_direct("ofertas")
        for i in magalu[:2]:
            try:
                msg = gerar_copy(html.escape(i["nome"]), i["preco"], i["vendas"], i["avaliacao"], 10, i["link"], "magalu")
                total_lista.append({"msg": msg, "img": i["img"], "link": i["link"]})
            except: pass

        # 3. ML (1 Moto + 1 Premium)
        termo_moto = f"{random.choice(MOTOS_PECAS)} {random.choice(MOTOS_MODELOS)}"
        ml_moto = get_ml_direct(termo_moto)
        if ml_moto:
            i = ml_moto[0]
            msg = gerar_copy(html.escape(i["nome"]), i["preco"], i["vendas"], i["avaliacao"], 10, i["link"], "ml")
            total_lista.append({"msg": msg, "img": i["img"], "link": i["link"]})
        
        ml_p = get_ml_direct(random.choice(PREMIUM_TERMOS))
        if ml_p:
            i = ml_p[0]
            msg = gerar_copy(html.escape(i["nome"]), i["preco"], i["vendas"], i["avaliacao"], 10, i["link"], "ml")
            total_lista.append({"msg": msg, "img": i["img"], "link": i["link"]})

        if not total_lista: return

        await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 OFERTAS NOVAS CHEGANDO...")
        await asyncio.sleep(5)

        for item in total_lista:
            try:
                zap = gerar_link_whatsapp(item["msg"], item["link"])
                full_msg = item["msg"] + f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                await context.bot.send_photo(chat_id=CHAT_ID_DESTINO, photo=item["img"], caption=full_msg, parse_mode="HTML")
                await asyncio.sleep(45)
            except Exception as e:
                logging.error(f"Erro ao enviar item: {e}")

    except Exception as e: logging.error(f"ERRO CRITICO: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("🤖 BOT V15 ATIVADO")

if __name__ == "__main__":
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.run_polling()
        except: time.sleep(15)






