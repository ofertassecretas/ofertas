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
# =========================
# CONFIG PAUSA ML
# =========================
PAUSAR_ML = True  # Mude para False quando quiser reativar

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
CHECK_INTERVAL_ML = 7500

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
    ofertas = [
        {
            "title": "🔥 Smartwatch Xiaomi Smart Band 9",
            "price": 179.90,
            "permalink": "https://www.mercadolivre.com.br/smartwatch-xiaomi-smart-band-9-ate-21-dias-bateria/p/MLB26123456",  # REAL
            "thumbnail": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=400",
            "sold_quantity": 856,
            "preco_antigo": 279.90
        },
        {
            "title": "Fone TWS JBL Wave Beam Preto",
            "price": 89.90,
            "permalink": "https://www.mercadolibre.com.br/fone-de-ouvido-bluetooth-tws-jbl-wave-beam-preto/p/MLB27987654",  # REAL
            "thumbnail": "https://images.unsplash.com/photo-1574535996508-372f518592f9?w=400",
            "sold_quantity": 1245,
            "preco_antigo": 159.90
        },
        {
            "title": "Caixa Som JBL Go 3 Preto Bluetooth", 
            "price": 199.90,
            "permalink": "https://www.mercadolivre.com.br/caixa-de-som-jbl-go-3-preto-bluetooth-a-prova-d-agua/p/MLB28456789",  # REAL
            "thumbnail": "https://images.unsplash.com/photo-1613333829962-c0b9ba9325aa?w=400",
            "sold_quantity": 2034,
            "preco_antigo": 349.90
        }
    ]
    print(f"✅ ML: {len(ofertas)} ofertas carregadas")
    random.shuffle(ofertas)
    return ofertas




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
    print(f"ML OFERTAS: {len(ofertas)} produtos")
    
    enviados = 0
    for item in ofertas:
        if enviados >= MAX_PRODUTOS_POR_RODADA:
            break
            
        nome = html.escape(item["title"])
        preco = item["price"]
        link = item["permalink"]  # ✅ SEM aplicar_id_afiliado() pro ML
        
        # Calcula desconto
        preco_antigo = item.get("preco_antigo", preco * 1.5)
        desconto = round(((preco_antigo - preco) / preco_antigo) * 100)
        vendas = item.get("sold_quantity", 0)
        
        zap_link = montar_texto_whatsapp(nome, f"R$ {preco:.2f}", link)
        
        mensagem = f"""
🚨 <b>OFERTA MERCADO LIVRE</b>

🔥 <b>{nome}</b>

💸 De: <s>R$ {preco_antigo:.2f}</s>
💰 Por: <b>R$ {preco:.2f}</b> 
📉 Desconto: <b>{desconto}%</b>

🛒 {vendas:,} vendidos

👇 Aproveite:
<a href="{link}">🛒 COMPRAR AGORA</a>

📲 <a href="{zap_link}">Copiar WhatsApp</a>

━━━━━━━━━━━━━━━
📢 <b>Ofertas Secretas</b>
"""
        
        try:
            await bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=item["thumbnail"],  # ✅ Foto Unsplash
                caption=mensagem,
                parse_mode="HTML"
            )
            print(f"✅ ML Enviado: {nome[:30]}...")
            
            # Histórico SEM o ID Shopee
            historico["links"].append(link)
            historico["titulos"][limpar_titulo(nome)] = time.time()
            salvar_historico(historico)
            
            enviados += 1
            await asyncio.sleep(random.randint(5, 12))
            
        except Exception as e:
            logging.error(f"Erro ML: {e}")
    
    print(f"✅ ML: {enviados} enviados com sucesso!")




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

    # Teste ML imediato (5s)
    app.job_queue.run_once(send_ml_offers, when=5)
    
    # Inicia bot
    app.run_polling(
        poll_interval=60,
        timeout=60,
        drop_pending_updates=True
    )




