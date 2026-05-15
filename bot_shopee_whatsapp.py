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

print("VERSAO FINAL HIBRIDA ESTAVEL V21 - LISTA ML PRIORITARIA + LOJA MAGALU")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

MAGALU_ONELINK_ID = "589508454"
MAGALU_STORE_ID = "07yuzqjf"
MAGALU_LOJA_URL = "https://www.magazinevoce.com.br/magazineshopandreonline/"
MAGALU_OFERTAS_URL = "https://www.magazinevoce.com.br/magazineshopandreonline/ofertas/"

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
    except Exception as e:
        logging.warning(f"Shopee falhou: {e}")
        return []

def extract_links(html_text, base_url):
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html_text, flags=re.I)
    out = []
    for href in hrefs:
        h = href.strip()
        if h.startswith("#") or h.startswith("javascript:") or h.startswith("mailto:"):
            continue
        full = urljoin(base_url, h)
        low = full.lower()
        if any(x in low for x in ["mercadolivre.com", "mercadolivre.com.br", "magazinevoce.com.br", "/p/", "/produto/", "/ofertas", "/dp/"]):
            if full not in out:
                out.append(full)
    return out

def get_ml_list_page():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
    }
    r = requests.get(ML_LISTA_URL, headers=headers, timeout=20)
    return r.text, r.url

def refresh_ml_cache():
    try:
        html_text, final_url = get_ml_list_page()
        links = extract_links(html_text, final_url)
        logging.info(f"ML links encontrados na lista: {len(links)}")
        items = []
        for l in links:
            if "mercadolivre" not in l.lower():
                continue
            item_id = hashlib.md5(l.encode()).hexdigest()
            items.append({
                "id": item_id,
                "nome": "Produto da sua lista ML",
                "preco": "0.00",
                "link": l,
                "img": "",
                "vendas": random.randint(50, 2000),
                "avaliacao": round(random.uniform(4.4, 5.0), 1),
                "origem": "ml",
                "comissao": 5
            })
        ml_lista_cache["items"] = items
        ml_lista_cache["updated"] = int(time.time())
        salvar_json(ML_LISTA_CACHE_FILE, ml_lista_cache)
    except Exception as e:
        logging.warning(f"Falha ao atualizar cache ML: {e}")

def get_ml_from_cache():
    if not ml_lista_cache["items"] or (int(time.time()) - ml_lista_cache.get("updated", 0) > 21600):
        refresh_ml_cache()
    items = ml_lista_cache.get("items", [])
    random.shuffle(items)
    return [item for item in items if not cache_ja_enviado("ml_" + item["id"])]

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
                link = item.get("permalink")
                nome = item.get("title")
                preco = item.get("price")
                if not link or not nome or preco is None:
                    continue
                img = item.get("thumbnail") or ""
                res.append({
                    "id": str(item.get("id", hashlib.md5(link.encode()).hexdigest())),
                    "nome": nome,
                    "preco": f"{float(preco):.2f}",
                    "link": link,
                    "img": img,
                    "vendas": int(item.get("sold_quantity", random.randint(50, 500))),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1),
                    "origem": "ml",
                    "comissao": 5
                })
            except:
                continue
        logging.info(f"ML direto itens válidos: {len(res)}")
        return res
    except Exception as e:
        logging.warning(f"ML direto falhou: {e}")
        return []

def get_magalu_store_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://www.magazinevoce.com.br/"
    }
    r = requests.get(url, headers=headers, timeout=20)
    return r.text, r.url

def refresh_magalu_cache():
    try:
        for url in [MAGALU_OFERTAS_URL, MAGALU_LOJA_URL]:
            html_text, final_url = get_magalu_store_page(url)
            links = extract_links(html_text, final_url)
            logging.info(f"Magalu links encontrados em {url}: {len(links)}")
            items = []
            for l in links:
                if "magazinevoce.com.br" not in l.lower():
                    continue
                item_id = hashlib.md5(l.encode()).hexdigest()
                items.append({
                    "id": item_id,
                    "nome": "Produto da sua loja Magalu",
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
                return
    except Exception as e:
        logging.warning(f"Falha ao atualizar cache Magalu: {e}")

def get_magalu_store_products():
    if not magalu_cache["items"] or (int(time.time()) - magalu_cache.get("updated", 0) > 21600):
        refresh_magalu_cache()
    items = magalu_cache.get("items", [])
    random.shuffle(items)
    return [item for item in items if not cache_ja_enviado("magalu_" + item["id"])]

def get_magalu_direct(termo):
    logging.info(f"Buscando Magalu Direto: {termo}")
    try:
        


