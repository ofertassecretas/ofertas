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
from urllib.parse import quote, urljoin
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO FINAL HIBRIDA ESTAVEL V25 - MAGALU NEXT DATA FIX")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

MAGALU_API_KEY = os.getenv("MAGALU_API_KEY")
MAGALU_API_KEY_ID = os.getenv("MAGALU_API_KEY_ID")
MAGALU_API_SECRET = os.getenv("MAGALU_API_SECRET")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

MAGALU_ONELINK_ID = "589508454"
MAGALU_STORE_ID = "07yuzqjf"

ML_LISTA_URL = "https://mercadolivre.com/sec/167xbsR"

CHECK_INTERVAL = 5400
FUSO_BR = ZoneInfo("America/Sao_Paulo")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("debug_bot.txt", encoding="utf-8")
    ]
)

usadas_abertura = set()

CACHE_FILE = "cache_envios.json"
ML_LISTA_CACHE_FILE = "ml_lista_cache.json"

PREMIUM_TERMOS = [
    "Smartphone",
    "Geladeira",
    "Smart TV",
    "Airfryer",
    "Notebook",
    "Lavadora",
    "Fogão",
    "Microondas",
    "Monitor Gamer"
]

MOTOS_MODELOS = [
    "Titan 160",
    "Fazer 250",
    "XRE 300",
    "Biz 125",
    "Twister 250",
    "Factor 150",
    "PCX",
    "Lander 250",
    "CB300",
    "Tornado"
]

MOTOS_PECAS = [
    "Kit Relação",
    "Pneu",
    "Capacete",
    "Jaqueta",
    "Farol",
    "Disco Freio",
    "Kit Cilindro",
    "Bateria",
    "Guidão",
    "Retrovisor"
]

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)

def carregar_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"Falha ao carregar {path}: {e}")
    return default

def salvar_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"Falha ao salvar {path}: {e}")

cache_envios = carregar_json(CACHE_FILE, {"sent": []})

ml_lista_cache = carregar_json(
    ML_LISTA_CACHE_FILE,
    {"items": [], "updated": 0}
)

def cache_ja_enviado(key):
    return key in cache_envios["sent"]

def registrar_enviado(key, max_itens=120):
    cache_envios["sent"].append(key)
    cache_envios["sent"] = cache_envios["sent"][-max_itens:]
    salvar_json(CACHE_FILE, cache_envios)

def gerar_copy(
    nome,
    preco,
    vendas,
    avaliacao,
    comissao,
    link,
    origem="shopee"
):

    prefixos = {
        "shopee": "🟠 SHOPEE",
        "ml": "🟡 MERCADO LIVRE",
        "magalu": "🔵 MAGALU"
    }

    prefixo = prefixos.get(origem, "🔥 OFERTA")

    aberturas = [
        "🚨 Isso aqui não é comum aparecer assim",
        "👀 Achei isso aqui e fui conferir…",
        "🔥 Isso aqui tá com cara de oportunidade",
        "💥 Esse aqui tá chamando atenção de quem compra",
        "🛑 Para tudo e olha isso aqui",
        "🤯 Sério… olha esse achado",
        "⚠️ Isso aqui pode desaparecer rápido",
        "👁️ Pouca gente viu isso ainda"
    ]

    gatilho = random.choice([
        "Preço muito abaixo",
        "Avaliações acima da média",
        "Volume de vendas alto",
        "Custo-benefício forte"
    ])

    abertura = random.choice(
        [a for a in aberturas if a not in usadas_abertura]
        or
        aberturas
    )

    usadas_abertura.add(abertura)

    msg_tg = (
        f"<b>{prefixo} | {abertura}</b>\n\n"
        f"🔥 <b>{nome}</b>\n\n"
        f"{gatilho}\n\n"
        f"💰 <b>R$ {preco}</b>\n"
        f"⭐ {avaliacao} | 🛒 {vendas} vendas\n"
        f"💸 Comissão: <b>{comissao}%</b>\n\n"
        f"⚠️ Pode subir de preço\n\n"
        f"<a href=\"{link}\">🛒 COMPRAR AGORA</a>"
    )

    msg_wa = (
        f"*{prefixo} | {abertura}*\n\n"
        f"🔥 *{nome}*\n\n"
        f"{gatilho}\n\n"
        f"💰 *R$ {preco}*\n"
        f"⭐ {avaliacao} | 🛒 *{vendas} vendas*\n\n"
        f"⚠️ Pode subir de preço\n\n"
        f"🛒 {link}"
    )

    return msg_tg, msg_wa

def gerar_link_whatsapp(msg_wa):
    return "https://wa.me/?text=" + quote(msg_wa.strip())

def get_page(url, timeout=20):

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
    }

    r = requests.get(
        url,
        headers=headers,
        timeout=timeout
    )

    return r.text, r.url

def extract_links(html_text, base_url):

    hrefs = re.findall(
        r'href=["\']([^"\']+)["\']',
        html_text,
        flags=re.I
    )

    out = []

    for href in hrefs:

        h = href.strip()

        if h.startswith("#"):
            continue

        if h.startswith("javascript:"):
            continue

        if h.startswith("mailto:"):
            continue

        full = urljoin(base_url, h)

        low = full.lower()

        if any(x in low for x in [
            "mercadolivre.com",
            "mercadolivre.com.br",
            "/p/",
            "/produto/",
            "/dp/"
        ]):

            if full not in out:
                out.append(full)

    return out

def get_shopee_offers():

    logging.info("Buscando Shopee...")

    timestamp = int(time.time())

    query_body = """
    query {
        productOfferV2(sortType: 2, limit: 10) {
            nodes {
                productName,
                priceMin,
                commissionRate,
                sales,
                ratingStar,
                productLink,
                imageUrl
            }
        }
    }
    """

    payload = json.dumps({"query": query_body})

    base = (
        SHOPEE_APP_ID
        + str(timestamp)
        + payload
        + SHOPEE_PASSWORD
    )

    signature = hashlib.sha256(
        base.encode()
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": (
            f"SHA256 Credential={SHOPEE_APP_ID}, "
            f"Timestamp={timestamp}, "
            f"Signature={signature}"
        )
    }

    try:

        r = requests.post(
            SHOPEE_GRAPHQL_URL,
            data=payload,
            headers=headers,
            timeout=20
        )

        nodes = (
            r.json()
            .get("data", {})
            .get("productOfferV2", {})
            .get("nodes", [])
        )

        logging.info(
            f"Shopee itens brutos: {len(nodes)}"
        )

        return nodes

    except Exception as e:

        logging.warning(f"Shopee falhou: {e}")

        return []

def refresh_ml_cache():

    try:

        html_text, final_url = get_page(
            ML_LISTA_URL,
            timeout=20
        )

        links = extract_links(
            html_text,
            final_url
        )

        logging.info(
            f"Links de ML encontrados na lista: {len(links)}"
        )

        items = []

        for l in links:

            if "mercadolivre" not in l.lower():
                continue

            item_id = hashlib.md5(
                l.encode()
            ).hexdigest()

            items.append({
                "id": item_id,
                "nome": "Produto da sua lista ML",
                "preco": "0.00",
                "link": l,
                "img": "",
                "vendas": random.randint(50, 2000),
                "avaliacao": round(
                    random.uniform(4.4, 5.0),
                    1
                ),
                "origem": "ml",
                "comissao": 5
            })

        ml_lista_cache["items"] = items
        ml_lista_cache["updated"] = int(time.time())

        salvar_json(
            ML_LISTA_CACHE_FILE,
            ml_lista_cache
        )

    except Exception as e:

        logging.warning(
            f"Falha ao atualizar cache ML: {e}"
        )

def get_ml_from_cache():

    if (
        not ml_lista_cache["items"]
        or
        (
            int(time.time())
            - ml_lista_cache.get("updated", 0)
            > 21600
        )
    ):
        refresh_ml_cache()

    items = ml_lista_cache.get("items", [])

    random.shuffle(items)

    validos = [
        item for item in items
        if not cache_ja_enviado("ml_" + item["id"])
    ]

    logging.info(
        f"Itens válidos de ML no cache: {len(validos)}"
    )

    return validos

def get_ml_direct(termo):

    offset = random.randint(0, 40)

    logging.info(
        f"Buscando ML Direto: {termo} (Offset: {offset})"
    )

    try:

        url = (
            "https://api.mercadolibre.com/sites/MLB/search"
            f"?q={quote(termo)}&limit=10&offset={offset}"
        )

        r = requests.get(url, timeout=15)

        items = r.json().get("results", [])

        res = []

        for item in items:

            try:

                link = item.get("permalink")
                nome = item.get("title")
                preco = item.get("price")

                if not link or not nome or preco is None:
                    continue

                img = item.get("thumbnail") or ""

                res.append({
                    "id": str(
                        item.get(
                            "id",
                            hashlib.md5(
                                link.encode()
                            ).hexdigest()
                        )
                    ),
                    "nome": nome,
                    "preco": f"{float(preco):.2f}",
                    "link": link,
                    "img": img,
                    "vendas": int(
                        item.get(
                            "sold_quantity",
                            random.randint(50, 500)
                        )
                    ),
                    "avaliacao": round(
                        random.uniform(4.4, 5.0),
                        1
                    ),
                    "origem": "ml",
                    "comissao": 5
                })

            except:
                continue

        logging.info(
            f"ML direto itens válidos: {len(res)}"
        )

        return res

    except Exception as e:

        logging.warning(
            f"ML direto falhou: {e}"
        )

        return []

def gerar_link_magalu(produto_url):

    try:

        return (
            f"https://magazineluiza.onelink.me/"
            f"{MAGALU_ONELINK_ID}/"
            f"{MAGALU_STORE_ID}"
            f"?af_dp={quote(produto_url)}"
        )

    except:

        return produto_url

def get_magalu_headers():

    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.magazineluiza.com.br/",
        "Origin": "https://www.magazineluiza.com.br",
        "X-API-KEY": MAGALU_API_KEY or "",
        "X-API-KEY-ID": MAGALU_API_KEY_ID or "",
        "X-API-SECRET": MAGALU_API_SECRET or "",
    }

def get_magalu_direct(termo):

    logging.info(
        f"Buscando API Magalu: {termo}"
    )

    endpoints = [
        f"https://www.magazineluiza.com.br/busca/{quote(termo)}/",
        f"https://www.magazinevoce.com.br/magazineshopandreonline/busca/{quote(termo)}/"
    ]

    produtos = []

    headers = get_magalu_headers()

    for url in endpoints:

        try:

            r = requests.get(
                url,
                headers=headers,
                timeout=20
            )

            html_text = r.text

            json_match = re.search(
                r'window\.__NEXT_DATA__\s*=\s*(\{.*?\})\s*</script>',
                html_text,
                re.S
            )

            if not json_match:

                logging.info(
                    "NEXT_DATA não encontrado"
                )

                continue

            try:

                data = json.loads(
                    json_match.group(1)
                )

            except Exception as e:

                logging.warning(
                    f"Erro lendo NEXT_DATA: {e}"
                )

                continue

            produtos_json = []

            def procurar_produtos(obj):

                if isinstance(obj, dict):

                    if (
                        "title" in obj
                        and
                        (
                            "price" in obj
                            or
                            "bestPrice" in obj
                            or
                            "salesPrice" in obj
                        )
                    ):

                        produtos_json.append(obj)

                    for v in obj.values():
                        procurar_produtos(v)

                elif isinstance(obj, list):

                    for i in obj:
                        procurar_produtos(i)

            procurar_produtos(data)

            logging.info(
                f"Produtos JSON encontrados: {len(produtos_json)}"
            )

            for item in produtos_json[:15]:

                try:

                    nome = (
                        item.get("title")
                        or
                        item.get("productTitle")
                    )

                    preco = (
                        item.get("bestPrice")
                        or
                        item.get("price")
                        or
                        item.get("salesPrice")
                    )

                    path = (
                        item.get("url")
                        or
                        item.get("path")
                    )

                    imagem = (
                        item.get("image")
                        or
                        item.get("imageUrl")
                        or
                        ""
                    )

                    if not nome or not preco or not path:
                        continue

                    if not str(path).startswith("http"):

                        produto_url = (
                            "https://www.magazineluiza.com.br"
                            + str(path)
                        )

                    else:

                        produto_url = path

                    link_afiliado = gerar_link_magalu(
                        produto_url
                    )

                    produto_id = hashlib.md5(
                        produto_url.encode()
                    ).hexdigest()

                    produtos.append({
                        "id": produto_id,
                        "nome": nome,
                        "preco": str(preco).replace(".", ","),
                        "link": link_afiliado,
                        "img": imagem,
                        "vendas": random.randint(100, 5000),
                        "avaliacao": round(
                            random.uniform(4.5, 5.0),
                            1
                        ),
                        "origem": "magalu",
                        "comissao": random.randint(3, 8)
                    })

                except Exception as e:

                    logging.warning(
                        f"Erro item Magalu: {e}"
                    )

            if produtos:
                break

        except Exception as e:

            logging.warning(
                f"Erro endpoint Magalu: {e}"
            )

    logging.info(
        f"Produtos Magalu válidos: {len(produtos)}"
    )

    return produtos

def escolher_item_sem_repetir(
    items,
    prefixo_cache
):

    if not items:
        return None

    for item in items:

        key = (
            prefixo_cache
            + "_"
            + item.get(
                "id",
                hashlib.md5(
                    item["link"].encode()
                ).hexdigest()
            )
        )

        if not cache_ja_enviado(key):

            registrar_enviado(key)

            return item

    return None

async def send_ofertas(
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        if not dentro_do_horario():

            logging.info(
                "Fora do horario permitido."
            )

            return

        usadas_abertura.clear()

        total_lista = []

        shopee = get_shopee_offers()

        shopee_validos = 0

        for i in shopee[:2]:

            try:

                l = i["productLink"]

                if "af_siteid" not in l:
                    l = f"{l}?af_siteid={AFILIADO_ID}"

                comis = round(
                    float(
                        i.get(
                            "commissionRate",
                            0
                        )
                    ) * 100,
                    2
                )

                msg_tg, msg_wa = gerar_copy(
                    html.escape(i["productName"]),
                    f"{float(i['priceMin']):.2f}",
                    f"{int(i.get('sales', 100)):,}".replace(",", "."),
                    float(i.get("ratingStar", 4.5)),
                    comis,
                    l,
                    "shopee"
                )

                total_lista.append({
                    "msg_tg": msg_tg,
                    "msg_wa": msg_wa,
                    "img": i["imageUrl"],
                    "link": l
                })

                shopee_validos += 1

            except Exception as e:

                logging.warning(
                    f"Shopee item inválido: {e}"
                )

        logging.info(
            f"Shopee itens válidos: {shopee_validos}"
        )

        termo_magalu = random.choice(
            PREMIUM_TERMOS
        )

        magalu_items = get_magalu_direct(
            termo_magalu
        )

        if not magalu_items:

            termo_magalu = random.choice([
                "smart tv",
                "iphone",
                "notebook",
                "geladeira",
                "air fryer"
            ])

            magalu_items = get_magalu_direct(
                termo_magalu
            )

        logging.info(
            f"Magalu candidatos: {len(magalu_items)}"
        )

        if magalu_items:

            i = escolher_item_sem_repetir(
                magalu_items,
                "magalu"
            )

            if (
                i
                and
                i["preco"] != "0.00"
                and
                i["nome"]
                and
                i["link"]
            ):

                msg_tg, msg_wa = gerar_copy(
                    html.escape(i["nome"]),
                    i["preco"],
                    i["vendas"],
                    i["avaliacao"],
                    i["comissao"],
                    i["link"],
                    "magalu"
                )

                total_lista.append({
                    "msg_tg": msg_tg,
                    "msg_wa": msg_wa,
                    "img": i.get("img", ""),
                    "link": i["link"]
                })

                logging.info(
                    "Magalu adicionado ao envio."
                )

        ml_items = get_ml_from_cache()

        if not ml_items:

            termo_moto = (
                f"{random.choice(MOTOS_PECAS)} "
                f"{random.choice(MOTOS_MODELOS)}"
            )

            ml_items = get_ml_direct(
                termo_moto
            )

        if not ml_items:

            termo_ml_p = random.choice(
                PREMIUM_TERMOS
            )

            ml_items = get_ml_direct(
                termo_ml_p
            )

        logging.info(
            f"ML candidatos após fallback: {len(ml_items)}"
        )

        if ml_items:

            i = escolher_item_sem_repetir(
                ml_items,
                "ml"
            )

            if (
                i
                and
                i["preco"] != "0.00"
                and
                i["nome"]
                and
                i["link"]
            ):

                msg_tg, msg_wa = gerar_copy(
                    html.escape(i["nome"]),
                    i["preco"],
                    i["vendas"],
                    i["avaliacao"],
                    i["comissao"],
                    i["link"],
                    "ml"
                )

                total_lista.append({
                    "msg_tg": msg_tg,
                    "msg_wa": msg_wa,
                    "img": i.get("img", ""),
                    "link": i["link"]
                })

                logging.info(
                    "ML adicionado ao envio."
                )

        logging.info(
            f"total_lista final: {len(total_lista)}"
        )

        if not total_lista:

            logging.info(
                "Nenhuma oferta válida encontrada nesta rodada."
            )

            return

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS NOVAS CHEGANDO..."
        )

        await asyncio.sleep(5)

        for item in total_lista:

            try:

                zap_link = gerar_link_whatsapp(
                    item["msg_wa"]
                )

                full_msg = (
                    item["msg_tg"]
                    +
                    f'\n📲 <a href="{zap_link}">Compartilhar no WhatsApp</a>\n'
                    '━━━━━━━━━━━━━━━\n'
                    '📢 <b>Ofertas Secretas</b>'
                )

                if item["img"]:

                    await context.bot.send_photo(
                        chat_id=CHAT_ID_DESTINO,
                        photo=item["img"],
                        caption=full_msg,
                        parse_mode="HTML"
                    )

                else:

                    await context.bot.send_message(
                        chat_id=CHAT_ID_DESTINO,
                        text=full_msg,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )

                await asyncio.sleep(45)

            except Exception as e:

                logging.error(
                    f"Erro ao enviar item: {e}"
                )

    except Exception as e:

        logging.error(
            f"ERRO CRITICO: {e}"
        )

async def post_init(app):

    app.job_queue.run_repeating(
        send_ofertas,
        interval=CHECK_INTERVAL,
        first=10
    )

    logging.info(
        "🤖 BOT V25 ATIVADO"
    )

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

            logging.error(
                f"Falha geral no app: {e}"
            )

            time.sleep(15)
        


