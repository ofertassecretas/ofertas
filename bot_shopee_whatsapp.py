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
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

# =========================
# CONFIGURAÇÕES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400  # 1h30
MAX_PRODUTOS_POR_RODADA = 3

logging.basicConfig(level=logging.INFO)

produtos_enviados = set()
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# =========================
# HORÁRIO
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    inicio = dt_time(6, 30)
    fim = dt_time(21, 0)
    return inicio <= agora <= fim

# =========================
# COPYS AGRESSIVAS
# =========================

COPYS = [

"""🚨 PARA TUDO.

Esse <b>{nome}</b> está por <b>R$ {preco}</b>.

{vendas} vendas | {avaliacao} ⭐

Isso aqui NÃO é preço normal.
Se você estava esperando cair… caiu.

👀 {vendo} pessoas estão vendo agora.

👇 Pega antes que volte:
<a href="{link}">GARANTIR AGORA</a>
""",

"""🔥 ISSO AQUI VAI SUBIR.

<b>{nome}</b> por <b>R$ {preco}</b>.

Produto validado ({vendas} vendas | {avaliacao} ⭐).

Esse valor não faz sentido ficar muito tempo.

⚠️ Pode acabar ainda hoje.

👇 Corre:
<a href="{link}">APROVEITAR ENQUANTO DÁ</a>
""",

"""💣 PREÇO FORA DO PADRÃO.

<b>{nome}</b> → <b>R$ {preco}</b>

{vendas} pessoas já compraram.
Avaliação {avaliacao} ⭐.

Quando entra nesse nível, gira rápido.

👀 {vendo} pessoas olhando agora.

👇 Se vacilar, perde:
<a href="{link}">VER AGORA</a>
""",

"""⚡ NÃO IGNORA ISSO.

<b>{nome}</b> por <b>R$ {preco}</b>.

Com {vendas} vendas e {avaliacao} ⭐,
não é produto encalhado.

Está barato demais pro que entrega.

👇 Enquanto ainda está nesse valor:
<a href="{link}">GARANTIR</a>
""",

"""🚨 ALERTA DE OPORTUNIDADE.

<b>{nome}</b> saindo por <b>R$ {preco}</b>.

{vendas} vendas comprovando.
Avaliação {avaliacao} ⭐.

Esse tipo de preço corrige rápido.

👀 Alta procura agora.

👇 Antes que ajuste:
<a href="{link}">CONFERIR PREÇO</a>
"""
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
                priceMin
                commissionRate
                sales
                ratingStar
                productLink
                imageUrl
                itemId
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
        resp = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)

        if resp.status_code == 200:
            data = resp.json()
            produtos = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
            random.shuffle(produtos)
            return produtos

        return []

    except Exception as e:
        logging.error(f"Erro Shopee: {e}")
        return []

# =========================
# ENVIO TELEGRAM
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
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

        try:
            preco = float(item["priceMin"])
        except:
            continue

        nome_produto = html.escape(item["productName"])
        vendas = item.get("sales", 0)
        avaliacao = item.get("ratingStar", "0")
        imagem_url = item.get("imageUrl")

        vendo_agora = random.randint(12, 47)

        copy_escolhida = random.choice(COPYS)

        mensagem = copy_escolhida.format(
            nome=nome_produto,
            preco=f"{preco:.2f}",
            vendas=vendas,
            avaliacao=avaliacao,
            vendo=vendo_agora,
            link=link_final
        )

        mensagem += "\n\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

        try:
            if imagem_url:
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=imagem_url,
                    caption=mensagem,
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=CHAT_ID_DESTINO,
                    text=mensagem,
                    parse_mode="HTML",
                    disable_web_page_preview=True
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



