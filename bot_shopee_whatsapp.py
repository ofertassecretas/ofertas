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

print("VERSAO SHOPEE V8 CATEGORIAS")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"
CHECK_INTERVAL = 5400

CATEGORIAS = {
    "Casa": [
        "decoração casa", "utensílios cozinha", "organização casa", "eletrônicos casa", "cama mesa banho"
    ],
    "Moda feminina": [
        "roupa feminina", "vestido feminino", "blusa feminina", "calçado feminino", "acessórios femininos"
    ],
    "Moda masculina": [
        "roupa masculina", "camiseta masculina", "bermuda masculina", "calçado masculino", "acessórios masculinos"
    ],
    "Maternidade": [
        "roupa bebê", "brinquedos bebê", "produtos higiene bebê", "carrinho bebê", "quarto bebê"
    ],
    "Motocicleta": [
        "luvas moto", "jaquetas moto", "kit relação moto", "cabos moto", "kit embreagem moto",
        "pneus moto", "kit freio a disco moto", "guidão moto", "rodas moto", "raios moto",
        "kit pastilhas de freios moto", "pinças de freio moto", "burrinho de freio moto", "caixa direção moto",
        "painel moto", "bombas combustivel moto", "refil bomba combustivel moto", "velas iridium moto",
        "chave ignição moto", "manoplas moto", "kit motor moto", "vacinas pneu moto", "reparo pneu moto",
        "carenagens moto", "tanques moto", "chave luz moto", "manicotos moto", "filtro de ar moto",
        "filtro de combustivel moto", "boia de tanque moto", "aros moto", "coluna direção moto",
        "bacalhau moto", "aba tanque moto", "tranca moto", "setas moto", "estator moto",
        "chicote principal moto", "cdi moto", "carburador moto", "sensor de lenta moto", "tbi moto",
        "corpo de injeção moto", "sensor tps moto", "correia moto", "corrente comando moto",
        "honda biz peças", "pop 100 peças", "cg 125 peças", "cg 150 peças", "cg 160 peças",
        "bros 150 peças", "bros 160 peças", "fazer 150 peças", "fazer 250 peças", "lander peças",
        "cb 250 peças", "cb 300 peças", "crosser 150 peças", "pcx peças", "tornado peças",
        "saara 300 peças", "twister 250 peças", "twister 300 peças", "xre 190 peças", "xre 300 peças"
    ]
}

NICHOS_CICLO = ["Casa", "Moda feminina", "Moda masculina", "Maternidade", "Motocicleta"]

ULTIMA_CATEGORIA_ENVIADA = None
ULTIMAS_BUSCAS_SHOPEE = []
usadas_abertura = set()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

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

🔥 {nome}

{gatilho}

{chamada_acao}

💰 R$ {preco}
⭐ {avaliacao} | 🛒 {vendas} vendas

⚠️ Pode subir de preço

🛒 COMPRAR AGORA: {link}
{chamada_grupo}
"""
    else:
        return f"""<b>{abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

{chamada_acao}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
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
    palavra_chave = random.choice(CATEGORIAS[categoria_selecionada])
    logging.info(f"Buscando na categoria: {categoria_selecionada} com palavra-chave: {palavra_chave}")

    timestamp = int(time.time())

    query_body = f'''
    query {{
        productOfferV2(sortType: 4, limit: 30, keyword: "{palavra_chave}") {{
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
    '''

    payload = json.dumps({"query": query_body})
    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    r = requests.post(
        SHOPEE_GRAPHQL_URL,
        data=payload,
        headers=headers,
        timeout=20
    )

    data = r.json()
    return data["data"]["productOfferV2"]["nodes"]


def get_shopee_offers():
    global ULTIMAS_BUSCAS_SHOPEE

    logging.info("Buscando ofertas Shopee")
    categorias_ciclo = escolher_categorias_do_ciclo()
    produtos_gerados = []

    for categoria_selecionada in categorias_ciclo:
        try:
            produtos_brutos = buscar_produtos_da_categoria(categoria_selecionada)

            escolhido = None
            for p in produtos_brutos:
                if p["productLink"] not in ULTIMAS_BUSCAS_SHOPEE:
                    escolhido = p
                    break

            if escolhido:
                produtos_gerados.append(escolhido)
                ULTIMAS_BUSCAS_SHOPEE.append(escolhido["productLink"])
                if len(ULTIMAS_BUSCAS_SHOPEE) > 50:
                    ULTIMAS_BUSCAS_SHOPEE.pop(0)

        except Exception as e:
            logging.error(f"Erro na categoria {categoria_selecionada}: {e}")

    while len(produtos_gerados) < 6:
        categoria_extra = random.choice(list(CATEGORIAS.keys()))
        try:
            produtos_brutos = buscar_produtos_da_categoria(categoria_extra)

            escolhido = None
            for p in produtos_brutos:
                if p["productLink"] not in ULTIMAS_BUSCAS_SHOPEE:
                    escolhido = p
                    break

            if escolhido:
                produtos_gerados.append(escolhido)
                ULTIMAS_BUSCAS_SHOPEE.append(escolhido["productLink"])
                if len(ULTIMAS_BUSCAS_SHOPEE) > 50:
                    ULTIMAS_BUSCAS_SHOPEE.pop(0)

        except Exception as e:
            logging.error(f"Erro extra na categoria {categoria_extra}: {e}")

        if len(produtos_gerados) >= 6:
            break

    logging.info(f"Shopee OK: {len(produtos_gerados)} produtos únicos para envio")
    return produtos_gerados[:6]


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
                link = aplicar_id_afiliado(item["productLink"])
                nome = html.escape(item["productName"])
                preco = float(item["priceMin"])
                img = item["imageUrl"]

                rating = float(item.get("ratingStar", 4.5))
                vendas = int(item.get("sales", 100))
                comissao = round(float(item.get("commissionRate", 0)) * 100, 2)

                vendas_f = f"{vendas:,}".replace(",", ".")

                msg = gerar_copy(
                    nome,
                    f"{preco:.2f}",
                    vendas_f,
                    rating,
                    comissao,
                    link,
                    for_whatsapp=False
                )

                zap_msg = gerar_copy(
                    nome,
                    f"{preco:.2f}",
                    vendas_f,
                    rating,
                    0,
                    link,
                    for_whatsapp=True
                )

                zap = gerar_link_whatsapp_from_html(zap_msg)
                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

                selecionadas.append({
                    "msg": msg,
                    "img": img
                })

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
    app.job_queue.run_repeating(
        send_ofertas,
        interval=CHECK_INTERVAL,
        first=10
    )
    asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTAVEL")


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
            app.run_polling()

        except Exception as e:
            logging.error(f"BOT REINICIANDO: {e}")
            time.sleep(15)




        


