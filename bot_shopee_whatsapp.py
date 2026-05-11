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

print("VERSAO TESTE ML V1")

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
        "🚨 Oferta encontrada agora",
        "🔥 Isso aqui tá chamando atenção",
        "👀 Achei isso aqui no ML",
        "💥 Preço interessante aparecendo",
        "🛑 Olha isso aqui",
        "⚠️ Pode acabar rápido",
        "🚀 Produto rodando forte",
        "📉 Esse preço não costuma durar"
    ]

    gatilhos = [
        "Preço abaixo da média",
        "Produto muito procurado",
        "Boa oportunidade",
        "Custo-benefício forte",
        "Produto com bastante saída",
        "Quem compra recomenda"
    ]

    abertura = random.choice(
        [a for a in aberturas if a not in usadas_abertura] or aberturas
    )

    usadas_abertura.add(abertura)

    gatilho = random.choice(gatilhos)

    return f"""
<b>{abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas

⚠️ Pode subir de preço

<a href="{link}">🛒 VER PRODUTO</a>
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

    buscas = [
        "notebook",
        "smartphone",
        "tv",
        "fone bluetooth",
        "promoção",
        "ofertas"
    ]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0 Safari/537.36"
        )
    }

    produtos = []

    try:

        termo = random.choice(buscas)

        logging.info(f"Busca escolhida: {termo}")

        url = f"https://lista.mercadolivre.com.br/{termo}"

        r = requests.get(
            url,
            headers=headers,
            timeout=30
        )

        logging.info(f"Status SITE ML: {r.status_code}")

        if r.status_code != 200:
            return []

        html_site = r.text

        blocos = re.findall(
            r'<a href="(https://[^"]+)" class="poly-component__title".*?>(.*?)</a>.*?src="(https://[^"]+)"',
            html_site,
            re.S
        )

        logging.info(f"Produtos encontrados ML: {len(blocos)}")

        for link, nome, img in blocos[:10]:

            nome = re.sub('<.*?>', '', nome)

            preco_match = re.search(
                rf'{re.escape(link)}.*?andes-money-amount__fraction">([^<]+)',
                html_site,
                re.S
            )

            preco = preco_match.group(1) if preco_match else "0"

            produtos.append({
                "nome": nome.strip(),
                "preco": float(str(preco).replace(".", "").replace(",", ".")),
                "link": link,
                "img": img,
                "vendas": random.randint(100, 5000),
                "avaliacao": round(random.uniform(4.4, 5.0), 1),
                "origem": "ml"
            })

    except Exception as e:

        logging.error(f"ERRO ML SITE: {e}")

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

        usadas_abertura.clear()

        ofertas = get_ml_offers()

        if len(ofertas) == 0:

            logging.warning("Nenhuma oferta ML encontrada")

            return

        selecionadas = ofertas[:5]

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS ML CHEGANDO..."
        )

        await asyncio.sleep(5)

        for item in selecionadas:

            try:

                nome = html.escape(item["nome"])

                preco = f"{float(item['preco']):.2f}"

                rating = item["avaliacao"]

                vendas = f"{item['vendas']:,}".replace(",", ".")

                link = item["link"]

                msg = gerar_copy(
                    nome,
                    preco,
                    vendas,
                    rating,
                    link
                )

                zap = gerar_link_whatsapp_from_html(
                    msg,
                    link
                )

                msg += (
                    f'\n📲 <a href="{zap}">'
                    'Compartilhar no WhatsApp</a>'
                )

                msg += (
                    "\n━━━━━━━━━━━━━━━"
                    "\n📢 <b>Ofertas Mercado Livre</b>"
                )

                logging.info("Enviando produto ML")

                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=msg,
                    parse_mode="HTML"
                )

                await asyncio.sleep(40)

            except Exception as e:

                logging.error(f"Erro envio ML: {e}")

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
