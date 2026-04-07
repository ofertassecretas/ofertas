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
    "carenagem cg 160",
    "capacete moto",
    "vela iridium moto",
    "kit embreagem moto",
    "amortecedor moto"
]

keywords_maternidade = [
    "kit maternidade bebê",
    "roupa bebê menina",
    "body bebê",
    "saída maternidade",
    "kit enxoval bebê",
    "bolsa maternidade"
]

keywords_moda = [
    "vestido feminino",
    "camisa masculina",
    "tenis masculino"
]

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
    agora = time.time()
    for titulo, timestamp in historico["titulos"].items():
        if agora - timestamp < 43200:
            if len(set(nome_limpo.split()) & set(titulo.split())) >= 2:
                return True
    return False

# =========================
# COPY MELHORADA
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, zap):

    nome_lower = nome.lower()

    if any(p in nome_lower for p in ["bebe","bebê","body","enxoval","maternidade"]):
        categoria = "maternidade"
    elif any(p in nome_lower for p in ["moto","cg","fan","titan","capacete","freio","embreagem"]):
        categoria = "moto"
    elif any(p in nome_lower for p in ["tenis","camisa","vestido"]):
        categoria = "moda"
    else:
        categoria = "casa"

    if categoria == "maternidade":
        frase = random.choice([
            "💖 Olha isso aqui que gracinha",
            "👶 Muito útil pra quem tem bebê",
            "🍼 Esse aqui vale a pena"
        ])
    elif categoria == "moto":
        frase = random.choice([
            "🏍️ Olha essa peça aqui",
            "🔥 Compensa demais isso aqui",
            "⚙️ Muito procurado"
        ])
    elif categoria == "moda":
        frase = random.choice([
            "👀 Olha esse achado",
            "🔥 Estilo com preço baixo",
            "✨ Vale conferir"
        ])
    else:
        frase = random.choice([
            "👀 Olha isso aqui",
            "🔥 Esse aqui chamou atenção"
        ])

    copy = f"""
<b>{frase}</b>

🔥 <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode acabar rápido

<a href="{link}">🛒 COMPRAR AGORA</a>

📲 <a href="{zap}">Compartilhar no WhatsApp</a>
"""

    return copy, categoria

# =========================
# WHATSAPP
# =========================

def gerar_link_whatsapp(texto):
    return f"https://wa.me/?text={quote(texto)}"

def montar_texto_whatsapp(nome, preco, vendas, avaliacao, link):

    texto = f"""🔥 OFERTA

{nome}

💰 R$ {preco}
⭐ {avaliacao} | 🛒 {vendas} vendas

👇 confira:
{link}
"""
    return gerar_link_whatsapp(texto)

# =========================
# API
# =========================

def get_shopee_offers(keyword=None):

    timestamp = int(time.time())

    if keyword:
        query_body = f"""
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
    else:
        query_body = """
        query {
            productOfferV2 {
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

    payload = json.dumps({"query": query_body})

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
            produtos = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
            random.shuffle(produtos)
            return produtos
    except Exception as e:
        logging.error(e)

    return []

# =========================
# ENVIO
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    ofertas = []

    ofertas += get_shopee_offers()

    for k in keywords_moto:
        ofertas += get_shopee_offers(k)

    for k in keywords_maternidade:
        ofertas += get_shopee_offers(k)

    for k in keywords_moda:
        ofertas += get_shopee_offers(k)

    categorias = {"casa": [], "moda": [], "maternidade": [], "moto": []}

    for item in ofertas:

        link = aplicar_id_afiliado(item["productLink"])

        if link in historico["links"]:
            continue

        nome = html.escape(item["productName"])
        nome_limpo = limpar_titulo(nome)

        if produto_similar(nome_limpo):
            continue

        try:
            preco = float(item["priceMin"])
        except:
            continue

        if preco > 250:
            continue

        vendas = item.get("sales", 0)
        avaliacao = item.get("ratingStar", 0)
        comissao = item.get("commissionRate", 0)
        img = item.get("imageUrl")

        vendas_f = f"{int(vendas):,}".replace(",", ".")
        comissao_f = round(float(comissao)*100,2)

        msg, cat = gerar_copy(nome, f"{preco:.2f}", vendas_f, avaliacao, comissao_f, link, "")
        zap = montar_texto_whatsapp(nome, f"{preco:.2f}", vendas_f, avaliacao, link)

        msg = msg.replace('href=""', f'href="{zap}"')
        msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

        categorias[cat].append({
            "msg": msg,
            "img": img,
            "link": link,
            "nome_limpo": nome_limpo
        })

    selecionadas = []
    selecionadas += categorias["casa"][:2]
    selecionadas += categorias["moda"][:1]
    selecionadas += categorias["maternidade"][:1]
    selecionadas += categorias["moto"][:1]

    if selecionadas:
        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS LIBERADAS AGORA 👇"
        )

    for item in selecionadas:

        try:
            if item["img"]:
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=item["msg"],
                    parse_mode="HTML"
                )

            historico["links"].append(item["link"])
            historico["titulos"][item["nome_limpo"]] = time.time()
            salvar_historico(historico)

            await asyncio.sleep(60)

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

