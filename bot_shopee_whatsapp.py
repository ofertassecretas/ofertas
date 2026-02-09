import asyncio
import requests
import logging
import random
import hashlib
import time
import json
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from telegram.ext import ApplicationBuilder, ContextTypes

# =========================
# CONFIGURAÇÕES
# =========================
TELEGRAM_TOKEN = "7591538191:AAH6PsQwQH2Xh9Q-2xH3Y5Q3oMxAxpBmES0"
CHAT_ID_DESTINO = "7311246066"

SHOPEE_APP_ID = "18349740277"
SHOPEE_PASSWORD = "6VWUZA5SYDQ6Q3XXIHBSTILAY2SNNNXV"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 3600  # 1 hora
MAX_PRODUTOS_POR_RODADA = 4

logging.basicConfig(level=logging.INFO)
produtos_enviados = set()


# =========================
# CTAs TURBINADAS
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
# FUNÇÕES DE APOIO
# =========================

def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    nova_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=nova_query))


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
    signature = hashlib.sha256(base_str.encode('utf-8')).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        logging.info("Conectando à Shopee...")
        resp = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)

        if resp.status_code == 200:
            data = resp.json()
            if "errors" in data:
                logging.error(f"Erro da API: {data['errors']}")
                return []
            return data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
        else:
            logging.error(f"Erro HTTP {resp.status_code}")
            return []

    except Exception as e:
        logging.error(f"Erro de conexão: {e}")
        return []


# =========================
# ENVIO PARA TELEGRAM
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):
    logging.info("Buscando novas ofertas...")
    ofertas = get_shopee_offers()

    if not ofertas:
        logging.info("Nenhuma oferta encontrada.")
        return

    enviados_nesta_rodada = 0

    for item in ofertas:

        if enviados_nesta_rodada >= MAX_PRODUTOS_POR_RODADA:
            break

        try:
            link_final = aplicar_id_afiliado(item["productLink"])

            if link_final in produtos_enviados:
                continue

            preco = float(item["price"])

            mensagem = (
                f"{random.choice(TITULOS)}\n\n"
                f"📦 *{item['productName']}*\n"
                f"💰 *R$ {preco:.2f}*\n\n"
                f"{random.choice(CTAS)}\n\n"
                f"🛒 [CLIQUE AQUI PARA COMPRAR]({link_final})\n\n"
                f"━━━━━━━━━━━━━━━\n"
                f"📢 *Ofertas Secretas*"
            )

            if item.get("imageUrl"):
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["imageUrl"],
                    caption=mensagem,
                    parse_mode="Markdown"
                )
            else:
                await context.bot.send_message(
                    chat_id=CHAT_ID_DESTINO,
                    text=mensagem,
                    parse_mode="Markdown"
                )

            produtos_enviados.add(link_final)
            enviados_nesta_rodada += 1
            await asyncio.sleep(5)

        except Exception as e:
            logging.error(f"Erro ao enviar oferta: {e}")


# =========================
# INICIALIZAÇÃO
# =========================

async def post_init(app):
    app.job_queue.run_repeating(
        send_shopee_offers,
        interval=CHECK_INTERVAL,
        first=5
    )
    logging.info("🤖 Bot Shopee Online!")


if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.run_polling()