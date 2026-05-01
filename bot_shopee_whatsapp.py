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
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO HIBRIDA SHOPEE + ML")

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400

logging.basicConfig(level=logging.INFO)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

ARQUIVO_HISTORICO = "historico_produtos.json"

# =========================
# HISTÓRICO
# =========================

def carregar_historico():
    if os.path.exists(ARQUIVO_HISTORICO):
        with open(ARQUIVO_HISTORICO, "r") as f:
            return json.load(f)
    return {"links": [], "titulos": {}}

def salvar_historico(data):
    with open(ARQUIVO_HISTORICO, "w") as f:
        json.dump(data, f)

historico = carregar_historico()

# =========================
# HORÁRIO
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(21, 0)

# =========================
# LIMPEZA
# =========================

def limpar_titulo(nome):
    nome = nome.lower()
    nome = re.sub(r'\d+', '', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome

def produto_similar(nome_limpo):
    for titulo in historico["titulos"].keys():
        if len(set(nome_limpo.split()) & set(titulo.split())) >= 2:
            return True
    return False

# =========================
# COPY
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link):

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

    gatilhos = [
        "Preço muito abaixo do que costuma aparecer",
        "Avaliações acima da média (produto confiável)",
        "Volume de vendas alto nos últimos dias",
        "Simples, útil e direto ao ponto",
        "Custo-benefício difícil de bater",
        "Quem compra normalmente recomenda",
        "Produto funcional, sem frescura",
        "Tá girando bem dentro da plataforma",
        "Boa margem pra afiliado",
        "Não é hype, é produto que resolve"
    ]

    return f"""
<b>{random.choice(aberturas)}</b>

🔥 <b>{nome}</b>

{random.choice(gatilhos)}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# WHATSAPP
# =========================

def gerar_link_whatsapp(msg, link):
    texto = re.sub('<[^<]+?>', '', msg)
    texto += f"\n\n{link}"
    return f"https://wa.me/?text={quote(texto)}"

# =========================
# SHOPEE
# =========================

def get_shopee():

    timestamp = int(time.time())

    query = """
    query {
        productOfferV2(sortType: 2, limit: 20) {
            nodes {
                productName
                priceMin
                commissionRate
                sales
                ratingStar
                productLink
                imageUrl
            }
        }
    }
    """

    payload = json.dumps({"query": query})
    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers)
        data = r.json()
        return data["data"]["productOfferV2"]["nodes"]
    except:
        return []

# =========================
# MERCADO LIVRE
# =========================

def get_ml():

    url = "https://api.mercadolibre.com/sites/MLB/search?q=oferta"
    r = requests.get(url).json()

    produtos = []

    for item in r.get("results", [])[:10]:
        produtos.append({
            "productName": item["title"],
            "priceMin": item["price"],
            "sales": random.randint(100, 5000),
            "ratingStar": round(random.uniform(4.2, 5.0), 1),
            "productLink": item["permalink"],
            "imageUrl": item["thumbnail"],
            "commissionRate": 0.05
        })

    return produtos

# =========================
# ENVIO
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    produtos = get_shopee()[:10] + get_ml()[:10]
    random.shuffle(produtos)

    enviados = []

    for item in produtos:

        link = item["productLink"]

        if link in historico["links"]:
            continue

        nome = html.escape(item["productName"])
        nome_limpo = limpar_titulo(nome)

        if produto_similar(nome_limpo):
            continue

        preco = float(item["priceMin"])

        if preco < 10 or preco > 800:
            continue

        rating = float(item["ratingStar"])
        vendas = int(item["sales"])

        if rating < 4.2 or vendas < 20:
            continue

        msg = gerar_copy(
            nome,
            f"{preco:.2f}",
            f"{vendas:,}".replace(",", "."),
            rating,
            round(item["commissionRate"]*100,2),
            link
        )

        zap = gerar_link_whatsapp(msg, link)

        msg += f'\n📲 <a href="{zap}">Compartilhar</a>'

        enviados.append({
            "msg": msg,
            "img": item["imageUrl"],
            "link": link,
            "nome": nome_limpo
        })

        if len(enviados) >= 5:
            break

    for item in enviados:
        try:
            await context.bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=item["img"],
                caption=item["msg"],
                parse_mode="HTML"
            )

            historico["links"].append(item["link"])
            historico["titulos"][item["nome"]] = time.time()
            salvar_historico(historico)

            await asyncio.sleep(30)

        except Exception as e:
            logging.error(e)

# =========================
# START
# =========================

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    print("🤖 BOT HIBRIDO RODANDO")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.run_polling()
