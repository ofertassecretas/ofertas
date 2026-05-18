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

print("VERSÃO FINAL HIBRIDA ESTAVEL V30 - MAGALU GRAPHQL FIX REAL")

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
MAGALU_STORE_ID = "magazineshopandreonline"

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

PREMIUM_TERMOS = [
    "Smartphone", "Geladeira", "Smart TV", "Airfryer",
    "Notebook", "Lavadora", "Fogão", "Microondas", "Monitor Gamer"
]

MOTOS_MODELOS = ["Titan 160","Fazer 250","XRE 300","Biz 125","Twister 250"]
MOTOS_PECAS = ["Kit Relação","Pneu","Capacete","Jaqueta","Farol"]


# =========================
# UTIL
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)


def gerar_link_whatsapp(msg):
    return "https://wa.me/?text=" + quote(msg)


def gerar_link_magalu(produto_url):
    return (
        f"https://magazineluiza.onelink.me/"
        f"{MAGALU_ONELINK_ID}/{MAGALU_STORE_ID}"
        f"?af_dp={quote(produto_url)}"
    )


# =========================
# SHOPEE (NÃO MEXI)
# =========================

def get_shopee_offers():

    logging.info("Buscando Shopee...")

    timestamp = int(time.time())

    query_body = """
    query {
        productOfferV2(sortType: 2, limit: 10) {
            nodes {
                productName,
                priceMin,
                commissionRate,
                sales,
                ratingStar,
                productLink,
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
        "Authorization": (
            f"SHA256 Credential={SHOPEE_APP_ID}, "
            f"Timestamp={timestamp}, "
            f"Signature={signature}"
        )
    }

    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)

        nodes = r.json().get("data", {}).get("productOfferV2", {}).get("nodes", [])

        return nodes

    except Exception as e:
        logging.warning(f"Shopee falhou: {e}")
        return []


# =========================
# 🔵 MAGALU NOVO (GRAPHQL REAL)
# =========================

def get_magalu_direct(termo):

    logging.info(f"Magalu GraphQL busca: {termo}")

    url = "https://federation.magazineluiza.com.br/graphql"

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://www.magazinevoce.com.br",
        "Referer": "https://www.magazinevoce.com.br/",
        "User-Agent": "Mozilla/5.0"
    }

    payload = {
        "operationName": "showcaseQuery",
        "variables": {
            "includePagination": False,
            "toggleWishlist": True,
            "withButtonAction": False,
            "isSourceProductAds": False,
            "customerId": f"temp_{random.randint(1000,9999)}",
            "filters": [],
            "pageId": "uOGIQZGXJl",
            "partnerId": "3440",
            "placeId": "lbezB0Wslz",
            "storeId": MAGALU_STORE_ID
        },
        "query": """
        query {
          recommendation(
            recommendationRequest: {
              customerId: $customerId,
              pageId: $pageId,
              placeId: $placeId,
              metadata: {
                partnerId: $partnerId,
                loyaltyParams: {
                  storeId: $storeId
                }
              },
              filters: $filters
            }
          ) {
            dynamic {
              products {
                id
                title
                image
                url
                price {
                  price
                  bestPrice
                }
                rating {
                  score
                  count
                }
              }
            }
          }
        }
        """
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=20)

        data = r.json()

        products = (
            data.get("data", {})
            .get("recommendation", {})
            .get("dynamic", {})
            .get("products", [])
        )

        res = []

        for p in products:

            try:
                nome = p.get("title")
                img = p.get("image", "")
                link_raw = p.get("url")

                if not nome or not link_raw:
                    continue

                if not link_raw.startswith("http"):
                    link_raw = "https://www.magazineluiza.com.br" + link_raw

                link = gerar_link_magalu(link_raw)

                price = p.get("price", {}).get("bestPrice") or p.get("price", {}).get("price")

                res.append({
                    "id": hashlib.md5(link.encode()).hexdigest(),
                    "nome": nome,
                    "preco": f"{float(price):.2f}" if price else "0.00",
                    "link": link,
                    "img": img,
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.5, 5.0), 1),
                    "origem": "magalu",
                    "comissao": random.randint(3, 8)
                })

            except:
                continue

        logging.info(f"Magalu GraphQL OK: {len(res)}")
        return res

    except Exception as e:
        logging.warning(f"Erro Magalu GraphQL: {e}")
        return []


# =========================
# GERADOR DE COPY (NÃO MEXIDO)
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):

    prefixos = {
        "shopee": "🟠 SHOPEE",
        "ml": "🟡 MERCADO LIVRE",
        "magalu": "🔵 MAGALU"
    }

    prefixo = prefixos.get(origem, "🔥 OFERTA")

    abertura = random.choice([
        "🚨 Isso aqui não é comum aparecer assim",
        "🔥 Isso aqui tá chamando atenção",
        "👀 Achei isso aqui e fui conferir…"
    ])

    msg_tg = (
        f"<b>{prefixo} | {abertura}</b>\n\n"
        f"🔥 <b>{nome}</b>\n\n"
        f"💰 <b>R$ {preco}</b>\n"
        f"⭐ {avaliacao} | 🛒 {vendas} vendas\n"
        f"💸 Comissão: <b>{comissao}%</b>\n\n"
        f"⚠️ Pode subir de preço\n\n"
        f"<a href=\"{link}\">🛒 COMPRAR AGORA</a>\n\n"
        f"<a href=\"{gerar_link_whatsapp(nome + ' ' + link)}\">📲 WhatsApp</a>\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📢 Ofertas Secretas"
    )

    return msg_tg, msg_tg


# =========================
# LOOP PRINCIPAL
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    total = []

    # SHOPEE (igual)
    shopee = get_shopee_offers()

    for i in shopee[:2]:
        try:
            link = i["productLink"]

            if "af_siteid" not in link:
                link += f"?af_siteid={AFILIADO_ID}"

            msg, _ = gerar_copy(
                i["productName"],
                f"{float(i['priceMin']):.2f}",
                i.get("sales", 100),
                i.get("ratingStar", 4.5),
                round(float(i.get("commissionRate", 0)) * 100, 2),
                link,
                "shopee"
            )

            total.append(msg)

        except:
            continue

    # MAGALU NOVO
    magalu = get_magalu_direct(random.choice(PREMIUM_TERMOS))

    if magalu:
        i = random.choice(magalu)

        msg, _ = gerar_copy(
            i["nome"],
            i["preco"],
            i["vendas"],
            i["avaliacao"],
            i["comissao"],
            i["link"],
            "magalu"
        )

        total.append(msg)

    # ENVIO
    for m in total:
        await context.bot.send_message(
            chat_id=-1003848415150,
            text=m,
            parse_mode="HTML"
        )

        await asyncio.sleep(45)


# =========================
# START
# =========================

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=5400, first=10)
    logging.info("BOT V30 ATIVO")


if __name__ == "__main__":

    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.run_polling()

        except Exception as e:
            logging.error(e)
            time.sleep(10)
        


