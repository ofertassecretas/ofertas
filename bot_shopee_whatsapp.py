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

print("VERSAO FINAL HIBRIDA ESTAVEL V18 - MAGALU ONELINK + ML DIVERSO")

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

# MAGALU (ONELINK)
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

MOTOS_MODELOS = ["Titan 160", "Fazer 250", "XRE 300", "Biz 125", "Twister 250", "Factor 150", "PCX", "Lander 250", "CB300", "Tornado"]
MOTOS_PECAS = ["Kit Relação", "Pneu", "Capacete", "Jaqueta", "Farol", "Disco Freio", "Kit Cilindro", "Bateria", "Guidão", "Retrovisor"]

PREMIUM_TERMOS = ["Smartphone", "Geladeira", "Smart TV", "Airfryer", "Notebook", "Lavadora", "Fogão", "Microondas", "Monitor Gamer"]

# =========================
# HORÁRIO
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)

# =========================
# COPY E FORMATACAO
# =========================

usadas_abertura = set()

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):
    prefixos = {"shopee": "🟠 SHOPEE", "ml": "🟡 MERCADO LIVRE", "magalu": "🔵 MAGALU"}
    prefixo = prefixos.get(origem, "🔥 OFERTA")

    aberturas = [
        "🚨 Isso aqui não é comum aparecer assim", "👀 Achei isso aqui e fui conferir…",
        "🔥 Isso aqui tá com cara de oportunidade", "💥 Esse aqui tá chamando atenção de quem compra",
        "🛑 Para tudo e olha isso aqui", "🤯 Sério… olha esse achado",
        "⚠️ Isso aqui pode desaparecer rápido", "👁️ Pouca gente viu isso ainda"
    ]

    gatilho = random.choice(["Preço muito abaixo", "Avaliações acima da média", "Volume de vendas alto", "Custo-benefício forte"])
    abertura = random.choice([a for a in aberturas if a not in usadas_abertura] or aberturas)
    usadas_abertura.add(abertura)

    # Telegram (HTML)
    msg_tg = f"""
<b>{prefixo} | {abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>
"""
    
    # WhatsApp (Markdown + Sem Comissão)
    msg_wa = f"""
*{prefixo} | {abertura}*

🔥 *{nome}*

{gatilho}

💰 *R$ {preco}*
⭐ {avaliacao} | 🛒 *{vendas} vendas*

⚠️ Pode subir de preço

🛒 {link}
"""
    return msg_tg, msg_wa

def gerar_link_whatsapp(msg_wa):
    return f"https://wa.me/?text={quote(msg_wa.strip())}"

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
# BUSCA MAGALU (FIX ONELINK)
# =========================

def get_magalu_direct(termo):
    logging.info(f"Buscando Magalu Direto: {termo}")
    try:
        url = f"https://www.magazineluiza.com.br/busca-parcial/v1/search?q={quote(termo)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.magazineluiza.com.br/"
        }
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        items = data.get("data", {}).get("search", {}).get("products", [])
        
        res = []
        for item in items[:5]:
            try:
                p_url = f"https://www.magazineluiza.com.br/{item['path']}"
                aff = f"https://magazineluiza.onelink.me/{MAGALU_ONELINK_ID}/{MAGALU_STORE_ID}?af_dp={quote(p_url)}"
                res.append({
                    "nome": item["title"], "preco": f"{float(item['price']['salesPrice']):.2f}",
                    "link": aff, "img": item["image"], "vendas": random.randint(100, 2000),
                    "avaliacao": round(random.uniform(4.5, 5.0), 1), "origem": "magalu", "comissao": 4
                })
            except: continue
        return res
    except: return []

# =========================
# BUSCA MERCADO LIVRE (DIVERSIFICADA)
# =========================

def get_ml_direct(termo):
    # Sorteia uma página (offset) para não pegar sempre os mesmos primeiros resultados
    offset = random.randint(0, 30)
    logging.info(f"Buscando ML Direto: {termo} (Offset: {offset})")
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={quote(termo)}&limit=10&offset={offset}"
        r = requests.get(url, timeout=10)
        items = r.json().get("results", [])
        
        res = []
        for item in items:
            try:
                img_id = item["thumbnail_id"]
                img_url = f"https://http2.mlstatic.com/D_NQ_NP_{img_id}-O.webp"
                res.append({
                    "nome": item["title"], "preco": f"{item['price']:.2f}",
                    "link": item["permalink"], "img": img_url,
                    "vendas": int(item.get("sold_quantity", random.randint(50, 500))), 
                    "avaliacao": round(random.uniform(4.4, 5.0), 1), "origem": "ml", "comissao": 5
                })
            except: continue
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
                comis = round(float(i.get("commissionRate", 0)) * 100, 2)
                msg_tg, msg_wa = gerar_copy(html.escape(i["productName"]), f"{float(i['priceMin']):.2f}", f"{int(i.get('sales', 100)):,}".replace(",", "."), float(i.get("ratingStar", 4.5)), comis, l, "shopee")
                total_lista.append({"msg_tg": msg_tg, "msg_wa": msg_wa, "img": i["imageUrl"], "link": l})
            except: pass

        # 2. MAGALU (2)
        termo_magalu = random.choice(PREMIUM_TERMOS)
        magalu = get_magalu_direct(termo_magalu)
        for i in magalu[:2]:
            try:
                msg_tg, msg_wa = gerar_copy(html.escape(i["nome"]), i["preco"], i["vendas"], i["avaliacao"], i["comissao"], i["link"], "magalu")
                total_lista.append({"msg_tg": msg_tg, "msg_wa": msg_wa, "img": i["img"], "link": i["link"]})
            except: pass

        # 3. ML (2)
        termo_moto = f"{random.choice(MOTOS_PECAS)} {random.choice(MOTOS_MODELOS)}"
        ml_moto = get_ml_direct(termo_moto)
        if ml_moto:
            i = random.choice(ml_moto[:5])
            msg_tg, msg_wa = gerar_copy(html.escape(i["nome"]), i["preco"], i["vendas"], i["avaliacao"], i["comissao"], i["link"], "ml")
            total_lista.append({"msg_tg": msg_tg, "msg_wa": msg_wa, "img": i["img"], "link": i["link"]})
        
        termo_ml_p = random.choice(PREMIUM_TERMOS)
        ml_p = get_ml_direct(termo_ml_p)
        if ml_p:
            i = random.choice(ml_p[:5])
            msg_tg, msg_wa = gerar_copy(html.escape(i["nome"]), i["preco"], i["vendas"], i["avaliacao"], i["comissao"], i["link"], "ml")
            total_lista.append({"msg_tg": msg_tg, "msg_wa": msg_wa, "img": i["img"], "link": i["link"]})

        if not total_lista: return

        await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 OFERTAS NOVAS CHEGANDO...")
        await asyncio.sleep(5)

        for item in total_lista:
            try:
                zap_link = gerar_link_whatsapp(item["msg_wa"])
                full_msg = item["msg_tg"] + f'\n📲 <a href="{zap_link}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                await context.bot.send_photo(chat_id=CHAT_ID_DESTINO, photo=item["img"], caption=full_msg, parse_mode="HTML")
                await asyncio.sleep(45)
            except Exception as e:
                logging.error(f"Erro ao enviar item: {e}")

    except Exception as e: logging.error(f"ERRO CRITICO: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("🤖 BOT V18 ATIVADO")

if __name__ == "__main__":
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.run_polling()
        except: time.sleep(15)





