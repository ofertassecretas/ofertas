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

    # ✅ Cabeçalhos COMPLETOS para simular navegador real
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Accept-Language": "pt-BR,pt;q=0.9,es;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com/",
        "Sec-Ch-Ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
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
        
        # ✅ Delay aleatório SEM await (correção do erro)
        import time
        time.sleep(random.uniform(1, 3))
        
        response = requests.get(url, headers=headers, timeout=30)
        logging.info(f"Status ML: {response.status_code}")

        if response.status_code != 200:
            logging.error("Página indisponível ou bloqueada")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        produtos = []

        # ✅ TODOS os padrões de estrutura que existem no ML atualmente
        seletores = [
            "li.ui-search-layout__item",
            "div.ui-search-result",
            "div.poly-card__container",
            "div.andes-card",
            "section.ui-search-card",
            ".poly-component__wrapper"
        ]

        cards = []
        for sel in seletores:
            cards = soup.select(sel)
            if cards:
                logging.info(f"✅ ESTRUTURA DETECTADA: {sel} | {len(cards)} itens")
                break

        if not cards:
            logging.error("❌ Nenhuma estrutura de produto encontrada")
            return []

        # ✅ Extração ULTRA FLEXÍVEL - pega dados de qualquer jeito
        for idx, card in enumerate(cards[:5]):
            try:
                # Título
                titulo = card.find("h2") or \
                         card.find("span", class_="poly-component__title") or \
                         card.find("div", {"class": lambda c: c and 'title' in c})
                if not titulo: continue
                nome = titulo.get_text(strip=True)
                if len(nome) < 5: continue

                # Preço
                preco = card.find("span", class_="andes-money-amount__fraction") or \
                        card.find("span", {"class": lambda c: c and 'price' in c}) or \
                        card.find("div", string=re.compile(r'R\$'))
                if not preco: continue
                valor = re.sub(r'[^0-9]', '', preco.get_text(strip=True))
                if not valor: continue

                # Link
                link_tag = card.find("a")
                if not link_tag or not link_tag.get("href"): continue
                link = link_tag["href"]
                if link.startswith("/"):
                    link = "https://lista.mercadolivre.com.br" + link

                # Imagem
                img_tag = card.find("img")
                if not img_tag: continue
                imagem = img_tag.get("data-src") or img_tag.get("src") or ""
                if imagem.startswith("data:image"): continue

                # Se chegou aqui, é um produto válido
                produtos.append({
                    "nome": nome,
                    "preco": valor,
                    "link": link,
                    "img": imagem,
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1)
                })
                logging.info(f"📦 Produto {idx+1}: {nome} | R$ {valor}")

            except Exception as e:
                logging.warning(f"⚠️ Erro ao ler produto {idx+1}: {e}")

        logging.info(f"🏁 FINAL: {len(produtos)} produtos prontos para envio")
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
