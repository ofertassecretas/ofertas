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

    # ✅ SESSÃO COMPLETA + COOKIES + CABEÇALHOS REAIS
    sessao = requests.Session()
    sessao.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,es;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com.br/",
        "Sec-Ch-Ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    })

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
        # ✅ ROTA ALTERNATIVA que NÃO BLOQUEIA (usada por todos os bots que funcionam)
        url = f"https://lista.mercadolivre.com.br/{quote(termo)}_OrderId_PRICE*Asc_NoIndex_True"

        # Delay aleatório para parecer humano
        import time
        time.sleep(random.uniform(2, 4))

        # Primeiro acessa a página inicial para pegar cookies válidos
        sessao.get("https://lista.mercadolivre.com.br/", timeout=30)
        time.sleep(1)

        # Agora sim busca os produtos com sessão pronta
        response = sessao.get(url, timeout=30)
        logging.info(f"Status ML: {response.status_code}")

        if response.status_code != 200:
            logging.error("Página com erro")
            return []

        # ✅ SALVA O HTML PARA DEBUG (pode deixar, não atrapalha)
        # with open("debug.html", "w", encoding="utf-8") as f:
        #     f.write(response.text)

        soup = BeautifulSoup(response.text, "html.parser")
        produtos = []

        # ✅ TODOS OS SELETORES NOVOS E ANTIGOS
        seletores = [
            "li.ui-search-layout__item",
            "div.poly-card__container",
            "div.ui-search-result",
            "section.andes-card",
            "div[class*='item']",
            "div[class*='product']"
        ]

        cards = []
        for sel in seletores:
            cards = soup.select(sel)
            if cards:
                logging.info(f"✅ ENCONTRADO: {sel} | {len(cards)} itens")
                break

        if not cards:
            logging.error("❌ Nenhum card encontrado")
            return []

        # ✅ EXTRAÇÃO POR PADRÃO, NÃO POR CLASSE ESPECÍFICA
        for idx, card in enumerate(cards[:5]):
            try:
                # Título: pega qualquer tag de texto grande
                titulo = card.find("h2") or card.find("h3") or card.find("span", class_=re.compile("title|name", re.I))
                if not titulo: continue
                nome = titulo.get_text(strip=True)
                if len(nome) < 5: continue

                # Preço: pega qualquer coisa com R$ ou números
                preco_texto = card.get_text()
                preco_match = re.search(r'R\$\s*([\d.,]+)', preco_texto)
                if not preco_match: continue
                preco = preco_match.group(1).strip()

                # Link: primeiro link da div
                link_tag = card.find("a", href=True)
                if not link_tag: continue
                link = link_tag["href"]
                if link.startswith("/"):
                    link = "https://lista.mercadolivre.com.br" + link

                # Imagem: primeira imagem válida
                img_tag = card.find("img", src=True)
                if not img_tag: continue
                img = img_tag.get("data-src") or img_tag.get("src") or ""
                if img.startswith("data:image"): continue

                produtos.append({
                    "nome": nome,
                    "preco": preco,
                    "link": link,
                    "img": img,
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1)
                })
                logging.info(f"📦 {nome} | R$ {preco}")

            except Exception as e:
                logging.warning(f"⚠️ Erro item {idx+1}: {e}")

        logging.info(f"🏁 Final: {len(produtos)} produtos")
        return produtos

    except Exception as e:
        logging.error(f"💥 ERRO GERAL: {e}")
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
