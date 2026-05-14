import asyncio
import requests
import logging
import random
import hashlib
import time
import json
import os
import html
import re

from bs4 import BeautifulSoup
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO CURADORIA V1 - MAGALU + ML LISTAS")

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

# =========================
# SHOPEE
# =========================

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# =========================
# MAGALU SUA LOJA
# =========================

MAGALU_STORE_URL = "https://www.magazinevoce.com.br/magazineshopandreonline/"

MAGALU_FILTROS = [
    "smartphone",
    "iphone",
    "samsung",
    "tv",
    "geladeira",
    "notebook",
    "air fryer",
]

# =========================
# LISTAS ML
# =========================

ML_LISTAS = [
    "https://mercadolivre.com/sec/167xbsR",
]

# =========================
# CONFIG GERAL
# =========================

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
    return dt_time(5, 0) <= agora <= dt_time(22, 0)

# =========================
# COPY
# =========================

usadas_abertura = set()

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):

    prefixos = {
        "shopee": "🟠 SHOPEE",
        "ml": "🟡 MERCADO LIVRE",
        "magalu": "🔵 MAGALU"
    }

    prefixo = prefixos.get(origem, "🔥 OFERTA")

    aberturas = [
        "🚨 Isso aqui não é comum aparecer assim",
        "👀 Achei isso aqui e fui conferir…",
        "🔥 Isso aqui tá com cara de oportunidade",
        "💥 Esse aqui tá chamando atenção de quem compra",
        "🛑 Para tudo e olha isso aqui",
        "🤯 Sério… olha esse achado",
        "⚠️ Isso aqui pode desaparecer rápido",
        "👁️ Pouca gente viu isso ainda",
        "📉 Esse preço aqui não costuma durar",
        "🚀 Esse aqui tá começando a rodar forte"
    ]

    gatilho = random.choice([
        "Preço muito abaixo",
        "Avaliações acima da média",
        "Volume de vendas alto",
        "Custo-benefício forte"
    ])

    abertura = random.choice(
        [a for a in aberturas if a not in usadas_abertura] or aberturas
    )

    usadas_abertura.add(abertura)

    return f"""
<b>{prefixo} | {abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão estimada

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# WHATSAPP
# =========================

def gerar_link_whatsapp(msg_html, link):

    texto = re.sub('<[^<]+?>', '', msg_html)

    texto += f"\n\n🛒 {link}"

    return f"https://wa.me/?text={quote(texto)}"

# =========================
# SHOPEE
# =========================

def get_shopee_offers():

    logging.info("Buscando Shopee...")

    timestamp = int(time.time())

    query_body = """
    query {
      productOfferV2(sortType: 2, limit: 10) {
        nodes {
          productName,
          priceMin,
          commissionRate,
          sales,
          ratingStar,
          productLink,
          imageUrl
        }
      }
    }
    """

    payload = json.dumps({"query": query_body})

    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD

    signature = hashlib.sha256(base.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:

        r = requests.post(
            SHOPEE_GRAPHQL_URL,
            data=payload,
            headers=headers,
            timeout=15
        )

        return r.json()["data"]["productOfferV2"]["nodes"]

    except Exception as e:

        logging.error(f"Erro Shopee: {e}")

        return []

# =========================
# MAGALU SUA LOJA
# =========================

def get_magalu_store():

    logging.info("Buscando produtos da SUA LOJA MAGALU")

    try:

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(
            MAGALU_STORE_URL,
            headers=headers,
            timeout=15
        )

        soup = BeautifulSoup(r.text, "html.parser")

        produtos = []

        links = soup.find_all("a", href=True)

        for l in links:

            href = l["href"]

            texto = l.get_text(" ", strip=True)

            if not texto:
                continue

            texto_lower = texto.lower()

            if any(f in texto_lower for f in MAGALU_FILTROS):

                if "/p/" in href:

                    try:

                        preco = "0"

                        m = re.search(r'R\$ ?([\d\.,]+)', texto)

                        if m:
                            preco = m.group(1)

                        if href.startswith("/"):
                            href = "https://www.magazinevoce.com.br" + href

                        produtos.append({
                            "nome": texto[:120],
                            "preco": preco,
                            "link": href,
                            "img": "https://a-static.mlcdn.com.br/1500x1500/smartphone-samsung-galaxy/magazineluiza/227344500/123.jpg",
                            "vendas": random.randint(100, 4000),
                            "avaliacao": round(random.uniform(4.5, 5.0), 1),
                            "origem": "magalu"
                        })

                    except:
                        pass

        random.shuffle(produtos)

        return produtos[:10]

    except Exception as e:

        logging.error(f"Erro MAGALU: {e}")

        return []

# =========================
# ML LISTA
# =========================

def get_ml_lista():

    logging.info("Buscando produtos da LISTA ML")

    produtos = []

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:

        for url in ML_LISTAS:

            r = requests.get(
                url,
                headers=headers,
                timeout=15
            )

            soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            links = soup.find_all(
                "a",
                href=True
            )

            encontrados = []

            for l in links:

                href = l["href"]

                # somente produtos MLB
                if "MLB-" not in href:
                    continue

                if href in encontrados:
                    continue

                encontrados.append(href)

                texto = l.get_text(
                    " ",
                    strip=True
                )

                if len(texto) < 10:
                    continue

                # =========================
                # PREÇO
                # =========================

                preco = "0"

                texto_pai = l.parent.get_text(
                    " ",
                    strip=True
                )

                preco_match = re.search(
                    r'R\$ ?([\d\.\,]+)',
                    texto_pai
                )

                if preco_match:

                    preco = preco_match.group(1)

               # =========================
# IMAGEM ML
# =========================

img = "https://http2.mlstatic.com/D_NQ_NP_2X_945607-MLB83916558834_042025-F.webp"

produto_req = requests.get(
    href,
    headers=headers,
    timeout=10
)

produto_soup = BeautifulSoup(
    produto_req.text,
    "html.parser"
)

meta_img = produto_soup.find(
    "meta",
    property="og:image"
)

if meta_img:

    possible_img = meta_img.get(
        "content",
        ""
    )

    if possible_img:

        possible_img = possible_img.replace(
            "\\u002F",
            "/"
        )

        if possible_img.startswith("//"):

            possible_img = "https:" + possible_img

        if possible_img.startswith("http"):

            img = possible_img

            produtos.append({
                "nome": texto[:120],
                "preco": preco,
                "link": href,
                "img": img,
                "vendas": random.randint(100, 5000),
                "avaliacao": round(random.uniform(4.4, 5.0), 1),
                "origem": "ml"
            })

    random.shuffle(produtos)

    logging.info(
        f"ML Produtos encontrados: {len(produtos)}"
    )

    return produtos[:10]

except Exception as e:

    logging.error(
        f"Erro ML LISTA: {e}"
    )

    return []

# =========================
# ENVIO
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    try:

        if not dentro_do_horario():
            return

        usadas_abertura.clear()

        total_lista = []

        # =========================
        # 1 - SHOPEE
        # =========================

        shopee = get_shopee_offers()

        for i in shopee[:2]:

            try:

                l = i["productLink"]

                if "af_siteid" not in l:
                    l = f"{l}?af_siteid={AFILIADO_ID}"

                msg = gerar_copy(
                    html.escape(i["productName"]),
                    f"{float(i['priceMin']):.2f}",
                    f"{int(i.get('sales', 100)):,}".replace(",", "."),
                    float(i.get("ratingStar", 4.5)),
                    round(float(i.get("commissionRate", 0)) * 100, 2),
                    l,
                    "shopee"
                )

                total_lista.append({
                    "msg": msg,
                    "img": i["imageUrl"],
                    "link": l
                })

            except:
                pass

        # =========================
        # 2 - MAGALU SUA LOJA
        # =========================

        magalu = get_magalu_store()

        for i in magalu[:2]:

            try:

                msg = gerar_copy(
                    html.escape(i["nome"]),
                    i["preco"],
                    i["vendas"],
                    i["avaliacao"],
                    10,
                    i["link"],
                    "magalu"
                )

                total_lista.append({
                    "msg": msg,
                    "img": i["img"],
                    "link": i["link"]
                })

            except:
                pass

        # =========================
        # 3 - ML LISTA
        # =========================

        ml = get_ml_lista()

        for i in ml[:2]:

            try:

                msg = gerar_copy(
                    html.escape(i["nome"]),
                    i["preco"],
                    i["vendas"],
                    i["avaliacao"],
                    10,
                    i["link"],
                    "ml"
                )

                total_lista.append({
                    "msg": msg,
                    "img": i["img"],
                    "link": i["link"]
                })

            except:
                pass

        # =========================
        # ENVIO
        # =========================

        if not total_lista:
            return

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS NOVAS CHEGANDO..."
        )

        await asyncio.sleep(5)

        random.shuffle(total_lista)

        for item in total_lista:

            try:

                zap = gerar_link_whatsapp(
                    item["msg"],
                    item["link"]
                )

                full_msg = (
                    item["msg"] +
                    f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                    '\n━━━━━━━━━━━━━━━'
                    '\n📢 <b>Ofertas Secretas</b>'
                )

                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=full_msg,
                    parse_mode="HTML"
                )

                await asyncio.sleep(45)

            except Exception as e:

                logging.error(f"Erro ao enviar item: {e}")

    except Exception as e:

        logging.error(f"ERRO CRITICO: {e}")

# =========================
# START
# =========================

async def post_init(app):

    logging.info("🤖 BOT CURADORIA V1 ATIVADO")

    app.job_queue.run_repeating(
        send_ofertas,
        interval=CHECK_INTERVAL,
        first=10
    )

# =========================
# MAIN
# =========================

def main():

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.run_polling()

if __name__ == "__main__":
    main()




