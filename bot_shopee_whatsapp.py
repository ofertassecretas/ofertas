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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://www.mercadolivre.com.br/",
        "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Upgrade-Insecure-Requests": "1"
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
        response = requests.get(url, headers=headers, timeout=25)
        logging.info(f"Status ML: {response.status_code}")

        if response.status_code != 200:
            logging.error("Página com erro ou bloqueada")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        produtos = []

        # 🟡 TODOS OS SELETORES POSSÍVEIS DO MERCADO LIVRE (versões antigas e novas)
        seletores_cards = [
            "li.ui-search-layout__item",
            "div.ui-search-result",
            "div.poly-card",
            "div.andes-card",
            "section.ui-search-card"
        ]

        cards = []
        for sel in seletores_cards:
            cards = soup.select(sel)
            if cards:
                logging.info(f"Usando seletor: {sel} | Encontrados: {len(cards)}")
                break

        if not cards:
            logging.warning("Nenhum seletor encontrou produtos — estrutura mudou completamente")
            return []

        # Pegamos só os 5 primeiros
        for card in cards[:5]:
            try:
                # 🔹 TÍTULO
                titulo = card.select_one("h2") or \
                         card.select_one(".poly-component__title") or \
                         card.select_one(".ui-search-item__title")
                if not titulo:
                    continue
                nome_prod = titulo.get_text(strip=True)
                if not nome_prod:
                    continue

                # 🔹 PREÇO
                preco = card.select_one(".andes-money-amount__fraction") or \
                        card.select_one(".price-tag-fraction") or \
                        card.select_one(".ui-search-price__part--medium")
                if not preco:
                    continue
                preco_prod = preco.get_text(strip=True)
                if not preco_prod:
                    continue

                # 🔹 LINK
                link_tag = card.select_one("a")
                if not link_tag or not link_tag.get("href"):
                    continue
                link_prod = link_tag["href"]
                if link_prod.startswith("/"):
                    link_prod = "https://lista.mercadolivre.com.br" + link_prod

                # 🔹 IMAGEM
                imagem = card.select_one("img")
                if not imagem:
                    continue
                img_prod = imagem.get("src") or imagem.get("data-src") or ""
                if not img_prod or img_prod.startswith("data:image"):
                    continue

                # Se passou por tudo, adiciona
                produtos.append({
                    "nome": nome_prod,
                    "preco": preco_prod,
                    "link": link_prod,
                    "img": img_prod,
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1)
                })
                logging.info(f"✅ Produto capturado: {nome_prod} - R$ {preco_prod}")

            except Exception as e:
                logging.error(f"Erro ao extrair dados do produto: {e}")

        logging.info(f"ML OK: {len(produtos)} produtos válidos")
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
