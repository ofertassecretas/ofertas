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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "pt-BR,pt;q=0.9",
        "Referer": "https://lista.mercadolivre.com.br/",
        "Origin": "https://lista.mercadolivre.com.br",
        "Sec-Ch-Ua": '"Not.A/Brand";v="8", "Chromium";v="114"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-site"
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
        # ✅ USAMOS A API INTERNA DO MERCADO LIVRE (não HTML)
        url_api = f"https://api.mercadolibre.com/sites/MLB/search?q={quote(termo)}&limit=10&offset=0"

        import time
        time.sleep(random.uniform(1, 2))

        response = requests.get(url_api, headers=headers, timeout=30)
        logging.info(f"Status ML API: {response.status_code}")

        if response.status_code != 200:
            logging.error("API indisponível ou bloqueada")
            return []

        dados = response.json()
        produtos = []

        if "results" not in dados or len(dados["results"]) == 0:
            logging.warning("Nenhum resultado retornado pela API")
            return []

        logging.info(f"✅ Itens recebidos da API: {len(dados['results'])}")

        # ✅ Extrai dados DIRETAMENTE do JSON (sem depender de classes)
        for item in dados["results"][:5]:
            try:
                nome = item.get("title", "").strip()
                if not nome or len(nome) < 5:
                    continue

                preco = str(item.get("price", "0")).replace(".", ",")
                link = item.get("permalink", "")
                imagem = item.get("thumbnail", "").replace("I.jpg", "O.jpg") # imagem maior

                if not link or not imagem:
                    continue

                produtos.append({
                    "nome": nome,
                    "preco": preco,
                    "link": link,
                    "img": imagem,
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1)
                })
                logging.info(f"📦 Produto: {nome} | R$ {preco}")

            except Exception as e:
                logging.warning(f"⚠️ Erro ao processar item: {e}")

        logging.info(f"🏁 Final: {len(produtos)} produtos prontos")
        return produtos

    except Exception as e:
        logging.error(f"💥 ERRO GERAL ML: {e}")
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

                zap = gerar_link_whatsapp_from_html(msg, item["link"])
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
