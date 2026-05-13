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

print("VERSAO FINAL HIBRIDA ESTAVEL V10 - MOTO + PREMIUM + LOMADEE FIX")

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

# LOMADEE / SOCIALSOUL
LOMADEE_TOKEN = "ra1-ATlyjfiMkWhSWRkpEs53kgoPVSQ"
LOMADEE_SOURCE_ID = "6ff2699e-ceaa-4fad-a58a-8b91f885485f"

CHECK_INTERVAL = 5400

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

# =========================
# LISTAS DE BUSCA (MOTO E PREMIUM)
# =========================

MOTOS_MODELOS = ["Titan 125", "Titan 150", "Titan 160", "Fazer 150", "Fazer 250", "Lander 250", "CB300", "XRE 190", "XRE 300", "Biz 125", "Twister 250", "Tornado", "PCX", "Factor 150"]
MOTOS_PECAS = ["Kit Relação", "Kit Embreagem", "Pneu", "Guidão", "Roda", "Manete", "Banco", "Cabo de Freio", "Estator", "Kit Cilindro", "Biela", "Rolamento", "Corrente Comando", "Carenagem", "Farol", "Vela Iridium", "CDI", "Bobina", "Carburador", "Filtro de Ar", "Bomba Combustivel", "Pedal Cambio", "Disco Freio", "Capacete", "Luva", "Jaqueta"]

PREMIUM_TERMOS = ["Smartphone", "Geladeira", "Smart TV", "Fogão", "Microondas", "Airfryer", "Notebook", "Lavadora"]

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
    prefixos = {"shopee": "🟠 SHOPEE", "ml": "🟡 MERCADO LIVRE", "magalu": "🔵 MAGALU", "lomadee": "🔥 OFERTA"}
    prefixo = prefixos.get(origem, "🔥 OFERTA")

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
# BUSCA LOMADEE (MÉTODO COMPATÍVEL V2/V3)
# =========================

def get_lomadee_offers(termo):
    logging.info(f"Buscando Lomadee para: {termo}")
    # Tentamos primeiro o endpoint que aceita o Token ra1- (V2)
    try:
        url = f"http://api.lomadee.com/v2/{LOMADEE_TOKEN}/offer/_search"
        params = {"sourceId": LOMADEE_SOURCE_ID, "keyword": termo, "size": 5}
        r = requests.get(url, params=params, timeout=10)
        
        if r.status_code == 200:
            data = r.json()
            offers = data.get("offers", [])
            res = []
            for item in offers:
                loja_nome = item.get("store", {}).get("name", "").lower()
                origem = "lomadee"
                if "magazineluiza" in loja_nome or "magalu" in loja_nome: origem = "magalu"
                elif "mercado livre" in loja_nome: origem = "ml"
                
                res.append({
                    "nome": item["name"], "preco": f"{item['price']:.2f}",
                    "link": item["link"], "img": item["thumbnail"],
                    "vendas": random.randint(100, 5000), "avaliacao": round(random.uniform(4.5, 5.0), 1),
                    "origem": origem, "comissao": 10
                })
            return res
    except: pass

    # Se falhar, tentamos o endpoint V3 Beta (SocialSoul) com o token como API KEY
    try:
        url = "https://api-beta.lomadee.com.br/affiliate/products"
        headers = {"x-api-key": LOMADEE_TOKEN}
        params = {"search": termo, "limit": 5}
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            data = r.json()
            products = data.get("data", [])
            res = []
            for p in products:
                loja = "lomadee"
                if "magazineluiza" in p["url"]: loja = "magalu"
                elif "mercadolivre" in p["url"]: loja = "ml"
                preco_real = float(p["options"][0]["pricing"][0]["price"]) / 100
                res.append({
                    "nome": p["name"], "preco": f"{preco_real:.2f}",
                    "link": p["url"], "img": p["images"][0]["url"],
                    "vendas": random.randint(100, 5000), "avaliacao": round(random.uniform(4.5, 5.0), 1),
                    "origem": loja, "comissao": 10
                })
            return res
    except: pass
    
    return []

# =========================
# LOOP DE ENVIO
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not dentro_do_horario(): return
        usadas_abertura.clear()
        
        total_lista = []

        # 1. SHOPEE (2 ofertas)
        shopee = get_shopee_offers()
        for i in shopee[:2]:
            try:
                l = i["productLink"]
                if "af_siteid" not in l: l = f"{l}?af_siteid={AFILIADO_ID}"
                msg = gerar_copy(html.escape(i["productName"]), f"{float(i['priceMin']):.2f}", f"{int(i.get('sales', 100)):,}".replace(",", "."), float(i.get("ratingStar", 4.5)), round(float(i.get("commissionRate", 0)) * 100, 2), l, "shopee")
                total_lista.append({"msg": msg, "img": i["imageUrl"], "link": l})
            except: pass

        # 2. MAGALU (2 ofertas Premium)
        termo_magalu = random.choice(PREMIUM_TERMOS)
        magalu = get_lomadee_offers(f"Magalu {termo_magalu}")
        for i in magalu[:2]:
            try:
                msg = gerar_copy(html.escape(i["nome"]), i["preco"], i["vendas"], i["avaliacao"], 10, i["link"], "magalu")
                total_lista.append({"msg": msg, "img": i["img"], "link": i["link"]})
            except: pass

        # 3. MERCADO LIVRE (1 Moto + 1 Premium)
        # Oferta de Moto
        termo_moto = f"{random.choice(MOTOS_PECAS)} {random.choice(MOTOS_MODELOS)}"
        ml_moto = get_lomadee_offers(f"Mercado Livre {termo_moto}")
        if ml_moto:
            i = ml_moto[0]
            msg = gerar_copy(html.escape(i["nome"]), i["preco"], i["vendas"], i["avaliacao"], 10, i["link"], "ml")
            total_lista.append({"msg": msg, "img": i["img"], "link": i["link"]})
        
        # Oferta Premium ML
        termo_ml_p = random.choice(PREMIUM_TERMOS)
        ml_p = get_lomadee_offers(f"Mercado Livre {termo_ml_p}")
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
    logging.info("🤖 BOT V10 RODANDO")

if __name__ == "__main__":
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.run_polling()
        except Exception as e:
            logging.error(f"BOT REINICIANDO: {e}")
            time.sleep(15)



