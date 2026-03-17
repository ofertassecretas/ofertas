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

# =========================
# CONFIGURAÇÕES
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL_SHOPEE = 5400
CHECK_INTERVAL_ML = 10

MAX_PRODUTOS_POR_RODADA = 3

logging.basicConfig(level=logging.INFO)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

ARQUIVO_HISTORICO = "historico_produtos.json"

# =========================
# HISTÓRICO
# =========================

def carregar_historico():
    if os.path.exists(ARQUIVO_HISTORICO):
        with open(ARQUIVO_HISTORICO, "r") as f:
            return json.load(f)
    return {"links": [], "titulos": {}}

def salvar_historico(data):
    with open(ARQUIVO_HISTORICO, "w") as f:
        json.dump(data, f)

historico = carregar_historico()

# =========================
# HORÁRIO
# =========================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    inicio = dt_time(5, 0)
    fim = dt_time(21, 0)
    return inicio <= agora <= fim

# =========================
# LIMPAR TITULO
# =========================

def limpar_titulo(nome):

    nome = nome.lower()

    nome = re.sub(r'\d+', '', nome)
    nome = re.sub(r'\b(ml|l|litro|litros|cm|mm|pcs|peças)\b', '', nome)

    palavras_ruins = [
        "kit", "original", "novo", "oficial", "promoção", "oferta"
    ]

    for p in palavras_ruins:
        nome = nome.replace(p, "")

    nome = re.sub(r'\s+', ' ', nome).strip()

    return nome

# =========================
# VERIFICAR SIMILARIDADE
# =========================

def produto_similar(nome_limpo):

    agora = time.time()

    for titulo, timestamp in historico["titulos"].items():

        if agora - timestamp < 43200:

            palavras_novas = set(nome_limpo.split())
            palavras_antigas = set(titulo.split())

            inter = palavras_novas & palavras_antigas

            if len(inter) >= 2:
                return True

    return False

# =========================
# COPY
# =========================

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, zap):

    headlines = [
        "🚨 ISSO NÃO FICA NESSE PREÇO.",
        "💣 OFERTA FORA DO PADRÃO.",
        "⚡ ACHADO DO DIA.",
        "🔥 PREÇO ABAIXO DO MERCADO."
    ]

    pressao = [
        "Preço baixo + venda alta não ficam juntos.",
        "Depois que sobe, não volta.",
        "Se esperar, paga mais."
    ]

    headline = random.choice(headlines)
    frase_pressao = random.choice(pressao)

    copy = f"""
<b>{headline}</b>

🔥 <b>{nome}</b>

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

{frase_pressao}

👇 Clique antes que mude:
<a href="{link}">🛒 COMPRAR AGORA</a>

📲 <a href="{zap}">Copiar para divulgar no WhatsApp</a>
"""

    return copy

# =========================
# AUXILIARES
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

    texto = f"""🔥 OFERTA

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
# MERCADO LIVRE
# =========================

def get_ml_offers():
    try:
        url = "https://api.mercadolibre.com/sites/MLB/search"
        
        termos = [
            "fone bluetooth TWS barato", 
            "smartwatch economico", 
            "caixa som bluetooth", 
            "panela eletrica 110v"
        ]
        
        params = {
            "q": random.choice(termos),
            "sort": "sold_quantity_desc",
            "limit": 50,
            "condition": "new"
        }
        
        print(f"🔍 ML Query: {params['q']}")
        resp = requests.get(url, params=params, timeout=15)
        print(f"🔍 ML Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"🔍 ML Response: {resp.text[:200]}")
            return []
            
        data = resp.json()
        print(f"🔍 ML Total: {data.get('paging', {}).get('total', 0)}")
        
        produtos = data.get("results", [])
        filtrados = []
        
        print(f"🔍 ML Produtos iniciais: {len(produtos)}")
        
        for p in produtos:
            preco = p.get("price", 0)
            if preco > 250 or preco < 10:
                continue
                
            p["desconto"] = random.randint(10, 30)
            p["preco_antigo"] = preco * 1.3  # Simula preço antigo
            filtrados.append(p)
            
        print(f"🔍 ML Filtrados: {len(filtrados)}")
        random.shuffle(filtrados)
        return filtrados
        
    except Exception as e:
        print(f"🔍 ML ERRO COMPLETO: {e}")
        return []



# =========================
# ENVIO SHOPEE
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):

    if not dentro_do_horario():
        return

    ofertas = get_shopee_offers()

    enviados = 0

    for item in ofertas:

        if enviados >= MAX_PRODUTOS_POR_RODADA:
            break

        link_final = aplicar_id_afiliado(item["productLink"])

        if link_final in historico["links"]:
            continue

        nome_produto = html.escape(item["productName"])

        nome_limpo = limpar_titulo(nome_produto)

        if produto_similar(nome_limpo):
            continue

        try:
            preco = float(item["priceMin"])
        except:
            continue

        if preco > 250:
            continue

        vendas = item.get("sales", 0)
        avaliacao = item.get("ratingStar", 0)
        comissao = item.get("commissionRate", 0)
        imagem_url = item.get("imageUrl")

        comissao_formatada = round(float(comissao) * 100, 2)

        vendas_formatadas = f"{int(vendas):,}".replace(",", ".")

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

            historico["links"].append(link_final)
            historico["titulos"][nome_limpo] = time.time()

            salvar_historico(historico)

            enviados += 1

            await asyncio.sleep(random.randint(5, 12))

        except Exception as e:
            logging.error(f"Erro envio: {e}")

# =========================
# ENVIO MERCADO LIVRE
# =========================

async def send_ml_offers(context):
    bot = context.bot
    
    ofertas = get_ml_offers()
    print("ML OFERTAS:", ofertas)
    ofertas = ofertas or []
    
    enviados = 0
    for item in ofertas:
        if enviados >= MAX_PRODUTOS_POR_RODADA:
            break
            
        nome = html.escape(item.get("title", ""))
        preco = item.get("price", 0)
        link = item.get("permalink", "")
        
        if preco > 300 or preco < 10:
            continue
            
        preco_antigo = item.get("preco_antigo")
        if preco_antigo:
            desconto = round(((preco_antigo - preco) / preco_antigo) * 100)
        else:
            desconto = random.randint(10, 30)
            
        zap_link = montar_texto_whatsapp(nome, f"R$ {preco:.2f}", link)
        
        mensagem = f"""
🚨 <b>OFERTA MERCADO LIVRE</b>

🔥 <b>{nome}</b>

💸 De: <s>R$ {preco_antigo or '---'}</s>
💰 Por: <b>R$ {preco:.2f}</b>
📉 Desconto: <b>{desconto}%</b>

🛒 {item.get("sold_quantity", 0)} vendidos

👇 Aproveite:
<a href="{link}">🛒 COMPRAR AGORA</a>

📲 <a href="{zap_link}">Copiar para WhatsApp</a>

━━━━━━━━━━━━━━━
📢 <b>Ofertas Secretas</b>
"""
        
        try:
            await bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=item.get("thumbnail", ""),
                caption=mensagem,
                parse_mode="HTML"
            )
            historico["links"].append(link)
            historico["titulos"][limpar_titulo(nome)] = time.time()
            salvar_historico(historico)
            enviados += 1
            await asyncio.sleep(random.randint(5, 12))
            
        except Exception as e:
            logging.error(f"Erro ML envio: {e}")



# =========================
# INICIALIZAÇÃO
# =========================

async def post_init(app):

    app.job_queue.run_repeating(
        send_shopee_offers,
        interval=CHECK_INTERVAL_SHOPEE,
        first=10
    )

    app.job_queue.run_repeating(
        send_ml_offers,
        interval=CHECK_INTERVAL_ML,
        first=2700
    )

    logging.info("🤖 Bot Shopee + Mercado Livre Online!")

if __name__ == "__main__":
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.job_queue.run_once(send_ml_offers, when=5)

    app.run_polling(
        poll_interval=60,
        timeout=60,
        drop_pending_updates=True
    )

# 🔑 GERADOR ML ACCESS TOKEN (RODE 1x)
ML_CLIENT_ID = "2239931406798467"
ML_CLIENT_SECRET = "LwUz7jRmHMd8ffid7YA9WNsCNEzZfo7l"
ML_REDIRECT_URI = "https://google.com"  # Qualquer URL

def gerar_ml_token():
    # 1. PRIMEIRO: Gere o CODE (abra no navegador)
    auth_url = f"https://auth.mercadolibre.com.br/authorization?response_type=code&client_id={ML_CLIENT_ID}&redirect_uri={ML_REDIRECT_URI}"
    print(f"🔑 PASSO 1: Abra este link no navegador:\n{auth_url}")
    print("\n👉 Autorize → Copie o 'code=XXXXX' da URL final")
    
    # 2. DEPOIS: Cole o CODE aqui e rode novamente
    code = input("🔑 Cole o CODE aqui: ").split('code=')[1].split('&')[0]
    
    # 3. Troca CODE por TOKEN
    token_url = "https://api.mercadolibre.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": ML_CLIENT_ID,
        "client_secret": ML_CLIENT_SECRET,
        "code": code,
        "redirect_uri": ML_REDIRECT_URI
    }
    
    resp = requests.post(token_url, data=data)
    token_data = resp.json()
    
    print(f"✅ ACCESS TOKEN: {token_data['access_token']}")
    print(f"✅ REFRESH TOKEN: {token_data['refresh_token']}")
    return token_data

# Teste (rode 1x)
if __name__ == "__main__":
    print("🚀 GERANDO ML TOKEN...")
    token = gerar_ml_token()



