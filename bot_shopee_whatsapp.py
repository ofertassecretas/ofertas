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

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL_SHOPEE = 5400

logging.basicConfig(level=logging.INFO)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

ARQUIVO_HISTORICO = "historico_produtos.json"

# =========================
# KEYWORDS
# =========================

keywords_moto = [
    "kit relação cg 160",
    "pastilha freio moto",
    "amortecedor moto",
    "kit embreagem moto",
    "vela iridium moto",
    "carenagem cg",
    "retentor bengala",
    "pneu moto"
]

keywords_maternidade = [
    "kit maternidade bebê",
    "body bebê",
    "saída maternidade",
    "bolsa maternidade",
    "carrinho bebê"
]

keywords_moda = [
    "vestido feminino",
    "camisa masculina",
    "tenis masculino"
]

# =========================
# FILTRO MOTO (ANTI ERRO)
# =========================

palavras_moto = [
    "moto","cg","fan","titan","biz","xre","lander","fazer","factor",
    "freio","embreagem","amortecedor","vela","pneu","carenagem",
    "guidão","pastilha","bengala","cilindro","motor"
]

def eh_produto_moto(nome):
    nome = nome.lower()
    return any(p in nome for p in palavras_moto)

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
    return dt_time(5, 0) <= agora <= dt_time(23, 0)

# =========================
# LIMPEZA
# =========================

def limpar_titulo(nome):
    nome = nome.lower()
    nome = re.sub(r'\d+', '', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome

# =========================
# COPY INTELIGENTE
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, categoria):

    if categoria == "moto":
        frase = random.choice([
            "🏍️ Peça com ótimo custo-benefício",
            "🔧 Essa aqui vale a pena conferir",
            "⚙️ Produto muito bem avaliado",
            "🔥 Esse tá saindo bastante"
        ])

    elif categoria == "maternidade":
        frase = random.choice([
            "👶 Muito procurado pelas mamães",
            "🍼 Ideal pro dia a dia do bebê",
            "💖 Produto bem avaliado",
            "✨ Ótima escolha pro enxoval"
        ])

    else:
        frase = random.choice([
            "🔥 Vale a pena conferir",
            "👀 Olha esse achado",
            "💥 Bom e barato",
            "🚨 Esse tá compensando"
        ])

    return f"""
<b>{frase}</b>

🔥 <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Oferta pode acabar a qualquer momento

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# WHATSAPP
# =========================

def gerar_link_whatsapp(texto):
    return f"https://wa.me/?text={quote(texto)}"

def montar_texto_whatsapp(nome, preco, vendas, avaliacao, link):
    texto = f"""🔥 Oferta top

{nome}

💰 R$ {preco}
⭐ {avaliacao} | 🛒 {vendas} vendas

👇 Link:
{link}
"""
    return gerar_link_whatsapp(texto)

# =========================
# API
# =========================

def get_shopee_offers(keyword=None):

    timestamp = int(time.time())

    query = f"""
    query {{
        productOfferV2(keyword: "{keyword}", sortType: 2, limit: 10) {{
            nodes {{
                productName
                priceMin
                commissionRate
                sales
                ratingStar
                productLink
                imageUrl
            }}
        }}
    }}
    """

    payload = json.dumps({"query": query})

    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            return data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
    except:
        return []

    return []

# =========================
# ENVIO
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    ofertas = []

    for k in keywords_moto:
        produtos = get_shopee_offers(k)
        for p in produtos:
            if eh_produto_moto(p["productName"]):
                ofertas.append((p, "moto"))

    for k in keywords_maternidade:
        produtos = get_shopee_offers(k)
        for p in produtos:
            ofertas.append((p, "maternidade"))

    for k in keywords_moda:
        produtos = get_shopee_offers(k)
        for p in produtos:
            ofertas.append((p, "moda"))

    enviados = 0

    for item, categoria in ofertas:

        if enviados >= 5:
            break

        link = aplicar_id_afiliado(item["productLink"])

        if link in historico["links"]:
            continue

        nome = html.escape(item["productName"])

        try:
            preco = float(item["priceMin"])
        except:
            continue

        if preco > 250:
            continue

        vendas = str(item.get("sales", 0))
        avaliacao = item.get("ratingStar", 0)
        comissao = round(float(item.get("commissionRate", 0)) * 100, 2)

        msg = gerar_copy(nome, f"{preco:.2f}", vendas, avaliacao, comissao, link, categoria)

        zap = montar_texto_whatsapp(nome, f"{preco:.2f}", vendas, avaliacao, link)

        msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
        msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

        try:
            await context.bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=item["imageUrl"],
                caption=msg,
                parse_mode="HTML"
            )

            historico["links"].append(link)
            salvar_historico(historico)

            enviados += 1
            await asyncio.sleep(40)

        except Exception as e:
            logging.error(e)

# =========================
# AUX
# =========================

def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

# =========================
# START
# =========================

async def post_init(app):
    app.job_queue.run_repeating(send_shopee_offers, interval=CHECK_INTERVAL_SHOPEE, first=10)
    logging.info("🤖 Bot rodando!")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.run_polling(drop_pending_updates=True)

