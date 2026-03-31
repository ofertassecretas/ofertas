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

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL_SHOPEE = 5400
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

    nome_lower = nome.lower()

    # =========================
    # DETECÇÃO DE CATEGORIA
    # =========================

    if any(p in nome_lower for p in ["tenis", "sapato", "camisa", "vestido", "blusa", "calça", "short"]):
        categoria = "roupa"

    elif any(p in nome_lower for p in ["fone", "bluetooth", "caixa", "carregador", "led", "smartwatch"]):
        categoria = "eletronico"

    elif any(p in nome_lower for p in ["panela", "pano", "cozinha", "organizador", "casa", "escova"]):
        categoria = "casa"

    else:
        categoria = "geral"

    # =========================
    # COPYS POR CATEGORIA
    # =========================

    copys = {
        "roupa": [
            "🔥 Esse {produto} parece de marca cara",
            "😮 Quem vê esse {produto} nem imagina o preço",
            "💎 Esse {produto} tá com cara de premium",
            "👀 Olha esse {produto}… sério",
            "✨ Esse {produto} valoriza demais o visual",
            "🖤 Simples e bonito demais esse {produto}"
        ],
        "eletronico": [
            "⚠️ Esse {produto} tá surpreendendo muita gente",
            "😳 Não esperava isso desse {produto}",
            "🔌 Esse {produto} tá vendendo MUITO",
            "🔥 Esse {produto} tá com avaliação alta demais",
            "👀 Olha isso nesse {produto}",
            "🚨 Esse {produto} virou achado"
        ],
        "casa": [
            "🏠 Esse {produto} facilita muito o dia a dia",
            "🧼 Esse {produto} tá salvando muita gente",
            "✨ Organização com esse {produto}",
            "🔥 Esse {produto} tá valendo muito a pena",
            "👀 Olha isso pra casa",
            "💥 Esse {produto} resolve fácil"
        ],
        "geral": [
            "💣 Oferta fora do padrão nesse {produto}",
            "⚡ Esse {produto} tá com preço absurdo",
            "😳 Esse {produto} tá chamando atenção",
            "🔥 Esse {produto} tá vendendo muito",
            "👀 Olha esse {produto}",
            "🚨 Esse {produto} pode subir a qualquer momento"
        ]
    }

    beneficios = {
        "roupa": [
            "💥 deixa o visual mais arrumado",
            "💥 combina com tudo",
            "💥 estilo sem gastar muito",
            "💥 aparência de produto caro",
            "💥 veste bem demais",
            "💥 destaque no visual"
        ],
        "eletronico": [
            "💥 muito acima do preço",
            "💥 tecnologia barata que funciona",
            "💥 entrega mais do que promete",
            "💥 qualidade surpreendente",
            "💥 custo-benefício absurdo",
            "💥 desempenho top pelo preço"
        ],
        "casa": [
            "💥 ajuda muito no dia a dia",
            "💥 deixa tudo mais organizado",
            "💥 praticidade total",
            "💥 facilita sua rotina",
            "💥 solução simples e barata",
            "💥 útil de verdade"
        ],
        "geral": [
            "💥 custo-benefício absurdo",
            "💥 barato demais pro que entrega",
            "💥 vale cada centavo",
            "💥 oportunidade real",
            "💥 preço muito abaixo",
            "💥 difícil achar nesse valor"
        ]
    }

    pressoes = [
        "Preço baixo + venda alta não ficam juntos.",
        "Depois que sobe, não volta.",
        "Se esperar, paga mais.",
        "Quem pegou barato, pegou.",
        "Esse tipo de oferta some rápido.",
        "Quando todo mundo descobre, já era."
    ]

    ctas = [
        "🛒 COMPRAR AGORA",
        "🔥 GARANTIR DESCONTO",
        "⚡ PEGAR OFERTA",
        "👇 APROVEITAR AGORA",
        "💥 VER PROMOÇÃO",
        "🚀 IR PRA OFERTA"
    ]

    # =========================
    # ESCOLHAS
    # =========================

    produto_curto = nome.split()[0].lower()

    frase = random.choice(copys[categoria]).format(produto=produto_curto)
    beneficio = random.choice(beneficios[categoria])
    pressao = random.choice(pressoes)
    cta = random.choice(ctas)

    # =========================
    # COPY FINAL
    # =========================

    copy = f"""
<b>{frase}</b>

🔥 <b>{nome}</b>

{beneficio}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

{pressao}

<a href="{link}">{cta}</a>

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

            await asyncio.sleep(random.randint(25, 35))

        except Exception as e:
            logging.error(f"Erro envio: {e}")

# =========================
# INICIALIZAÇÃO
# =========================

async def post_init(app):

    app.job_queue.run_repeating(
        send_shopee_offers,
        interval=CHECK_INTERVAL_SHOPEE,
        first=10
    )

    logging.info("🤖 Bot Shopee Online!")

if __name__ == "__main__":
    app = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.run_polling(
        poll_interval=60,
        timeout=60,
        drop_pending_updates=True
    )




