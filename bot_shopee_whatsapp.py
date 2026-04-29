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
# CONTEXTO
# =========================

def obter_contexto():
    mes = datetime.now().month
    if mes in [6,7,8]:
        return "inverno"
    elif mes in [12,1,2]:
        return "verao"
    elif mes in [3,4,5]:
        return "outono"
    return "primavera"

def eventos_atuais():
    hoje = datetime.now()
    if hoje.month == 5:
        return ["presente dia das mães", "perfume feminino", "kit beleza"]
    if hoje.month == 6:
        return ["roupa festa junina", "decoração festa junina"]
    if hoje.month == 11:
        return ["black friday ofertas"]
    return []

def keywords_por_epoca():
    contexto = obter_contexto()

    if contexto == "inverno":
        base = ["jaqueta", "moletom", "cobertor", "aquecedor"]
    elif contexto == "verao":
        base = ["camiseta", "ventilador", "chinelo"]
    elif contexto == "outono":
        base = ["calça jeans", "organizador casa"]
    else:
        base = ["decoração casa"]

    return base + eventos_atuais()

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
# COPY TELEGRAM (INTELIGENTE)
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link):

    nome_lower = nome.lower()

    if "bebê" in nome_lower or "bebe" in nome_lower:
        intro = "👶 Quem tem bebê sabe como isso ajuda MUITO no dia a dia"
        detalhe = "Facilita a rotina e evita dor de cabeça"
    elif "cozinha" in nome_lower or "panela" in nome_lower:
        intro = "🍳 Isso aqui na cozinha ajuda demais"
        detalhe = "Coisa simples, mas que no uso diário faz diferença"
    elif "camisa" in nome_lower or "vestido" in nome_lower:
        intro = "🧥 Olha isso aqui"
        detalhe = "Bonito, versátil e preço bem abaixo do normal"
    else:
        intro = "👀 Olha isso aqui"
        detalhe = "Não parece grande coisa, mas surpreende quando vê melhor"

    return f"""
<b>{intro}</b>

🔥 <b>{nome}</b>

{detalhe}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Não sei até quando fica nesse preço

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# COPY WHATSAPP (SEPARADO)
# =========================

def gerar_texto_whatsapp(nome, preco, vendas, avaliacao, link):

    return f"""👀 Olha isso aqui

🔥 {nome}

💰 R$ {preco}
⭐ {avaliacao} | 🛒 {vendas} vendas

⚠️ Não sei até quando fica nesse preço

👇 olha aqui:
{link}
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
        productOfferV2(keyword: "{keyword or ''}", sortType: 2, limit: 15) {{
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
    for k in keywords_por_epoca():
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

        if item.get("ratingStar", 0) < 4.5:
            continue

        if item.get("sales", 0) < 50:
            continue

        vendas = item.get("sales", 0)
        avaliacao = item.get("ratingStar", 0)
        comissao = round(float(item.get("commissionRate", 0)) * 100, 2)
        img = item.get("imageUrl")

        vendas_f = f"{int(vendas):,}".replace(",", ".")

        msg = gerar_copy(nome, f"{preco:.2f}", vendas_f, avaliacao, comissao, link)

        texto_zap = gerar_texto_whatsapp(nome, f"{preco:.2f}", vendas_f, avaliacao, link)
        zap = gerar_link_whatsapp(texto_zap)

        msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
        msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

        selecionadas.append({
            "msg": msg,
            "img": img,
            "link": link,
            "nome_limpo": nome_limpo
        })

        if len(selecionadas) >= 5:
            break

    if selecionadas:
        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS LIBERADAS AGORA\nSeparei umas MUITO boas hoje 👇"
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
