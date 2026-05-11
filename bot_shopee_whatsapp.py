import asyncio
import requests
import logging
import random
import os
import html
import re

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import quote
from bs4 import BeautifulSoup

from telegram.ext import ApplicationBuilder

print("VERSAO TESTE ML V3")

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
# HORÁRIO
# =========================

def dentro_do_horario():

    agora = datetime.now(FUSO_BR).time()

    return dt_time(5, 0) <= agora <= dt_time(21, 0)

# =========================
# COPY
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, link):

    aberturas = [
        "🚨 OFERTA ENCONTRADA",
        "🔥 PREÇO MUITO BOM",
        "💥 OLHA ESSE ACHADO",
        "👀 ENCONTREI ISSO AQUI",
        "⚠️ ESSA OFERTA PODE SUMIR"
    ]

    abertura = random.choice(aberturas)

    return f"""
<b>{abertura}</b>

🔥 <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao}
🛒 {vendas} vendas

<a href="{link}">🛒 COMPRAR AGORA</a>

━━━━━━━━━━━━━━━
📢 <b>Ofertas Secretas</b>
"""

# =========================
# WHATSAPP
# =========================

def gerar_link_whatsapp_from_html(msg_html, link):

    texto = re.sub('<[^<]+?>', '', msg_html)

    texto += f"\n\n🛒 {link}"

    return f"https://wa.me/?text={quote(texto)}"

# =========================
# MERCADO LIVRE
# =========================

def get_ml_offers():

    logging.info("Buscando ofertas ML")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    buscas = [
        "smartphone",
        "notebook",
        "fone bluetooth",
        "tv samsung",
        "air fryer",
        "cadeira gamer"
    ]

    termo = random.choice(buscas)

    logging.info(f"Busca escolhida: {termo}")

    try:

        url = f"https://lista.mercadolivre.com.br/{termo.replace(' ', '-')}"

        response = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        logging.info(f"Status ML: {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")

        produtos = []

        cards = soup.select(".ui-search-result")

        logging.info(f"Cards encontrados: {len(cards)}")

        for card in cards[:5]:

            try:

               titulo = card.select_one(".poly-component__title")

               preco = card.select_one(".andes-money-amount__fraction")

               link = card.select_one("a")

               imagem = card.select_one("img")

                if not titulo:
                    continue

                if not preco:
                    continue

                if not link:
                    continue

                if not imagem:
                    continue

                produtos.append({
                    "nome": titulo.get_text(strip=True),
                    "preco": preco.get_text(strip=True),
                    "link": link.get("href"),
                    "img": imagem.get("src"),
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1)
                })

            except Exception as e:

                logging.error(f"Erro produto: {e}")

        logging.info(f"ML OK: {len(produtos)} produtos")

        return produtos

    except Exception as e:

        logging.error(f"ERRO ML: {e}")

        return []

# =========================
# ENVIO
# =========================

async def send_ofertas(app):

    try:

        logging.info("Loop iniciado")

        if not dentro_do_horario():

            logging.info("Fora do horario")

            return

        ofertas = get_ml_offers()

        if len(ofertas) == 0:

            logging.warning("Nenhuma oferta encontrada")

            return

        await app.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS ML CHEGANDO..."
        )

        await asyncio.sleep(5)

        for item in ofertas:

            try:

                nome = html.escape(item["nome"])

                if not nome:
                    continue

                if not item["img"]:
                    continue

                if not item["link"]:
                    continue

                msg = gerar_copy(
                    nome,
                    item["preco"],
                    item["vendas"],
                    item["avaliacao"],
                    item["link"]
                )

                zap = gerar_link_whatsapp_from_html(
                    msg,
                    item["link"]
                )

                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'

                logging.info(f"Enviando produto: {nome}")

                await app.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=msg,
                    parse_mode="HTML"
                )

                await asyncio.sleep(40)

            except Exception as e:

                logging.error(f"Erro Telegram produto: {e}")

        logging.info("Loop finalizado")

    except Exception as e:

        logging.error(f"ERRO CRITICO: {e}")

# =========================
# LOOP MANUAL
# =========================

async def loop_ofertas(app):

    while True:

        try:

            await send_ofertas(app)

        except Exception as e:

            logging.error(f"ERRO LOOP: {e}")

        await asyncio.sleep(CHECK_INTERVAL)

# =========================
# MAIN
# =========================

async def main():

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    logging.info("🤖 BOT ML RODANDO")

    asyncio.create_task(loop_ofertas(app))

    await app.initialize()

    await app.start()

    await app.updater.start_polling(
        drop_pending_updates=True
    )

    while True:

        await asyncio.sleep(60)

# =========================
# START
# =========================

if __name__ == "__main__":

    asyncio.run(main())
