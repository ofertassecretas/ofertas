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

print("VERSAO SHOPEE V12 ANTI-REPETICAO E MOTO FORTE")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"
CHECK_INTERVAL = 5400

PRECO_MIN = 20.0
PRECO_MAX = 10000.0
COMISSAO_MIN = 0.08
VENDAS_MIN = 10
RATING_MIN = 4.0

PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "não compre", "nao compre", "produto teste", "exemplo", "dummy",
    "vela led", "vela decorativa", "decorativa", "decoração", "casamento", "festa"
]

NICHOS_CICLO = ["Casa", "Moda feminina", "Moda masculina", "Maternidade", "Motocicleta"]

KEYWORDS = {
    "Casa": [
        "organizador premium", "kit cozinha inox", "aspirador portátil", "ferramenta elétrica",
        "air fryer", "cafeteira elétrica", "liquidificador potente", "panela elétrica",
        "secador de cabelo profissional", "torradeira inox"
    ],
    "Moda feminina": [
        "vestido feminino", "blusa feminina premium", "calça feminina", "tenis feminino",
        "bolsa feminina", "kit moda feminina", "conjunto feminino", "sapato feminino"
    ],
    "Moda masculina": [
        "camisa masculina", "tenis masculino", "calça masculina", "relógio masculino",
        "mochila masculina", "carteira masculina", "kit moda masculina", "sapato masculino"
    ],
    "Maternidade": [
        "carrinho bebê", "cadeirinha bebê", "kit enxoval bebê", "babá eletrônica",
        "cadeira alimentação bebê", "brinquedo educativo bebê", "berço portátil", "mochila maternidade"
    ],
    "Motocicleta": [
        "amortecedor moto", "freio moto", "pastilha freio moto", "disco freio moto", "pneu moto",
        "kit relação moto", "embreagem moto", "injeção moto", "painel moto", "farol moto",
        "seta moto", "retrovisor moto", "carenagem moto", "motor moto", "bateria moto",
        "stator moto", "regulador moto", "bobina moto", "relé moto", "sensor moto"
    ]
}

ULTIMAS_BUSCAS_SHOPEE = []
ULTIMOS_TITULOS = []
usadas_abertura = set()
usados_no_ciclo = set()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

CHAMADAS_ACAO = [
    "👇 CORRE QUE TÁ ACABANDO!",
    "⚡ CLIQUE ANTES QUE AUMENTE!",
    "🚀 ESTOQUE LIMITADO - AGORA!",
    "💥 MELHOR PREÇO DO ANO!",
    "🎯 COMPRE ANTES DOS OUTROS!",
    "🔥 VOOU DAS PRATELEIRAS!",
    "⏰ PROMOÇÃO ACABA HOJE!",
    "💰 ECONOMIA REAL - CORRE!",
    "⭐ OFERTA QUENTE AGORA!",
    "🛒 NÃO DEIXA ESCAPAR!"
]


def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(21, 0)


def escolher_categorias_do_ciclo():
    return random.sample(NICHOS_CICLO, k=len(NICHOS_CICLO))


def normalizar_texto(txt):
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt


def tem_bloqueio(titulo):
    t = normalizar_texto(titulo)
    return any(p in t for p in PALAVRAS_BLOQUEIO)


def titulo_semelhante(titulo):
    t = normalizar_texto(titulo)
    for prev in ULTIMOS_TITULOS:
        ratio = SequenceMatcher(None, t, prev).ratio()
        if ratio >= 0.82:
            return True
    return False


def shop_type_score(shop_type):
    try:
        if not shop_type:
            return 0
        if 1 in shop_type:
            return 3
        if 4 in shop_type:
            return 2
        if 2 in shop_type:
            return 1
        return 0
    except Exception:
        return 0


def oferta_score(p):
    try:
        vendas = int(p.get("sales", 0) or 0)
        rating = float(p.get("ratingStar", 0) or 0)
        comissao = float(p.get("commissionRate", 0) or 0)
        preco = float(p.get("priceMin", 0) or 0)
        st = p.get("shopType", [])
        nome = str(p.get("productName", "")).lower()

        score = 0
        score += min(vendas / 8, 25)
        score += rating * 2
        score += comissao * 100
        score += shop_type_score(st)
        if 50 <= preco <= 5000:
            score += 6
        if "moto" in nome or "bebe" in nome or "bebê" in nome:
            score += 2
        return score
    except Exception:
        return 0


def produto_valido(p):
    try:
        titulo = str(p.get("productName", "")).strip()
        link = str(p.get("offerLink") or p.get("productLink") or "").strip()
        preco_min = float(p.get("priceMin", 0) or 0)
        comissao = float(p.get("commissionRate", 0) or 0)
        vendas = int(p.get("sales", 0) or 0)
        rating = float(p.get("ratingStar", 0) or 0)

        if not titulo or not link:
            return False
        if tem_bloqueio(titulo):
            return False
        if titulo_semelhante(titulo):
            return False
        if preco_min < PRECO_MIN or preco_min > PRECO_MAX:
            return False
        if comissao < COMISSAO_MIN:
            return False
        if vendas < VENDAS_MIN:
            return False
        if rating and rating < RATING_MIN:
            return False
        if link in ULTIMAS_BUSCAS_SHOPEE or link in usados_no_ciclo:
            return False

        return True
    except Exception:
        return False


def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, for_whatsapp=False):
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

    chamada_grupo = f"📢 Quer mais ofertas assim? Entre no nosso grupo: {LINK_GRUPO_OFERTAS}"
    chamada_acao = random.choice(CHAMADAS_ACAO)
    abertura = random.choice([a for a in aberturas if a not in usadas_abertura] or aberturas)
    usadas_abertura.add(abertura)
    gatilho = random.choice(gatilhos)

    if for_whatsapp:
        return f"""{abertura}

*🔥 {nome}*

{gatilho}

{chamada_acao}

*💰 R$ {preco}*
*⭐ {avaliacao} | 🛒 {vendas} vendas*

⚠️ Pode subir de preço

🛒 COMPRAR AGORA: {link}
{chamada_grupo}
"""
    return f"""{abertura}

🔥 <b>{nome}</b>

{gatilho}

{chamada_acao}

💰 <b>R$ {preco}</b>
⭐ <b>{avaliacao} | {vendas} vendas</b>
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>
<a href="{LINK_GRUPO_OFERTAS}">📲 Entrar no grupo de ofertas</a>
"""


def gerar_link_whatsapp_from_html(msg_html):
    texto = re.sub(r"<[^>]+>", "", msg_html)
    return f"https://wa.me/?text={quote(texto)}"


def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


def buscar_produtos_da_categoria(categoria_selecionada):
    palavra_chave = random.choice(KEYWORDS[categoria_selecionada])
    logging.info(f"Buscando na categoria: {categoria_selecionada} com palavra-chave: {palavra_chave}")

    timestamp = int(time.time())

    query_body = f'''
    query {{
        productOfferV2(sortType: 2, limit: 50, keyword: "{palavra_chave}", isAMSOffer: true) {{
            nodes {{
                productName
                priceMin
                priceMax
                commissionRate
                sales
                ratingStar
                productLink
                offerLink
                imageUrl
                shopType
            }}
        }}
    }}
    '''

    payload = json.dumps({"query": query_body})
    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
    data = r.json()
    return data["data"]["productOfferV2"]["nodes"]


def get_shopee_offers():
    global ULTIMAS_BUSCAS_SHOPEE, ULTIMOS_TITULOS, usados_no_ciclo

    logging.info("Buscando ofertas Shopee")
    usados_no_ciclo = set()
    categorias_ciclo = escolher_categorias_do_ciclo()
    candidatos = []

    for categoria_selecionada in categorias_ciclo:
        try:
            produtos_brutos = buscar_produtos_da_categoria(categoria_selecionada)
            filtrados = [p for p in produtos_brutos if produto_valido(p)]
            filtrados.sort(key=oferta_score, reverse=True)

            if filtrados:
                escolhido = filtrados[0]
                link = escolhido.get("offerLink") or escolhido.get("productLink")
                candidatos.append(escolhido)
                ULTIMAS_BUSCAS_SHOPEE.append(link)
                usados_no_ciclo.add(link)
                ULTIMOS_TITULOS.append(normalizar_texto(escolhido["productName"]))
                if len(ULTIMAS_BUSCAS_SHOPEE) > 300:
                    ULTIMAS_BUSCAS_SHOPEE.pop(0)
                if len(ULTIMOS_TITULOS) > 150:
                    ULTIMOS_TITULOS.pop(0)

        except Exception as e:
            logging.error(f"Erro na categoria {categoria_selecionada}: {e}")

    tentativas_extra = 0
    while len(candidatos) < 6 and tentativas_extra < 24:
        tentativas_extra += 1
        categoria_extra = random.choice(list(KEYWORDS.keys()))
        try:
            produtos_brutos = buscar_produtos_da_categoria(categoria_extra)
            filtrados = [p for p in produtos_brutos if produto_valido(p)]
            filtrados.sort(key=oferta_score, reverse=True)

            if filtrados:
                escolhido = filtrados[0]
                link = escolhido.get("offerLink") or escolhido.get("productLink")
                if link not in usados_no_ciclo and link not in ULTIMAS_BUSCAS_SHOPEE:
                    candidatos.append(escolhido)
                    ULTIMAS_BUSCAS_SHOPEE.append(link)
                    usados_no_ciclo.add(link)
                    ULTIMOS_TITULOS.append(normalizar_texto(escolhido["productName"]))
                    if len(ULTIMAS_BUSCAS_SHOPEE) > 300:
                        ULTIMAS_BUSCAS_SHOPEE.pop(0)
                    if len(ULTIMOS_TITULOS) > 150:
                        ULTIMOS_TITULOS.pop(0)

        except Exception as e:
            logging.error(f"Erro extra na categoria {categoria_extra}: {e}")

    candidatos.sort(key=oferta_score, reverse=True)
    logging.info(f"Shopee OK: {len(candidatos[:6])} produtos únicos para envio")
    return candidatos[:6]


async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        logging.info("Loop de ofertas iniciado")

        if not dentro_do_horario():
            logging.info("Fora do horario")
            return

        usadas_abertura.clear()
        shopee_ofertas = get_shopee_offers()
        selecionadas = []

        for item in shopee_ofertas[:6]:
            try:
                link_base = item.get("offerLink") or item.get("productLink")
                link = aplicar_id_afiliado(link_base)
                nome = html.escape(item["productName"])
                preco = float(item["priceMin"])
                img = item["imageUrl"]

                rating = float(item.get("ratingStar", 4.5))
                vendas = int(item.get("sales", 100))
                comissao = round(float(item.get("commissionRate", 0)) * 100, 2)

                vendas_f = f"{vendas:,}".replace(",", ".")
                msg = gerar_copy(nome, f"{preco:.2f}", vendas_f, rating, comissao, link, for_whatsapp=False)

                zap_msg = gerar_copy(nome, f"{preco:.2f}", vendas_f, rating, 0, link, for_whatsapp=True)
                zap = gerar_link_whatsapp_from_html(zap_msg)
                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

                selecionadas.append({"msg": msg, "img": img})

            except Exception as e:
                logging.error(f"Erro Shopee item: {e}")

        logging.info(f"Selecionadas: {len(selecionadas)}")

        if not selecionadas:
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


async def keep_alive():
    while True:
        logging.info("BOT VIVO")
        await asyncio.sleep(300)


async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTAVEL")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"ERRO TELEGRAM: {context.error}")


if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN ausente")

    while True:
        try:
            app = (
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .build()
            )
            app.add_error_handler(error_handler)
            app.run_polling(allowed_updates=None)
        except Exception as e:
            logging.error(f"BOT REINICIANDO: {e}")
            time.sleep(15)



        


