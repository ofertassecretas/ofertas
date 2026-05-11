import asyncio
import requests
import logging
import random
import time
import os
import html
import re

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
# HORÁRIO
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

    logging.info("Buscando ofertas ML SITE")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
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

        r = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        logging.info(f"Status SITE ML: {r.status_code}")

        html_site = r.text

        produtos = []

        padrao = re.findall(
            r'"polycard-(.*?)"',
            html_site
        )

        logging.info(f"Produtos brutos encontrados: {len(padrao)}")

        links = re.findall(
            r'https://www.mercadolivre.com.br/p/MLB[0-9]+',
            html_site
        )

        imagens = re.findall(
            r'https://http2.mlstatic.com/D_NQ_NP_[^"]+?jpg',
            html_site
        )

        titulos = re.findall(
            r'"title":"(.*?)"',
            html_site
        )

        precos = re.findall(
            r'"price":([0-9]+)',
            html_site
        )

        limite = min(
            len(links),
            len(imagens),
            len(titulos),
            len(precos),
            5
        )

        for i in range(limite):

            produtos.append({
                "nome": titulos[i],
                "preco": precos[i],
                "link": links[i],
                "img": imagens[i],
                "vendas": random.randint(100, 5000),
                "avaliacao": round(random.uniform(4.4, 5.0), 1)
            })

        logging.info(f"ML OK: {len(produtos)} produtos")

        return produtos

    except Exception as e:

        logging.error(f"ERRO ML: {e}")

        return []

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

        for item in ofertas:

            try:

                nome = html.escape(item["nome"])

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

                logging.info("Enviando produto ML")

                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=msg,
                    parse_mode="HTML"
                )

                await asyncio.sleep(40)

            except Exception as e:

                logging.error(f"Erro Telegram: {e}")

        logging.info("Loop finalizado")

    except Exception as e:

        logging.error(f"ERRO CRITICO: {e}")

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

# =========================
# MAIN
# =========================

if __name__ == "__main__":

    while True:

        try:

            app = (
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .build()
            )

            logging.info("INICIANDO BOT...")

            app.run_polling(
                allowed_updates=[]
            )

        except Exception as e:

            logging.error(f"BOT REINICIANDO: {e}")

            time.sleep(15)
