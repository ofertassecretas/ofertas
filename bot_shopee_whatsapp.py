import asyncio
import requests
import logging
import random
import time
import os
import html
import re

from bs4 import BeautifulSoup

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import quote

from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO TESTE ML V2")

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

CHAT_ID_DESTINO = -1003848415150

CHECK_INTERVAL = 5400

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

# =========================
# HORARIO
# =========================

def dentro_do_horario():

    agora = datetime.now(FUSO_BR).time()

    return dt_time(5, 0) <= agora <= dt_time(21, 0)

# =========================
# COPY
# =========================

usadas_abertura = set()

def gerar_copy(nome, preco, vendas, avaliacao, link):

    aberturas = [
        "🚨 OFERTA ENCONTRADA",
        "🔥 ACHADINHO DO MOMENTO",
        "💥 PREÇO MUITO FORTE",
        "⚠️ ISSO AQUI VAI SUMIR",
        "👀 OLHA ESSE PREÇO",
    ]

    abertura = random.choice(aberturas)

    return f"""
<b>{abertura}</b>

🔥 <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao}
🛒 {vendas} vendas

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
# ML
# =========================

def get_ml_offers():

    logging.info("Buscando ofertas ML SITE")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        )
    }

    buscas = [
        "notebook",
        "smartphone",
        "fone bluetooth",
        "tv samsung",
        "promoção"
    ]

    produtos = []

    try:

        termo = random.choice(buscas)

        logging.info(f"Busca escolhida: {termo}")

        url = f"https://lista.mercadolivre.com.br/{termo}"

        r = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        logging.info(f"Status SITE ML: {r.status_code}")

        soup = BeautifulSoup(r.text, "html.parser")

        cards = soup.select("li.ui-search-layout__item")

        logging.info(f"Cards encontrados: {len(cards)}")

        for card in cards[:10]:

            try:

                titulo = card.select_one("h3")

                preco = card.select_one(".andes-money-amount__fraction")

                link = card.select_one("a")

                imagem = card.select_one("img")

                if not titulo or not preco or not link:
                    continue

                nome = titulo.get_text(strip=True)

                preco_texto = preco.get_text(strip=True)

                preco_float = float(
                    preco_texto.replace(".", "")
                )

                link_produto = link.get("href")

                img = None

                if imagem:

                    img = imagem.get("src")

                    if not img:
                        img = imagem.get("data-src")

                if not img:
                    continue

                produtos.append({
                    "nome": nome,
                    "preco": preco_float,
                    "link": link_produto,
                    "img": img,
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1),
                })

            except Exception as e:

                logging.error(f"Erro item ML: {e}")

    except Exception as e:

        logging.error(f"Erro ML: {e}")

    logging.info(f"ML OK: {len(produtos)} produtos")

    return produtos

# =========================
# ENVIO
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    try:

        logging.info("Loop iniciado")

        if not dentro_do_horario():

            logging.info("Fora do horario")

            return

        ofertas = get_ml_offers()

        if len(ofertas) == 0:

            logging.warning("Nenhuma oferta ML encontrada")

            return

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS ML CHEGANDO..."
        )

        await asyncio.sleep(5)

        for item in ofertas[:5]:

            try:

                msg = gerar_copy(
                    item["nome"],
                    f'{item["preco"]:.2f}',
                    item["vendas"],
                    item["avaliacao"],
                    item["link"]
                )

                zap = gerar_link_whatsapp_from_html(
                    msg,
                    item["link"]
                )

                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'

                logging.info("Enviando produto ML")

                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=msg,
                    parse_mode="HTML"
                )

                await asyncio.sleep(25)

            except Exception as e:

                logging.error(f"Erro Telegram: {e}")

    except Exception as e:

        logging.error(f"ERRO LOOP: {e}")

# =========================
# KEEP ALIVE
# =========================

async def keep_alive():

    while True:

        logging.info("BOT ML VIVO")

        await asyncio.sleep(300)

# =========================
# START
# =========================

async def post_init(app):

    app.job_queue.run_repeating(
        send_ofertas,
        interval=CHECK_INTERVAL,
        first=10
    )

    asyncio.create_task(keep_alive())

    logging.info("🤖 BOT ML RODANDO")

if __name__ == "__main__":

    while True:

        try:

            app = (
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .build()
            )

            app.run_polling()

        except Exception as e:

            logging.error(f"BOT REINICIANDO: {e}")

            time.sleep(15)
