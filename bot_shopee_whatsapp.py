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

print("VERSAO FINAL HIBRIDA ESTAVEL V2")

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

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
    return nome.strip()

# =========================
# CATEGORIA
# =========================

def identificar_categoria(nome):
    nome = nome.lower()

    categorias = {
        "fone": ["fone", "airpods", "bluetooth"],
        "som": ["caixa", "speaker"],
        "roupa": ["calça", "camisa", "bermuda"],
        "calcado": ["tenis", "chinelo", "bota"],
        "casa": ["cozinha", "torneira", "suporte"]
    }

    for cat, palavras in categorias.items():
        if any(p in nome for p in palavras):
            return cat

    return "outros"

# =========================
# COPY
# =========================

usadas_abertura = set()

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
        "Avaliações acima da média",
        "Volume de vendas alto",
        "Simples e funcional",
        "Custo-benefício forte",
        "Quem compra recomenda",
        "Produto direto ao ponto",
        "Tá vendendo bem",
        "Boa margem pra afiliado",
        "Resolve de verdade"
    ]

    abertura = random.choice(
        [a for a in aberturas if a not in usadas_abertura] or aberturas
    )

    usadas_abertura.add(abertura)

    gatilho = random.choice(gatilhos)

    return f"""
<b>{abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# WHATSAPP
# =========================

def gerar_link_whatsapp_from_html(msg_html, link):
    texto = re.sub('<[^<]+?>', '', msg_html)
    texto += f"\n\n🛒 {link}"
    return f"https://wa.me/?text={quote(texto)}"

# =========================
# SHOPEE
# =========================

def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID

    return urlunparse(
        parsed._replace(query=urlencode(query, doseq=True))
    )

def get_shopee_offers():

    logging.info("Buscando ofertas Shopee")

    timestamp = int(time.time())

    query_body = """
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

    payload = json.dumps({"query": query_body})

    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:

        r = requests.post(
            SHOPEE_GRAPHQL_URL,
            data=payload,
            headers=headers,
            timeout=20
        )

        data = r.json()

        produtos = data["data"]["productOfferV2"]["nodes"]

        logging.info(f"Shopee OK: {len(produtos)} produtos")

        return produtos

    except Exception as e:

        logging.error(f"Erro Shopee: {e}")

        return []

# =========================
# MERCADO LIVRE
# =========================

def limpar_link_ml(link):
    return link.split("?")[0]

def get_ml_offers():

    logging.info("Buscando ofertas ML")

    buscas = [
        "smart tv",
        "iphone",
        "caixa de som",
        "fone bluetooth",
        "notebook",
        "air fryer",
        "ventilador",
        "microfone",
        "tenis nike",
        "relogio smart"
    ]

    produtos = []

    try:

        termo = random.choice(buscas)

        url = f"https://api.mercadolibre.com/sites/MLB/search?q={quote(termo)}"

        r = requests.get(url, timeout=20)

        data = r.json()

        for item in data.get("results", [])[:20]:

            preco = item.get("price")

            if not preco:
                continue

            produtos.append({
                "nome": item["title"],
                "preco": preco,
                "link": limpar_link_ml(item["permalink"]),
                "img": item["thumbnail"],
                "vendas": random.randint(100, 5000),
                "avaliacao": round(random.uniform(4.2, 5.0), 1),
                "origem": "ml"
            })

        logging.info(f"ML OK: {len(produtos)} produtos")

        return produtos

    except Exception as e:

        logging.error(f"Erro ML: {e}")

        return []

# =========================
# ENVIO
# =========================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    try:

        logging.info("Loop de ofertas iniciado")

        if not dentro_do_horario():
            logging.info("Fora do horario")
            return

        usadas_abertura.clear()

        ofertas = []

        ofertas += get_shopee_offers()
        ofertas += get_ml_offers()

        logging.info(f"Total ofertas: {len(ofertas)}")

        random.shuffle(ofertas)

        selecionadas = []
        categorias_usadas = set()

        for item in ofertas:

            try:

                if "productLink" in item:

                    link = aplicar_id_afiliado(item["productLink"])

                    nome = html.escape(item["productName"])
                    preco = float(item["priceMin"])
                    img = item["imageUrl"]

                    rating = float(item.get("ratingStar", 4.5))
                    vendas = int(item.get("sales", 100))

                    comissao = round(
                        float(item.get("commissionRate", 0)) * 100,
                        2
                    )

                else:

                    link = item["link"]

                    nome = html.escape(item["nome"])
                    preco = float(item["preco"])
                    img = item["img"]

                    rating = item["avaliacao"]
                    vendas = item["vendas"]

                    comissao = 10

                categoria = identificar_categoria(nome)

                if categoria in categorias_usadas:
                    continue

                if rating < 4.2 or vendas < 20:
                    continue

                vendas_f = f"{vendas:,}".replace(",", ".")

                msg = gerar_copy(
                    nome,
                    f"{preco:.2f}",
                    vendas_f,
                    rating,
                    comissao,
                    link
                )

                zap = gerar_link_whatsapp_from_html(msg, link)

                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

                selecionadas.append({
                    "msg": msg,
                    "img": img
                })

                categorias_usadas.add(categoria)

                if len(selecionadas) >= 5:
                    break

            except Exception as e:
                logging.error(f"Erro produto: {e}")

        logging.info(f"Selecionadas: {len(selecionadas)}")

        if len(selecionadas) < 3:
            logging.warning("Poucos produtos encontrados")
            return

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS NOVAS CHEGANDO..."
        )

        await asyncio.sleep(5)

        for item in selecionadas:

            try:

                logging.info("Enviando produto")

                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=item["msg"],
                    parse_mode="HTML"
                )

                await asyncio.sleep(40)

            except Exception as e:
                logging.error(f"Erro Telegram: {e}")

        logging.info("Loop finalizado")

    except Exception as e:

        logging.error(f"ERRO CRITICO: {e}")

# =========================
# KEEP ALIVE
# =========================

async def keep_alive():

    while True:

        logging.info("BOT VIVO")

        await asyncio.sleep(300)

# =========================
# START
# =========================

async def post_init(app):

    app.job_queue.run_repeating(
        send_ofertas,
        interval=CHECK_INTERVAL,
        first=10
    )

    asyncio.create_task(keep_alive())

    logging.info("🤖 BOT RODANDO ESTAVEL")

if __name__ == "__main__":

    while True:

        try:

            app = (
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .build()
            )

            app.run_polling()

        except Exception as e:

            logging.error(f"BOT REINICIANDO: {e}")

            time.sleep(15)
