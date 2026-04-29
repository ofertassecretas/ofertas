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

print("VERSAO NOVA ATIVA")

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
# CONTEXTO (SAZONAL)
# =========================

def keywords_inteligentes():
    mes = datetime.now().month

    base = ["organizador", "promoção", "oferta"]

    if mes in [6,7,8]:
        base += ["jaqueta", "moletom", "cobertor", "aquecedor"]
    elif mes in [12,1,2]:
        base += ["ventilador", "camiseta", "chinelo"]
    elif mes == 5:
        base += ["presente dia das mães", "perfume feminino", "kit beleza"]
    elif mes == 6:
        base += ["festa junina", "decoração junina"]

    return base

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
# COPY INTELIGENTE
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link):

    frases_inicio = [
        "🚨 Isso aqui tá chamando atenção",
        "👀 Olha isso aqui",
        "🔥 Achei isso e fui ver as avaliações",
        "💥 Esse aqui vale a pena olhar"
    ]

    gatilhos = [
        "Preço muito abaixo do que entrega",
        "Tá vendendo bem e a galera tá avaliando alto",
        "Simples mas resolve muito no dia a dia",
        "Não é à toa que tá saindo bastante"
    ]

    inicio = random.choice(frases_inicio)
    gatilho = random.choice(gatilhos)

    return f"""
<b>{inicio}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço a qualquer momento

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# WHATSAPP (CORRIGIDO)
# =========================

def gerar_texto_whatsapp(nome, preco, vendas, avaliacao, link):

    return f"""🔥 OLHA ISSO

{nome}

💰 R$ {preco}
⭐ {avaliacao} | 🛒 {vendas} vendas

⚠️ Pode subir de preço a qualquer momento

👉 {link}
"""

def gerar_link_whatsapp(texto):
    return f"https://wa.me/?text={quote(texto)}"

# =========================
# API
# =========================

def get_shopee_offers(keyword=None):

    timestamp = int(time.time())

    query_body = f"""
    query {{
        productOfferV2(keyword: "{keyword or ''}", sortType: 2, limit: 20) {{
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

    for k in keywords_inteligentes():
        ofertas += get_shopee_offers(k)

    selecionadas = []

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

        # 🔥 CORREÇÃO DO ERRO
        try:
            rating = float(item.get("ratingStar", 0))
        except:
            rating = 0

        if rating < 4.5:
            continue

        try:
            vendas = int(item.get("sales", 0))
        except:
            vendas = 0

        if vendas < 50:
            continue

        try:
            comissao = round(float(item.get("commissionRate", 0)) * 100, 2)
        except:
            comissao = 0

        vendas_f = f"{vendas:,}".replace(",", ".")

        msg = gerar_copy(nome, f"{preco:.2f}", vendas_f, rating, comissao, link)

        texto_zap = gerar_texto_whatsapp(nome, f"{preco:.2f}", vendas_f, rating, link)
        zap = gerar_link_whatsapp(texto_zap)

        msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
        msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

        selecionadas.append({
            "msg": msg,
            "img": item.get("imageUrl"),
            "link": link,
            "nome_limpo": nome_limpo
        })

        if len(selecionadas) >= 5:
            break

    if selecionadas:
        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS LIBERADAS AGORA\nSeparei as melhores 👇"
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
