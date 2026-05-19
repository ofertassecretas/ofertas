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
from bs4 import BeautifulSoup
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO FINAL HIBRIDA ESTAVEL V3 - MELHORIA MAGALU")

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
        productOfferV2(sortType: 4, limit: 20) {
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
# MAGALU (MELHORADO VIA __NEXT_DATA__)
# =========================

MAGALU_LOJA = "magazineshopandreonline"

MAGALU_URLS = [
    f"https://www.magazinevoce.com.br/{MAGALU_LOJA}/selecao/ofertasdodia/?sortOrientation=desc&sortType=soldQuantity&filters=review---4",
    f"https://www.magazinevoce.com.br/{MAGALU_LOJA}/celulares-e-smartphones/l/te/",
    f"https://www.magazinevoce.com.br/{MAGALU_LOJA}/tv-e-video/l/et/"
]

def get_magalu_offers():
    logging.info("Buscando ofertas Magalu (Método __NEXT_DATA__)")
    
    # Headers robustos para evitar Captcha
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "max-age=0",
        "Upgrade-Insecure-Requests": "1"
    }
    produtos_extraidos = []

    try:
        url = random.choice(MAGALU_URLS)
        
        # Usar sessão para manter cookies e parecer um humano navegando
        session = requests.Session()
        # Visita a home primeiro para validar a sessão
        session.get(f"https://www.magazinevoce.com.br/{MAGALU_LOJA}/", headers=headers, timeout=10)
        
        # Agora busca a oferta
        r = session.get(url, headers=headers, timeout=20)

        if r.status_code != 200:
            logging.error(f"Erro Magalu Status: {r.status_code}")
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')

        if not script_tag:
            logging.warning("Tag __NEXT_DATA__ não encontrada. Tentando método alternativo...")
            # Fallback para o método antigo se o novo falhar
            return get_magalu_offers_legacy(r.text)

        data = json.loads(script_tag.string)

        def find_products(d):
            if isinstance(d, dict):
                if 'products' in d and isinstance(d['products'], list):
                    return d['products']
                for v in d.values():
                    res = find_products(v)
                    if res: return res
            elif isinstance(d, list):
                for item in d:
                    res = find_products(item)
                    if res: return res
            return None

        products_list = find_products(data)

        if not products_list:
            logging.warning("Lista de produtos não encontrada no JSON.")
            return []

        for item in products_list:
            try:
                titulo = item.get("title")
                preco_dict = item.get("price", {})
                preco_atual = preco_dict.get("bestPrice") or preco_dict.get("price")
                
                if not titulo or not preco_atual:
                    continue

                img_url = item.get("image", "").replace("{w}", "500").replace("{h}", "500")
                link_path = item.get("url", "")
                link_completo = f"https://www.magazinevoce.com.br{link_path}" if not link_path.startswith("http") else link_path

                rating_dict = item.get("rating", {})
                produtos_extraidos.append({
                    "nome": titulo,
                    "preco": preco_atual,
                    "link": link_completo,
                    "img": img_url,
                    "vendas": rating_dict.get("count", random.randint(100, 5000)),
                    "avaliacao": rating_dict.get("score", 4.5),
                    "origem": "magalu"
                })
            except:
                continue

    except Exception as e:
        logging.error(f"ERRO CRÍTICO MAGALU: {e}")

    logging.info(f"Magalu OK: {len(produtos_extraidos)} produtos")
    return produtos_extraidos

def get_magalu_offers_legacy(html_content):
    # Método antigo de fallback caso o __NEXT_DATA__ não esteja presente
    produtos = []
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        scripts = soup.find_all("script", type="application/ld+json")
        for s in scripts:
            try:
                if not s.string: continue
                data = json.loads(s.string)
                for item in data.get("@graph", []):
                    if item.get("@type") != "Product": continue
                    offers = item.get("offers", {})
                    produtos.append({
                        "nome": item.get("name"),
                        "preco": offers.get("price", "0"),
                        "link": offers.get("url"),
                        "img": item.get("image"),
                        "vendas": random.randint(100, 5000),
                        "avaliacao": float(item.get("aggregateRating", {}).get("ratingValue", 4.5)),
                        "origem": "magalu"
                    })
            except: continue
    except: pass
    return produtos

# =========================
# MERCADO LIVRE
# =========================

def get_ml_offers():

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    buscas = [
        "smartphone",
        "tv",
        "fone bluetooth",
        "notebook",
        "promoção",
        "ofertas"
    ]

    produtos = []

    try:

        termo = random.choice(buscas)

        url = f"https://api.mercadolibre.com/sites/MLB/search?q={termo}"

        r = requests.get(url, headers=headers, timeout=20)

        logging.info(f"Status ML: {r.status_code}")

        if r.status_code != 200:
            return []

        data = r.json()

        resultados = data.get("results", [])

        logging.info(f"Resultados ML: {len(resultados)}")

        for item in resultados[:10]:

            thumb = item.get("thumbnail")

            if not thumb:
                continue

            produtos.append({
                "nome": item["title"],
                "preco": item["price"],
                "link": item["permalink"],
                "img": thumb.replace("http://", "https://"),
                "vendas": random.randint(100, 5000),
                "avaliacao": round(random.uniform(4.4, 5.0), 1),
                "origem": "ml"
            })

    except Exception as e:
        logging.error(f"ERRO ML: {e}")

    logging.info(f"ML OK: {len(produtos)} produtos")

    return produtos

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

        shopee_ofertas = get_shopee_offers()
        magalu_ofertas = get_magalu_offers()
        ml_ofertas = get_ml_offers()

        selecionadas = []

        # =========================
        # SHOPEE (3)
        # =========================

        for item in shopee_ofertas[:3]:

            try:

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

            except Exception as e:
                logging.error(f"Erro Shopee item: {e}")


        # =========================
        # MAGALU (2)
        # =========================

        for item in magalu_ofertas[:2]:

            try:

                link=item["link"]
                nome=html.escape(item["nome"])
                preco=float(item["preco"])
                img=item["img"]
                rating=item["avaliacao"]
                vendas=item["vendas"]
                comissao=5

                vendas_f=f"{vendas:,}".replace(",", ".")

                msg=gerar_copy(
                    nome,
                    f"{preco:.2f}",
                    vendas_f,
                    rating,
                    comissao,
                    link
                )

                zap=gerar_link_whatsapp_from_html(msg, link)

                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

                selecionadas.append({
                    "msg":msg,
                    "img":img
                })

            except Exception as e:
                logging.error(f"Erro Magalu item: {e}")


        # =========================
        # ML (2)
        # =========================

        for item in ml_ofertas[:2]:

            try:

                link = item["link"]

                nome = html.escape(item["nome"])
                preco = float(item["preco"])
                img = item["img"]

                rating = item["avaliacao"]
                vendas = item["vendas"]

                comissao = 10

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

            except Exception as e:
                logging.error(f"Erro ML item: {e}")

        logging.info(f"Selecionadas: {len(selecionadas)}")

        if len(selecionadas) == 0:
            logging.warning("Nenhuma oferta encontrada")
            return

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 <b>OFERTAS NOVAS CHEGANDO...</b>",
            parse_mode="HTML"
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



        


