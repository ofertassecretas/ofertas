import asyncio
import requests
import logging
import random
import hashlib
import time
import json
import os
import html

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo

from urllib.parse import (
    urlparse, parse_qs, urlencode, urlunparse, quote
)

from telegram.ext import ApplicationBuilder, ContextTypes


# =========================
# CONFIGURAÇÕES
# =========================

CHAT_ID_DESTINO = int(os.getenv("CHAT_ID_DESTINO"))
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1005280967179

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400  # 1h30
MAX_PRODUTOS_POR_RODADA = 3

logging.basicConfig(level=logging.INFO)
produtos_enviados = set()


# =========================
# 🇧🇷 FUSO HORÁRIO BRASIL
# =========================

FUSO_BR = ZoneInfo("America/Sao_Paulo")


def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    inicio = dt_time(6, 30)
    fim = dt_time(21, 0)
    return inicio <= agora <= fim


# =========================
# TEXTOS
# =========================

CTAS = [
    "🔥 Corre antes que acabe!",
    "⚠️ Últimas unidades!",
    "🛒 Oferta exclusiva do grupo!",
    "⏰ Aproveita agora!",
    "💥 Desconto absurdo, só hoje!"
]

TITULOS = [
    "🔥 OFERTA SHOPEE",
    "🚨 PROMOÇÃO IMPERDÍVEL",
    "💥 SUPER DESCONTO HOJE",
    "🛒 ACHADINHO DA SHOPEE",
    "⚡ PREÇO DESPENCOU",
    "😱 BARATO DEMAIS PRA IGNORAR",
    "🎯 OFERTA RELÂMPAGO",
    "💣 PROMOÇÃO BOMBÁSTICA",
    "📉 MENOR PREÇO DO DIA"
]


# =========================
# FUNÇÕES AUXILIARES
# =========================

def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    nova_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=nova_query))


def gerar_link_whatsapp(texto):
    return f"https://wa.me/?text={quote(texto)}"


# =========================
# SHOPEE API
# =========================

def get_shopee_offers():
    timestamp = int(time.time())

    query_body = """
    query {
        productOfferV2 {
            nodes {
                productName
                price
                productLink
                imageUrl
            }
        }
    }
    """

    payload = json.dumps({"query": query_body})

    base_str = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base_str.encode("utf-8")).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        logging.info("🔎 Buscando ofertas na Shopee...")
        resp = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)

        if resp.status_code == 200:
            data = resp.json()
            return data.get("data", {}).get("productOfferV2", {}).get("nodes", [])

        return []

    except Exception as e:
        logging.error(f"Erro Shopee: {e}")
        return []


# =========================
# ENVIO TELEGRAM
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        logging.info("🌙 Fora do horário. Bot pausado.")
        return

    ofertas = get_shopee_offers()

    if not ofertas:
        return

    enviados = 0

    for item in ofertas:

        if enviados >= MAX_PRODUTOS_POR_RODADA:
            break

        link_final = aplicar_id_afiliado(item["productLink"])

        if link_final in produtos_enviados:
            continue

        preco = float(item["price"])
        nome_produto = html.escape(item["productName"])

        texto_whats = (
            f"🔥 OFERTA SHOPEE\n\n"
            f"📦 {item['productName']}\n"
            f"💰 R$ {preco:.2f}\n\n"
            f"{link_final}"
        )

        link_whats = gerar_link_whatsapp(texto_whats)

        mensagem = (
            f"{random.choice(TITULOS)}\n\n"
            f"📦 <b>{nome_produto}</b>\n"
            f"💰 <b>R$ {preco:.2f}</b>\n\n"
            f"{random.choice(CTAS)}\n\n"
            f"🛒 <a href=\"{link_final}\">CLIQUE AQUI PARA COMPRAR</a>\n\n"
            f"📲 <a href=\"{link_whats}\">Enviar no WhatsApp</a>\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📢 <b>Ofertas Secretas</b>"
        )

        try:
            if item.get("imageUrl"):
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["imageUrl"],
                    caption=mensagem,
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=CHAT_ID_DESTINO,
                    text=mensagem,
                    parse_mode="HTML"
                )

            produtos_enviados.add(link_final)
            enviados += 1

            await asyncio.sleep(random.randint(5, 12))

        except Exception as e:
            logging.error(f"Erro envio: {e}")


# =========================
# INICIALIZAÇÃO
# =========================

async def post_init(app):
    app.job_queue.run_repeating(
        send_shopee_offers,
        interval=CHECK_INTERVAL,
        first=10
    )

    logging.info("🤖 Bot Shopee Online!")


if __name__ == "__main__":

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.run_polling(
        poll_interval=60,
        timeout=60,
        drop_pending_updates=True
    )


