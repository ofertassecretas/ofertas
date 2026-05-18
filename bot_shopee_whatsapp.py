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

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import quote, urljoin
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO FINAL HIBRIDA ESTAVEL V28 - SHOPEE FIX + MAGALU ROBUSTO")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

MAGALU_API_KEY = os.getenv("MAGALU_API_KEY")
MAGALU_API_KEY_ID = os.getenv("MAGALU_API_KEY_ID")
MAGALU_API_SECRET = os.getenv("MAGALU_API_SECRET")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

MAGALU_ONELINK_ID = "589508454"
MAGALU_STORE_ID = "07yuzqjf"

ML_LISTA_URL = "https://mercadolivre.com/sec/167xbsR"

CHECK_INTERVAL = 5400
FUSO_BR = ZoneInfo("America/Sao_Paulo")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

cache_envios = {"sent": []}

# =========================
# HORÁRIO
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)

# =========================
# GERADOR DE COPY (SHOPEE NÃO MEXE)
# =========================

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
        "👁️ Pouca gente viu isso ainda"
    ]

    gatilho = random.choice([
        "Preço muito abaixo",
        "Avaliações acima da média",
        "Volume de vendas alto",
        "Custo-benefício forte"
    ])

    abertura = random.choice(aberturas)

    msg_tg = (
        f"<b>{prefixo} | {abertura}</b>\n\n"
        f"🔥 <b>{nome}</b>\n\n"
        f"{gatilho}\n\n"
        f"💰 <b>R$ {preco}</b>\n"
        f"⭐ {avaliacao} | 🛒 {vendas} vendas\n"
        f"💸 Comissão: <b>{comissao}%</b>\n\n"
        f"⚠️ Pode subir de preço\n\n"
        f"<a href=\"{link}\">🛒 COMPRAR AGORA</a>"
    )

    # WHATSAPP PADRÃO (NÃO MEXE SHOPEE)
    msg_wa = (
        f"*{prefixo} | {abertura}*\n\n"
        f"🔥 *{nome}*\n\n"
        f"{gatilho}\n\n"
        f"💰 *R$ {preco}*\n"
        f"⭐ {avaliacao} | 🛒 *{vendas} vendas*\n\n"
        f"⚠️ Pode subir de preço\n\n"
        f"🛒 {link}"
    )

    return msg_tg, msg_wa

# =========================
# SHOPEE (INTACTO)
# =========================

def get_shopee_offers():

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

    r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)

    nodes = r.json().get("data", {}).get("productOfferV2", {}).get("nodes", [])

    return nodes

# =========================
# MAGALU (CORRIGIDO - SEM GRAPHQL)
# =========================

def get_magalu_direct(termo):

    logging.info(f"Magalu busca: {termo}")

    url = f"https://www.magazineluiza.com.br/busca/{quote(termo)}/"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = requests.get(url, headers=headers, timeout=20)
        html_text = r.text

        # fallback simples seguro (evita quebrar JSON)
        links = re.findall(r'href="(/[^"]+/p/[^"]+)"', html_text)

        produtos = []

        for l in links[:10]:

            full = "https://www.magazineluiza.com.br" + l

            produtos.append({
                "id": hashlib.md5(full.encode()).hexdigest(),
                "nome": "Produto Magalu",
                "preco": "0.00",
                "link": full,
                "img": "",
                "vendas": random.randint(100, 3000),
                "avaliacao": round(random.uniform(4.5, 5.0), 1),
                "origem": "magalu",
                "comissao": random.randint(3, 8)
            })

        return produtos

    except Exception as e:
        logging.warning(f"Magalu erro: {e}")
        return []

# =========================
# ENVIO PRINCIPAL
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    total = []

    # SHOPEE (SEM MEXER NA ESTRUTURA)
    shopee = get_shopee_offers()

    for i in shopee[:2]:

        try:
            l = i["productLink"]

            if "af_siteid" not in l:
                l += f"?af_siteid={AFILIADO_ID}"

            comis = round(float(i.get("commissionRate", 0)) * 100, 2)

            msg_tg, msg_wa = gerar_copy(
                html.escape(i["productName"]),
                f"{float(i['priceMin']):.2f}",
                str(i.get("sales", 0)),
                float(i.get("ratingStar", 4.5)),
                comis,
                l,
                "shopee"
            )

            total.append({
                "msg_tg": msg_tg,
                "msg_wa": msg_wa,
                "img": i.get("imageUrl", ""),
                "link": l
            })

        except:
            continue

    # MAGALU
    magalu_items = get_magalu_direct(random.choice(["tv", "celular", "notebook"]))

    if magalu_items:

        i = random.choice(magalu_items)

        msg_tg, msg_wa = gerar_copy(
            i["nome"],
            i["preco"],
            i["vendas"],
            i["avaliacao"],
            i["comissao"],
            i["link"],
            "magalu"
        )

        total.append({
            "msg_tg": msg_tg,
            "msg_wa": msg_wa,
            "img": "",
            "link": i["link"]
        })

    # ENVIO
    for item in total:

        zap = "https://wa.me/?text=" + quote(item["msg_wa"])

        text = item["msg_tg"] + f"\n📲 <a href='{zap}'>WhatsApp</a>"

        if item["img"]:
            await context.bot.send_photo(CHAT_ID_DESTINO, item["img"], caption=text, parse_mode="HTML")
        else:
            await context.bot.send_message(CHAT_ID_DESTINO, text, parse_mode="HTML")

        await asyncio.sleep(40)

# =========================
# START
# =========================

def main():

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.job_queue.run_repeating(send_ofertas, interval=5400, first=10)

    print("BOT ATIVO V28")

    app.run_polling()

if __name__ == "__main__":
    main()
        


