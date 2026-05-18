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
from urllib.parse import quote, urljoin
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO FINAL HIBRIDA ESTAVEL V27 - MAGALU ROBUSTO FIX")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

MAGALU_API_KEY = os.getenv("MAGALU_API_KEY")
MAGALU_API_KEY_ID = os.getenv("MAGALU_API_KEY_ID")
MAGALU_API_SECRET = os.getenv("MAGALU_API_SECRET")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

MAGALU_ONELINK_ID = "589508454"
MAGALU_STORE_ID = "07yuzqjf"

ML_LISTA_URL = "https://mercadolivre.com/sec/167xbsR"

CHECK_INTERVAL = 5400
FUSO_BR = ZoneInfo("America/Sao_Paulo")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("debug_bot.txt", encoding="utf-8")
    ]
)

usadas_abertura = set()

CACHE_FILE = "cache_envios.json"
ML_LISTA_CACHE_FILE = "ml_lista_cache.json"

# -------------------------
# TERMOS
# -------------------------
PREMIUM_TERMOS = [
    "Smartphone", "Geladeira", "Smart TV", "Airfryer",
    "Notebook", "Lavadora", "Fogão", "Microondas", "Monitor Gamer"
]

MOTOS_MODELOS = [
    "Titan 160", "Fazer 250", "XRE 300", "Biz 125",
    "Twister 250", "Factor 150", "PCX", "Lander 250"
]

MOTOS_PECAS = [
    "Kit Relação", "Pneu", "Capacete", "Jaqueta",
    "Farol", "Disco Freio", "Bateria", "Retrovisor"
]

# -------------------------
# UTIL
# -------------------------
def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)

def carregar_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default

def salvar_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

cache_envios = carregar_json(CACHE_FILE, {"sent": []})
ml_lista_cache = carregar_json(ML_LISTA_CACHE_FILE, {"items": [], "updated": 0})

def cache_ja_enviado(key):
    return key in cache_envios["sent"]

def registrar_enviado(key):
    cache_envios["sent"].append(key)
    cache_envios["sent"] = cache_envios["sent"][-120:]
    salvar_json(CACHE_FILE, cache_envios)

# -------------------------
# COPY
# -------------------------
def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):

    prefixos = {
        "shopee": "🟠 SHOPEE",
        "ml": "🟡 MERCADO LIVRE",
        "magalu": "🔵 MAGALU"
    }

    prefixo = prefixos.get(origem, "🔥 OFERTA")

    abertura = random.choice([
        "🚨 Isso aqui não é comum",
        "🔥 Achado forte agora",
        "👀 Olha isso aqui",
        "⚠️ Oferta rara",
        "💥 Preço chamando atenção"
    ])

    msg_tg = (
        f"<b>{prefixo} | {abertura}</b>\n\n"
        f"🔥 <b>{nome}</b>\n\n"
        f"💰 <b>R$ {preco}</b>\n"
        f"⭐ {avaliacao} | 🛒 {vendas} vendas\n"
        f"💸 Comissão: <b>{comissao}%</b>\n\n"
        f"<a href=\"{link}\">🛒 COMPRAR AGORA</a>"
    )

    msg_wa = (
        f"{prefixo} | {abertura}\n\n"
        f"{nome}\n\n"
        f"R$ {preco}\n"
        f"{link}"
    )

    return msg_tg, msg_wa

def gerar_link_whatsapp(msg):
    return "https://wa.me/?text=" + quote(msg)

# -------------------------
# SHOPEE (INTACTO)
# -------------------------
def get_shopee_offers():
    try:
        timestamp = int(time.time())

        query_body = """
        query {
            productOfferV2(sortType: 2, limit: 10) {
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

        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)

        return r.json().get("data", {}).get("productOfferV2", {}).get("nodes", [])

    except Exception as e:
        logging.warning(f"Shopee erro: {e}")
        return []

# -------------------------
# ML (INTACTO)
# -------------------------
def get_ml_direct(termo):

    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={quote(termo)}&limit=10"
        r = requests.get(url, timeout=15)

        items = r.json().get("results", [])

        res = []

        for item in items:
            res.append({
                "id": item.get("id"),
                "nome": item.get("title"),
                "preco": f"{float(item.get('price', 0)):.2f}",
                "link": item.get("permalink"),
                "img": item.get("thumbnail"),
                "vendas": item.get("sold_quantity", 0),
                "avaliacao": round(random.uniform(4.3, 5.0), 1),
                "origem": "ml",
                "comissao": 5
            })

        return res

    except:
        return []

# -------------------------
# 🔵 MAGALU ROBUSTO (FIX REAL)
# -------------------------
def get_magalu_direct(termo):

    logging.info(f"Magalu robusto: {termo}")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "pt-BR"
    }

    urls = [
        f"https://www.magazinevoce.com.br/magazineshopandreonline/busca/{quote(termo)}/"
    ]

    produtos = []

    for url in urls:

        try:
            r = requests.get(url, headers=headers, timeout=20)

            match = re.search(
                r'window\.__NEXT_DATA__\s*=\s*(\{.*?\})\s*</script>',
                r.text,
                re.S
            )

            if not match:
                continue

            data = json.loads(match.group(1))

            encontrados = []

            def scan(obj):
                if isinstance(obj, dict):
                    if "title" in obj and ("price" in obj or "bestPrice" in obj):
                        encontrados.append(obj)
                    for v in obj.values():
                        scan(v)
                elif isinstance(obj, list):
                    for i in obj:
                        scan(i)

            scan(data)

            for item in encontrados[:10]:

                nome = item.get("title")
                preco = item.get("bestPrice") or item.get("price")
                path = item.get("url") or item.get("path")
                img = item.get("image") or ""

                if not nome or not path:
                    continue

                link = path if path.startswith("http") else "https://www.magazinevoce.com.br" + path

                produtos.append({
                    "id": hashlib.md5(link.encode()).hexdigest(),
                    "nome": nome,
                    "preco": str(preco),
                    "link": gerar_link_magalu(link),
                    "img": img,
                    "vendas": random.randint(200, 5000),
                    "avaliacao": round(random.uniform(4.3, 5.0), 1),
                    "origem": "magalu",
                    "comissao": random.randint(3, 8)
                })

        except Exception as e:
            logging.warning(f"Magalu erro: {e}")

    return produtos

# -------------------------
# LINK MAGALU AFILIADO (SEU ID MANTIDO)
# -------------------------
def gerar_link_magalu(url):
    return (
        f"https://magazineluiza.onelink.me/"
        f"{MAGALU_ONELINK_ID}/"
        f"{MAGALU_STORE_ID}"
        f"?af_dp={quote(url)}"
    )

# -------------------------
# LOOP PRINCIPAL
# -------------------------
async def send_ofertas(context):

    if not dentro_do_horario():
        return

    total = []

    # Shopee
    for i in get_shopee_offers()[:2]:
        try:
            link = i["productLink"]
            msg_tg, msg_wa = gerar_copy(
                i["productName"],
                f"{float(i['priceMin']):.2f}",
                i.get("sales", 0),
                i.get("ratingStar", 4.5),
                i.get("commissionRate", 0),
                link,
                "shopee"
            )

            total.append({"msg": msg_tg, "wa": msg_wa, "img": i.get("imageUrl"), "link": link})

        except:
            pass

    # Magalu
    magalu = get_magalu_direct(random.choice(PREMIUM_TERMOS))

    if magalu:
        i = random.choice(magalu)
        msg_tg, msg_wa = gerar_copy(
            i["nome"],
            i["preco"],
            i["vendas"],
            i["avaliacao"],
            i["comissao"],
            i["link"],
            "magalu"
        )

        total.append({"msg": msg_tg, "wa": msg_wa, "img": i.get("img"), "link": i["link"]})

    if not total:
        return

    await context.bot.send_message(CHAT_ID_DESTINO, "🚨 OFERTAS NOVAS")

    for t in total:

        zap = gerar_link_whatsapp(t["wa"])

        final = t["msg"] + f"\n📲 <a href='{zap}'>WhatsApp</a>"

        if t["img"]:
            await context.bot.send_photo(CHAT_ID_DESTINO, t["img"], caption=final, parse_mode="HTML")
        else:
            await context.bot.send_message(CHAT_ID_DESTINO, final, parse_mode="HTML")

        await asyncio.sleep(40)

# -------------------------
# START
# -------------------------
async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=5400, first=10)

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.run_polling()
        


