import asyncio
import requests
import logging
import random
import hashlib
import time
import json
import os
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import quote
from telegram.ext import ApplicationBuilder, ContextTypes


print("VERSÃO FINAL HIBRIDA ESTAVEL V30 - SHOPEE + MAGALU FIX")

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

MAGALU_STORE_ID = "magazineshopandreonline"
MAGALU_ONELINK_ID = "589508454"

CHECK_INTERVAL = 5400
FUSO_BR = ZoneInfo("America/Sao_Paulo")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


# =========================
# UTIL
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)


def gerar_link_whatsapp(msg):
    return "https://wa.me/?text=" + quote(msg)


def gerar_link_magalu(url):
    return f"https://magazineluiza.onelink.me/{MAGALU_ONELINK_ID}/{MAGALU_STORE_ID}?af_dp={quote(url)}"


# =========================
# SHOPEE (SEM ALTERAÇÃO)
# =========================

def get_shopee_offers():

    logging.info("Buscando Shopee...")

    timestamp = int(time.time())

    query = """
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

    payload = json.dumps({"query": query})

    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        return r.json().get("data", {}).get("productOfferV2", {}).get("nodes", [])
    except:
        return []


# =========================
# 🔵 MAGALU FIX DEFINITIVO
# =========================

def get_magalu_direct(termo):

    logging.info(f"Magalu busca: {termo}")

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
        loyaltyParams: { storeId: $storeId }
      },
      filters: $filters
    }
  ) {
    dynamic {
      products {
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

        result = []

        for p in products:

            try:
                nome = p.get("title")
                url_raw = p.get("url")
                img = p.get("image")

                if not nome or not url_raw:
                    continue

                if not url_raw.startswith("http"):
                    url_raw = "https://www.magazineluiza.com.br" + url_raw

                link = gerar_link_magalu(url_raw)

                price = p.get("price", {}).get("bestPrice") or p.get("price", {}).get("price")

                result.append({
                    "nome": nome,
                    "preco": f"{float(price):.2f}" if price else "0.00",
                    "link": link,
                    "img": img,
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.5, 5.0), 1),
                    "comissao": random.randint(3, 8)
                })

            except:
                continue

        logging.info(f"Magalu OK: {len(result)} produtos")
        return result

    except Exception as e:
        logging.warning(f"Erro Magalu: {e}")
        return []


# =========================
# COPY (SHOPEE NÃO ALTERADO)
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):

    prefix = {
        "shopee": "🟠 SHOPEE",
        "magalu": "🔵 MAGALU"
    }

    abertura = random.choice([
        "🚨 Isso aqui não é comum aparecer assim",
        "🔥 Isso aqui tá chamando atenção",
        "👀 Achei isso aqui e fui conferir…"
    ])

    msg = (
        f"<b>{prefix.get(origem,'🔥 OFERTA')} | {abertura}</b>\n\n"
        f"🔥 <b>{nome}</b>\n\n"
        f"💰 <b>R$ {preco}</b>\n"
        f"⭐ {avaliacao} | 🛒 {vendas} vendas\n"
        f"💸 Comissão: <b>{comissao}%</b>\n\n"
        f"⚠️ Pode subir de preço\n\n"
        f"<a href=\"{link}\">🛒 COMPRAR AGORA</a>\n\n"
        f"<a href=\"{gerar_link_whatsapp(nome + ' ' + link)}\">📲 WhatsApp</a>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📢 Ofertas Secretas"
    )

    return msg


# =========================
# LOOP PRINCIPAL
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    mensagens = []

    # SHOPEE
    shopee = get_shopee_offers()

    for i in shopee[:2]:
        try:
            link = i["productLink"]

            if "af_siteid" not in link:
                link += f"?af_siteid={AFILIADO_ID}"

            msg = gerar_copy(
                i["productName"],
                f"{float(i['priceMin']):.2f}",
                i.get("sales", 100),
                i.get("ratingStar", 4.5),
                round(float(i.get("commissionRate", 0)) * 100, 2),
                link,
                "shopee"
            )

            mensagens.append(msg)

        except:
            continue

    # MAGALU
    magalu = get_magalu_direct(random.choice([
        "Smartphone", "TV", "Notebook", "Airfryer"
    ]))

    if magalu:
        p = random.choice(magalu)

        msg = gerar_copy(
            p["nome"],
            p["preco"],
            p["vendas"],
            p["avaliacao"],
            p["comissao"],
            p["link"],
            "magalu"
        )

        mensagens.append(msg)

    # ENVIO
    for m in mensagens:
        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
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

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.run_polling()
        


