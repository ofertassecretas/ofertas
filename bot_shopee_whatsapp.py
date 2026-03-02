import asyncio
import requests
import logging
import random
import hashlib
import time
import json
import os
import html

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

# =========================
# CONFIGURAÇÕES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400
MAX_PRODUTOS_POR_RODADA = 3

logging.basicConfig(level=logging.INFO)

produtos_enviados = set()
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# =========================
# HORÁRIO
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    inicio = dt_time(6, 30)
    fim = dt_time(21, 0)
    return inicio <= agora <= fim

# =========================
# DETECTAR CATEGORIA
# =========================

def detectar_categoria(nome):
    nome = nome.lower()

    if any(p in nome for p in ["tv", "televis", "smart", "monitor"]):
        return "tv"
    if any(p in nome for p in ["panela", "frigideira", "cozinha", "air fryer"]):
        return "cozinha"
    if any(p in nome for p in ["mochila", "bolsa", "carteira"]):
        return "moda"
    if any(p in nome for p in ["varal", "organizador", "armario", "caixa"]):
        return "casa"
    if any(p in nome for p in ["fone", "bluetooth", "caixa de som"]):
        return "eletronico"

    return "geral"

# =========================
# COPY INTELIGENTE
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, zap):

    categoria = detectar_categoria(nome)

    emojis = {
        "tv": "📺",
        "cozinha": "🍳",
        "moda": "🎒",
        "casa": "🏠",
        "eletronico": "🎧",
        "geral": "🔥"
    }

    headlines = [
        "🚨 ISSO AQUI NÃO FICA NESSE PREÇO.",
        "💣 OFERTA FORA DO NORMAL.",
        "⚡ ACHADO DO DIA.",
        "🔥 PREÇO ABAIXO DO MERCADO."
    ]

    headline = random.choice(headlines)
    emoji = emojis.get(categoria, "🔥")

    # Texto por categoria
    textos_categoria = {
        "tv": "Perfeito pra quem quer transformar a sala sem pagar absurdo.",
        "cozinha": "Pra quem quer facilitar a rotina e gastar menos tempo na cozinha.",
        "moda": "Ideal pra quem gosta de estilo pagando pouco.",
        "casa": "Resolve organização e espaço sem pesar no bolso.",
        "eletronico": "Tecnologia boa e preço baixo não andam juntos por muito tempo.",
        "geral": "Preço baixo com validação alta não fica disponível muito tempo."
    }

    texto_categoria = textos_categoria.get(categoria)

    copy = f"""
<b>{headline}</b>

{emoji} <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

{texto_categoria}

Mais de {vendas} pessoas já compraram.
Avaliação alta não mente.

⚠️ Produto girando forte.

👇 Se for esperar, vai perder:
<a href="{link}">🛒 COMPRAR AGORA</a>

📲 <a href="{zap}">Copiar para divulgar no WhatsApp</a>
"""

    return copy

# =========================
# FUNÇÕES AUXILIARES
# =========================

def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    nova_query = urlencode(query, doseq=True)
    return urlunparse(parsed._replace(query=nova_query))

def gerar_link_whatsapp(texto):
    return f"https://wa.me/?text={quote(texto)}"

def montar_texto_whatsapp(nome, preco, link):
    texto = f"""🔥 OFERTA SHOPEE

📦 {nome}
💰 R$ {preco}

🛒 Comprar agora:
{link}
"""
    return gerar_link_whatsapp(texto)

# =========================
# SHOPEE API
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
                itemId
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
            data = resp.json()
            produtos = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
            random.shuffle(produtos)
            return produtos

        return []

    except Exception as e:
        logging.error(f"Erro Shopee: {e}")
        return []

# =========================
# ENVIO TELEGRAM
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    ofertas = get_shopee_offers()

    if not ofertas:
        return

    enviados = 0

    for item in ofertas:

        if enviados >= MAX_PRODUTOS_POR_RODADA:
            break

        link_final = aplicar_id_afiliado(item["productLink"])

        if link_final in produtos_enviados:
            continue

        try:
            preco = float(item["priceMin"])
        except:
            continue

        nome_produto = html.escape(item["productName"])
        vendas = item.get("sales", 0)
        avaliacao = item.get("ratingStar", 0)
        comissao = item.get("commissionRate", 0)
        imagem_url = item.get("imageUrl")

        try:
            comissao_formatada = round(float(comissao) * 100, 2)
        except:
            comissao_formatada = 0

        try:
            vendas_formatadas = f"{int(vendas):,}".replace(",", ".")
        except:
            vendas_formatadas = vendas

        zap_link = montar_texto_whatsapp(nome_produto, f"{preco:.2f}", link_final)

        mensagem = gerar_copy(
            nome_produto,
            f"{preco:.2f}",
            vendas_formatadas,
            avaliacao,
            comissao_formatada,
            link_final,
            zap_link
        )

        mensagem += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

        try:
            if imagem_url:
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=imagem_url,
                    caption=mensagem,
                    parse_mode="HTML"
                )
            else:
                await context.bot.send_message(
                    chat_id=CHAT_ID_DESTINO,
                    text=mensagem,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )

            produtos_enviados.add(link_final)
            enviados += 1

            await asyncio.sleep(random.randint(5, 12))

        except Exception as e:
            logging.error(f"Erro envio: {e}")

# =========================
# INICIALIZAÇÃO
# =========================

async def post_init(app):
    app.job_queue.run_repeating(
        send_shopee_offers,
        interval=CHECK_INTERVAL,
        first=10
    )

    logging.info("🤖 Bot Shopee Online!")

if __name__ == "__main__":

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.run_polling(
        poll_interval=60,
        timeout=60,
        drop_pending_updates=True
    )



