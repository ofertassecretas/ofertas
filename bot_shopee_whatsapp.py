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
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO SHOPEE V13 ESTAVEL")

TELEGRAM_TOKEN=(os.getenv("TELEGRAM_TOKEN") or "").strip()
SHOPEE_PASSWORD=os.getenv("SHOPEE_PASSWORD","")

CHAT_ID_DESTINO=-1003848415150
SHOPEE_APP_ID="18349740277"
AFILIADO_ID="18349740277"
LINK_GRUPO_OFERTAS="https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL="https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL=7200
PRECO_MIN=20
PRECO_MAX=10000
COMISSAO_MIN=0.08
VENDAS_MIN=50
RATING_MIN=4.5

FUSO_BR=ZoneInfo("America/Sao_Paulo")

ULTIMOS_TITULOS=[]
usados_no_ciclo=set()

KEYWORDS={
"Casa":["smart tv","iphone","xiaomi","notebook","air fryer","alexa","jbl"],
"Motocicleta":["capacete ls2","kit relação cg 160","pneu moto","farol led moto"],
"Moda feminina":["tenis feminino","bolsa feminina"],
"Moda masculina":["tenis masculino","relógio masculino"],
"Maternidade":["carrinho bebê","babá eletrônica"]
}

logging.basicConfig(level=logging.INFO)

def dentro_do_horario():
    agora=datetime.now(FUSO_BR).time()
    return dt_time(5,0)<=agora<=dt_time(21,0)

def normalizar_texto(t):
    return re.sub(r"\s+"," ",t.lower())

def titulo_semelhante(t):
    t=normalizar_texto(t)
    for x in ULTIMOS_TITULOS:
        if SequenceMatcher(None,t,x).ratio()>0.82:
            return True
    return False

def produto_valido(p):

    try:
        titulo=p.get("productName","")
        if titulo_semelhante(titulo):
            return False

        preco=float(p.get("priceMin",0))
        vendas=int(p.get("sales",0))
        rating=float(p.get("ratingStar",0))

        return (
            PRECO_MIN<=preco<=PRECO_MAX and
            vendas>=VENDAS_MIN and
            rating>=RATING_MIN
        )

    except:
        return False

def oferta_score(p):

    vendas=int(p.get("sales",0))
    rating=float(p.get("ratingStar",0))

    return vendas+(rating*100)

def buscar_produtos_da_categoria(categoria):

    keyword=random.choice(KEYWORDS[categoria])
    timestamp=int(time.time())

    query=f"""
    query {{
        productOfferV2(
        sortType:2,
        limit:50,
        keyword:"{keyword}",
        isAMSOffer:true
        ){{
            nodes{{
                productName
                priceMin
                commissionRate
                sales
                ratingStar
                productLink
                offerLink
                imageUrl
            }}
        }}
    }}
    """

    payload=json.dumps({"query":query})

    base=SHOPEE_APP_ID+str(timestamp)+payload+SHOPEE_PASSWORD
    signature=hashlib.sha256(base.encode()).hexdigest()

    headers={
    "Content-Type":"application/json",
    "Authorization":f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    r=requests.post(
        SHOPEE_GRAPHQL_URL,
        data=payload,
        headers=headers,
        timeout=20
    )

    data=r.json()
    return data["data"]["productOfferV2"]["nodes"]

def get_shopee_offers():

    candidatos=[]

    for categoria in KEYWORDS:

        try:

            produtos=buscar_produtos_da_categoria(categoria)

            validos=[p for p in produtos if produto_valido(p)]

            validos.sort(
            key=oferta_score,
            reverse=True
            )

            candidatos.extend(validos[:2])

        except Exception as e:
            logging.error(e)

    return candidatos

def gerar_copy(nome,preco,vendas,link,for_whatsapp=False):

    if for_whatsapp:

        return f"""
🚨 *OFERTA ENCONTRADA*

🔥 *PRODUTO*
{nome}

💰 *PREÇO*
R$ {preco}

🛒 *VENDAS*
{vendas}

⚠️ *Pode subir de preço*

🛒 {link}
"""

    return f"""
🔥 <b>{nome}</b>

💰 <b>R$ {preco}</b>

🛒 <b>{vendas} vendas</b>

<a href="{link}">Comprar agora</a>
"""

async def send_ofertas(context):

    if not dentro_do_horario():
        return

    ofertas=get_shopee_offers()

    for item in ofertas:

        try:

            nome=html.escape(item["productName"])
            preco=item["priceMin"]
            vendas=item["sales"]
            img=item.get("imageUrl","")
            link=item.get("offerLink") or item.get("productLink")

            msg=gerar_copy(
            nome,
            preco,
            vendas,
            link
            )

            if img:

                await context.bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=img,
                caption=msg,
                parse_mode="HTML"
                )

            else:

                await context.bot.send_message(
                chat_id=CHAT_ID_DESTINO,
                text=msg,
                parse_mode="HTML"
                )

            await asyncio.sleep(20)

        except Exception as e:
            logging.error(e)

async def post_init(app):
    app.job_queue.run_repeating(
    send_ofertas,
    interval=CHECK_INTERVAL,
    first=10
    )

if __name__=="__main__":

    app=(
    ApplicationBuilder()
    .token(TELEGRAM_TOKEN)
    .post_init(post_init)
    .build()
    )

    app.run_polling()



        


