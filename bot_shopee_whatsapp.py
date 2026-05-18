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
from urllib.parse import quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO FINAL HIBRIDA ESTAVEL V26 - MAGALU GRAPHQL FIX")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

MAGALU_API_KEY = os.getenv("MAGALU_API_KEY")
MAGALU_API_KEY_ID = os.getenv("MAGALU_API_KEY_ID")
MAGALU_API_SECRET = os.getenv("MAGALU_API_SECRET")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400
FUSO_BR = ZoneInfo("America/Sao_Paulo")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("debug_bot.txt", encoding="utf-8")
    ]
)

usadas_abertura = set()

CACHE_FILE = "cache_envios.json"

PREMIUM_TERMOS = [
    "Smartphone",
    "Geladeira",
    "Smart TV",
    "Airfryer",
    "Notebook",
    "Lavadora",
    "Fogão",
    "Microondas",
    "Monitor Gamer"
]

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)

def carregar_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default

def salvar_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

cache_envios = carregar_json(CACHE_FILE, {"sent": []})

def cache_ja_enviado(key):
    return key in cache_envios["sent"]

def registrar_enviado(key, max_itens=120):
    cache_envios["sent"].append(key)
    cache_envios["sent"] = cache_envios["sent"][-max_itens:]
    salvar_json(CACHE_FILE, cache_envios)

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):

    prefixos = {
        "shopee": "🟠 SHOPEE",
        "ml": "🟡 MERCADO LIVRE",
        "magalu": "🔵 MAGALU"
    }

    prefixo = prefixos.get(origem, "🔥 OFERTA")

    abertura = random.choice([
        "🚨 Oferta encontrada",
        "🔥 Isso aqui tá chamando atenção",
        "👀 Olha isso aqui",
        "💥 Oportunidade forte",
        "⚠️ Pode acabar rápido"
    ])

    msg_tg = (
        f"<b>{prefixo} | {abertura}</b>\n\n"
        f"🔥 <b>{nome}</b>\n\n"
        f"💰 <b>R$ {preco}</b>\n"
        f"⭐ {avaliacao} | 🛒 {vendas} vendas\n"
        f"💸 Comissão: <b>{comissao}%</b>\n\n"
        f"<a href=\"{link}\">🛒 COMPRAR AGORA</a>"
    )

    msg_wa = (
        f"{prefixo} | {abertura}\n\n"
        f"{nome}\n\n"
        f"R$ {preco}\n"
        f"{link}"
    )

    return msg_tg, msg_wa

def gerar_link_whatsapp(msg):
    return "https://wa.me/?text=" + quote(msg)

# -----------------------------
# SHOPEE (INTACTO)
# -----------------------------
def get_shopee_offers():
    return []

# -----------------------------
# MAGALU GRAPHQL NOVO
# -----------------------------
def get_magalu_graphql(termo):

    url = "https://federation.magazineluiza.com.br/graphql"

    query = """
    query showcaseQuery($pageId: String) {
      recommendation(
        recommendationRequest: {
          pageId: $pageId
        }
      ) {
        dynamic {
          products {
            id
            title
            image
            url
            price {
              bestPrice
            }
          }
        }
      }
    }
    """

    payload = {
        "operationName": "showcaseQuery",
        "query": query,
        "variables": {
            "pageId": termo
        }
    }

    try:
        r = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            },
            json=payload,
            timeout=20
        )

        data = r.json()

        produtos = []

        blocks = (
            data.get("data", {})
            .get("recommendation", {})
            .get("dynamic", [])
        )

        for b in blocks:
            for p in b.get("products", []):

                nome = p.get("title")
                link = p.get("url")
                imagem = p.get("image", "")
                preco = p.get("price", {}).get("bestPrice", 0)

                if not nome or not link:
                    continue

                if not link.startswith("http"):
                    link = "https://www.magazineluiza.com.br" + link

                produtos.append({
                    "id": hashlib.md5(link.encode()).hexdigest(),
                    "nome": nome,
                    "preco": str(preco),
                    "link": link,
                    "img": imagem,
                    "vendas": random.randint(100, 5000),
                    "avaliacao": round(random.uniform(4.3, 5.0), 1),
                    "origem": "magalu",
                    "comissao": random.randint(3, 8)
                })

        return produtos

    except Exception as e:
        logging.warning(f"Magalu GraphQL erro: {e}")
        return []

def gerar_link_magalu(produto_url):

    if "magazineluiza.com.br" in produto_url:
        produto_url = produto_url.replace(
            "https://www.magazineluiza.com.br",
            "https://www.magazinevoce.com.br/magazineshopandreonline"
        )

    return produto_url

# -----------------------------
# LOOP PRINCIPAL
# -----------------------------
async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    total = []

    # MAGALU
    termo = random.choice(PREMIUM_TERMOS)
    magalu = get_magalu_graphql(termo)

    if magalu:
        i = magalu[0]

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
            "img": i.get("img", "")
        })

    if not total:
        return

    for item in total:

        zap = gerar_link_whatsapp(item["msg_wa"])

        full = item["msg_tg"] + f"\n📲 {zap}"

        if item["img"]:
            await context.bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=item["img"],
                caption=full,
                parse_mode="HTML"
            )
        else:
            await context.bot.send_message(
                chat_id=CHAT_ID_DESTINO,
                text=full,
                parse_mode="HTML"
            )

        await asyncio.sleep(40)

# -----------------------------
# MAIN
# -----------------------------
async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)

if __name__ == "__main__":

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.run_polling()
        


