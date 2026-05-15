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
from urllib.parse import quote, urljoin, urlparse
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO FINAL HIBRIDA ESTAVEL V19 - CACHE + LISTA ML + LOJA MAGALU")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

MAGALU_ONELINK_ID = "589508454"
MAGALU_STORE_ID = "07yuzqjf"
MAGALU_LOJA_URL = "https://www.magazinevoce.com.br/magazineshopandreonline/"

ML_LISTA_URL = "https://mercadolivre.com/sec/167xbsR"

CHECK_INTERVAL = 5400
FUSO_BR = ZoneInfo("America/Sao_Paulo")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

usadas_abertura = set()

CACHE_FILE = "cache_envios.json"
ML_LISTA_CACHE_FILE = "ml_lista_cache.json"
MAGALU_CACHE_FILE = "magalu_cache.json"

PREMIUM_TERMOS = [
    "Smartphone", "Geladeira", "Smart TV", "Airfryer", "Notebook",
    "Lavadora", "Fogão", "Microondas", "Monitor Gamer"
]

MOTOS_MODELOS = [
    "Titan 160", "Fazer 250", "XRE 300", "Biz 125", "Twister 250",
    "Factor 150", "PCX", "Lander 250", "CB300", "Tornado"
]

MOTOS_PECAS = [
    "Kit Relação", "Pneu", "Capacete", "Jaqueta", "Farol",
    "Disco Freio", "Kit Cilindro", "Bateria", "Guidão", "Retrovisor"
]

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(22, 0)

def carregar_json(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default

def salvar_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except:
        pass

cache_envios = carregar_json(CACHE_FILE, {"sent": []})
ml_lista_cache = carregar_json(ML_LISTA_CACHE_FILE, {"items": [], "updated": 0})
magalu_cache = carregar_json(MAGALU_CACHE_FILE, {"items": [], "updated": 0})

def cache_ja_enviado(key):
    return key in cache_envios["sent"]

def registrar_enviado(key, max_itens=120):
    cache_envios["sent"].append(key)
    cache_envios["sent"] = cache_envios["sent"][-max_itens:]
    salvar_json(CACHE_FILE, cache_envios)

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, origem="shopee"):
    prefixos = {"shopee": "🟠 SHOPEE", "ml": "🟡 MERCADO LIVRE", "magalu": "🔵 MAGALU"}
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
    abertura = random.choice([a for a in aberturas if a not in usadas_abertura] or aberturas)
    usadas_abertura.add(abertura)

    msg_tg = f"""
<b>{prefixo} | {abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

    msg_wa = f"""
*{prefixo} | {abertura}*

🔥 *{nome}*

{gatilho}

💰 *R$ {preco}*
⭐ {avaliacao} | 🛒 *{vendas} vendas*

⚠️ Pode subir de preço

🛒 {link}
"""
    return msg_tg, msg_wa

def gerar_link_whatsapp(msg_wa):
    return f"https://wa.me/?text={quote(msg_wa.strip())}"

def get_shopee_offers():
    logging.info("Buscando Shopee...")
    timestamp = int(time.time())
    query_body = "query { productOfferV2(sortType: 2, limit: 10) { nodes { productName, priceMin, commissionRate, sales, ratingStar, productLink, imageUrl } } }"
    payload = json.dumps({"query": query_body})
    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }
    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=15)
        return r.json()["data"]["productOfferV2"]["nodes"]
    except:
        return []

def normalize_price(val):
    try:
        if val is None:
            return "0.00"
        return f"{float(val):.2f}"
    except:
        return "0.00"

def extract_product_links_from_html(base_url, html_text):
    links = []
    pattern = r'href=["\']([^"\']+)["\']'
    for href in re.findall(pattern, html_text, flags=re.I):
        if any(x in href.lower() for x in ["/p/", "/produto/", "/dp/", "/dp/", "produto", "mercadolivre.com", "magazinevoce.com.br"]):
            full = urljoin(base_url, href)
            links.append(full)
    unique = []
    for x in links:
        if x not in unique:
            unique.append(x)
    return unique

def get_ml_list_page():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
        }
        r = requests.get(ML_LISTA_URL, headers=headers, timeout=20)
        return r.text
    except:
        return ""

def refresh_ml_cache():
    html_text = get_ml_list_page()
    if not html_text:
        return
    links = extract_product_links_from_html(ML_LISTA_URL, html_text)
    items = []
    for l in links:
        item_id = hashlib.md5(l.encode()).hexdigest()
        items.append({
            "id": item_id,
            "nome": "Produto Mercado Livre",
            "preco": "0.00",
            "link": l,
            "img": "",
            "vendas": random.randint(50, 2000),
            "avaliacao": round(random.uniform(4.4, 5.0), 1),
            "origem": "ml",
            "comissao": 5
        })
    if items:
        ml_lista_cache["items"] = items
        ml_lista_cache["updated"] = int(time.time())
        salvar_json(ML_LISTA_CACHE_FILE, ml_lista_cache)

def get_ml_from_cache():
    if not ml_lista_cache["items"] or (int(time.time()) - ml_lista_cache.get("updated", 0) > 21600):
        refresh_ml_cache()
    items = ml_lista_cache.get("items", [])
    random.shuffle(items)
    res = []
    for item in items:
        key = item["id"]
        if not cache_ja_enviado("ml_" + key):
            res.append(item)
    return res

def get_ml_direct(termo):
    offset = random.randint(0, 40)
    logging.info(f"Buscando ML Direto: {termo} (Offset: {offset})")
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={quote(termo)}&limit=10&offset={offset}"
        r = requests.get(url, timeout=10)
        items = r.json().get("results", [])
        res = []
        for item in items:
            try:
                img_id = item.get("thumbnail_id", "")
                img_url = f"https://http2.mlstatic.com/D_NQ_NP_{img_id}-O.webp" if img_id else item.get("thumbnail", "")
                res.append({
                    "id": str(item.get("id", "")),
                    "nome": item["title"],
                    "preco": f"{float(item['price']):.2f}",
                    "link": item["permalink"],
                    "img": img_url,
                    "vendas": int(item.get("sold_quantity", random.randint(50, 500))),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1),
                    "origem": "ml",
                    "comissao": 5
                })
            except:
                continue
        return res
    except:
        return []

def get_magalu_store_page():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            "Referer": "https://www.magazinevoce.com.br/"
        }
        r = requests.get(MAGALU_LOJA_URL, headers=headers, timeout=20)
        return r.text
    except:
        return ""

def refresh_magalu_cache():
    html_text = get_magalu_store_page()
    if not html_text:
        return
    links = extract_product_links_from_html(MAGALU_LOJA_URL, html_text)
    items = []
    for l in links:
        item_id = hashlib.md5(l.encode()).hexdigest()
        items.append({
            "id": item_id,
            "nome": "Produto Magalu",
            "preco": "0.00",
            "link": l,
            "img": "",
            "vendas": random.randint(50, 2000),
            "avaliacao": round(random.uniform(4.4, 5.0), 1),
            "origem": "magalu",
            "comissao": 4
        })
    if items:
        magalu_cache["items"] = items
        magalu_cache["updated"] = int(time.time())
        salvar_json(MAGALU_CACHE_FILE, magalu_cache)

def get_magalu_store_products():
    if not magalu_cache["items"] or (int(time.time()) - magalu_cache.get("updated", 0) > 21600):
        refresh_magalu_cache()
    items = magalu_cache.get("items", [])
    random.shuffle(items)
    res = []
    for item in items:
        key = item["id"]
        if not cache_ja_enviado("magalu_" + key):
            res.append(item)
    return res

def get_magalu_direct(termo):
    logging.info(f"Buscando Magalu Direto: {termo}")
    try:
        url = f"https://www.magazineluiza.com.br/busca-parcial/v1/search?q={quote(termo)}"
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
            "Referer": "https://www.magazineluiza.com.br/"
        }
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        items = data.get("data", {}).get("search", {}).get("products", [])
        res = []
        for item in items[:10]:
            try:
                p_url = f"https://www.magazineluiza.com.br/{item['path']}"
                aff = f"https://magazineluiza.onelink.me/{MAGALU_ONELINK_ID}/{MAGALU_STORE_ID}?af_dp={quote(p_url)}"
                res.append({
                    "id": str(item.get("id", hashlib.md5(p_url.encode()).hexdigest())),
                    "nome": item["title"],
                    "preco": f"{float(item['price']['salesPrice']):.2f}",
                    "link": aff,
                    "img": item.get("image", ""),
                    "vendas": random.randint(100, 2000),
                    "avaliacao": round(random.uniform(4.5, 5.0), 1),
                    "origem": "magalu",
                    "comissao": 4
                })
            except:
                continue
        return res
    except:
        return []

def escolher_item_sem_repetir(items, prefixo_cache):
    if not items:
        return None
    random.shuffle(items)
    for item in items:
        key = prefixo_cache + "_" + item.get("id", hashlib.md5(item["link"].encode()).hexdigest())
        if not cache_ja_enviado(key):
            registrar_enviado(key)
            return item
    item = random.choice(items)
    key = prefixo_cache + "_" + item.get("id", hashlib.md5(item["link"].encode()).hexdigest())
    registrar_enviado(key)
    return item

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not dentro_do_horario():
            return

        usadas_abertura.clear()
        total_lista = []

        shopee = get_shopee_offers()
        for i in shopee[:2]:
            try:
                l = i["productLink"]
                if "af_siteid" not in l:
                    l = f"{l}?af_siteid={AFILIADO_ID}"
                comis = round(float(i.get("commissionRate", 0)) * 100, 2)
                msg_tg, msg_wa = gerar_copy(
                    html.escape(i["productName"]),
                    f"{float(i['priceMin']):.2f}",
                    f"{int(i.get('sales', 100)):,}".replace(",", "."),
                    float(i.get("ratingStar", 4.5)),
                    comis,
                    l,
                    "shopee"
                )
                total_lista.append({"msg_tg": msg_tg, "msg_wa": msg_wa, "img": i["imageUrl"], "link": l})
            except:
                pass

        magalu_items = get_magalu_store_products()
        if not magalu_items:
            termo_magalu = random.choice(PREMIUM_TERMOS)
            magalu_items = get_magalu_direct(termo_magalu)
        for _ in range(min(2, len(magalu_items))):
            i = escolher_item_sem_repetir(magalu_items, "magalu")
            if i:
                msg_tg, msg_wa = gerar_copy(
                    html.escape(i["nome"]),
                    i["preco"],
                    i["vendas"],
                    i["avaliacao"],
                    i["comissao"],
                    i["link"],
                    "magalu"
                )
                total_lista.append({"msg_tg": msg_tg, "msg_wa": msg_wa, "img": i.get("img", ""), "link": i["link"]})

        ml_items = get_ml_from_cache()
        if not ml_items:
            termo_moto = f"{random.choice(MOTOS_PECAS)} {random.choice(MOTOS_MODELOS)}"
            ml_items = get_ml_direct(termo_moto)

            if not ml_items:
                termo_ml_p = random.choice(PREMIUM_TERMOS)
                ml_items = get_ml_direct(termo_ml_p)

        for _ in range(min(2, len(ml_items))):
            i = escolher_item_sem_repetir(ml_items, "ml")
            if i:
                msg_tg, msg_wa = gerar_copy(
                    html.escape(i["nome"]),
                    i["preco"],
                    i["vendas"],
                    i["avaliacao"],
                    i["comissao"],
                    i["link"],
                    "ml"
                )
                total_lista.append({"msg_tg": msg_tg, "msg_wa": msg_wa, "img": i.get("img", ""), "link": i["link"]})

        if not total_lista:
            return

        await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 OFERTAS NOVAS CHEGANDO...")
        await asyncio.sleep(5)

        for item in total_lista:
            try:
                zap_link = gerar_link_whatsapp(item["msg_wa"])
                full_msg = item["msg_tg"] + f'\n📲 <a href="{zap_link}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                if item["img"]:
                    await context.bot.send_photo(chat_id=CHAT_ID_DESTINO, photo=item["img"], caption=full_msg, parse_mode="HTML")
                else:
                    await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text=full_msg, parse_mode="HTML", disable_web_page_preview=True)
                await asyncio.sleep(45)
            except Exception as e:
                logging.error(f"Erro ao enviar item: {e}")

    except Exception as e:
        logging.error(f"ERRO CRITICO: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("🤖 BOT V19 ATIVADO")

if __name__ == "__main__":
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.run_polling()
        except:
            time.sleep(15)




