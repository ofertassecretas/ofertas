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

ultimas_frases = []

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
# LIMPAR TITULO
# =========================

def limpar_titulo(nome):
    nome = nome.lower()
    nome = re.sub(r'\d+', '', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome

# =========================
# SIMILARIDADE
# =========================

def produto_similar(nome_limpo):
    agora = time.time()
    for titulo, timestamp in historico["titulos"].items():
        if agora - timestamp < 43200:
            if len(set(nome_limpo.split()) & set(titulo.split())) >= 2:
                return True
    return False

# =========================
# COPY INTELIGENTE
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, zap):

    global ultimas_frases

    nome_lower = nome.lower()

    if any(p in nome_lower for p in ["tenis", "camisa", "vestido", "calça", "short"]):
        categoria = "moda"

    elif any(p in nome_lower for p in ["bebe", "mamadeira", "fralda", "maternidade"]):
        categoria = "maternidade"

    elif any(p in nome_lower for p in ["cg", "biz", "xre", "fazer", "freio", "vela", "amortecedor", "cdi"]):
        categoria = "moto"

    else:
        categoria = "casa"

    if categoria == "moda":
        frases = [
            "👀 olha isso aqui",
            "😳 esse aqui me chamou atenção",
            "🔥 isso aqui tá saindo muito",
            "🤔 não dava nada por isso… mas olha"
        ]

    elif categoria == "maternidade":
        frases = [
            "👶 olha isso aqui, achei muito bom",
            "💗 esse aqui tá chamando atenção das mamães",
            "🍼 vi muita gente falando desse aqui",
            "✨ esse aqui vale muito a pena pro bebê"
        ]

    elif categoria == "moto":
        frases = [
            "🏍️ olha essa peça aqui",
            "🔧 isso aqui tá compensando demais",
            "💥 peça boa e preço baixo",
            "⚠️ isso aqui vale a pena pegar agora"
        ]

    else:
        frases = [
            "👀 olha isso aqui",
            "😳 esse aqui me surpreendeu",
            "🔥 isso aqui tá vendendo bem",
            "🤔 não dava nada por isso… até ver"
        ]

    frase = random.choice(frases)

    tentativas = 0
    while frase in ultimas_frases and tentativas < 5:
        frase = random.choice(frases)
        tentativas += 1

    ultimas_frases.append(frase)
    if len(ultimas_frases) > 10:
        ultimas_frases.pop(0)

    copy = f"""
<b>{frase}</b>

🔥 <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Não sei até quando vai ficar nesse preço

<a href="{link}">🛒 COMPRAR AGORA</a>

📲 <a href="{zap}">Copiar para divulgar no WhatsApp</a>
"""

    return copy, categoria

# =========================
# WHATSAPP (SEM COMISSÃO)
# =========================

def gerar_link_whatsapp(texto):
    return f"https://wa.me/?text={quote(texto)}"

def montar_texto_whatsapp(nome, preco, vendas, avaliacao, link):

    texto = f"""👀 olha isso aqui

🔥 {nome}

💰 R$ {preco}
⭐ {avaliacao} | 🛒 {vendas} vendas

⚠️ não sei até quando vai ficar nesse preço

👉 esse aqui tá barato demais:
{link}
"""

    return gerar_link_whatsapp(texto)

# =========================
# API SHOPEE
# =========================

def get_shopee_offers():

    timestamp = int(time.time())

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

    base_str = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base_str.encode("utf-8")).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        resp = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        if resp.status_code == 200:
            produtos = resp.json().get("data", {}).get("productOfferV2", {}).get("nodes", [])
            random.shuffle(produtos)
            return produtos
    except Exception as e:
        logging.error(e)

    return []

# =========================
# ENVIO PRINCIPAL
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    ofertas = get_shopee_offers()

    categorias = {"casa": [], "moda": [], "maternidade": [], "moto": []}

    for item in ofertas:

        link = item["productLink"]

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

        vendas = f"{int(item.get('sales',0)):,}".replace(",", ".")
        avaliacao = item.get("ratingStar", 0)
        comissao = round(float(item.get("commissionRate",0))*100,2)

        mensagem, categoria = gerar_copy(
            nome, f"{preco:.2f}", vendas, avaliacao, comissao, link, ""
        )

        zap = montar_texto_whatsapp(nome, f"{preco:.2f}", vendas, avaliacao, link)

        mensagem = mensagem.replace('href=""', f'href="{zap}"')
        mensagem += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

        categorias[categoria].append({
            "msg": mensagem,
            "img": item.get("imageUrl"),
            "link": link,
            "nome": nome_limpo
        })

    selecionadas = []

    if categorias["casa"]:
        selecionadas += categorias["casa"][:2]

    for cat in ["moda", "maternidade", "moto"]:
        if categorias[cat]:
            selecionadas.append(random.choice(categorias[cat]))

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
            historico["titulos"][item["nome"]] = time.time()
            salvar_historico(historico)

            await asyncio.sleep(60)

        except Exception as e:
            logging.error(e)

# =========================
# START
# =========================

async def post_init(app):
    app.job_queue.run_repeating(send_shopee_offers, interval=CHECK_INTERVAL_SHOPEE, first=10)
    logging.info("🤖 Bot rodando!")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.run_polling(drop_pending_updates=True)

