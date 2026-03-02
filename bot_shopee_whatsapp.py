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
# COPY MAIS PSICOLÓGICA
# =========================

COPYS = [

"""🚨 <b>VOCÊ NÃO VAI VER ESSE PREÇO DUAS VEZES.</b>

📦 <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

Isso aqui já tem validação pesada.
Quem comprou, aprovou.

⚠️ Produto girando forte.
Preço baixo + venda alta não ficam juntos por muito tempo.

👇 Quem clicar primeiro paga esse valor:
<a href="{link}">🔥 GARANTIR AGORA</a>

📲 <a href="{zap}">Enviar no WhatsApp</a>
""",

"""💣 <b>PREÇO FORA DO PADRÃO.</b>

📦 <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

Mais de {vendas} pessoas já confiaram.
Avaliação alta não mente.

Esse tipo de oferta corrige rápido.

👇 Depois que ajustar, não adianta reclamar:
<a href="{link}">🛒 COMPRAR AGORA</a>

📲 <a href="{zap}">Enviar no WhatsApp</a>
"""
]

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

        # 🔥 comissão x100
        try:
            comissao_formatada = round(float(comissao) * 100, 2)
        except:
            comissao_formatada = 0

        # 🔥 formatar vendas (4.684)
        try:
            vendas_formatadas = f"{int(vendas):,}".replace(",", ".")
        except:
            vendas_formatadas = vendas

        zap_link = montar_texto_whatsapp(nome_produto, f"{preco:.2f}", link_final)

        copy_escolhida = random.choice(COPYS)

        mensagem = copy_escolhida.format(
            nome=nome_produto,
            preco=f"{preco:.2f}",
            vendas=vendas_formatadas,
            avaliacao=avaliacao,
            comissao=comissao_formatada,
            link=link_final,
            zap=zap_link
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



