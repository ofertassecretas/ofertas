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

print("VERSAO PROFISSIONAL ANTIREPETICAO ATIVA")

# =========================
# CONFIG
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD")

CHAT_ID_DESTINO = -1003848415150

SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"

SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL_SHOPEE = 5400

logging.basicConfig(level=logging.INFO)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

ARQUIVO_HISTORICO = "historico_produtos.json"

ULTIMO_ALERTA_DIA = None

# =========================
# KEYWORDS
# =========================

def keywords_inteligentes():
    mes = datetime.now().month
    base = ["promoção", "oferta", "barato"]

    if mes in [6,7,8]:
        base += ["jaqueta", "moletom"]
    elif mes in [12,1,2]:
        base += ["ventilador", "chinelo"]
    elif mes == 5:
        base += ["dia das mães"]

    return base

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
    return dt_time(5, 0) <= agora <= dt_time(21, 0)

# =========================
# LIMPEZA
# =========================

def limpar_titulo(nome):
    nome = nome.lower()
    nome = re.sub(r'\d+', '', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()
    return nome

def produto_similar(nome_limpo):
    agora = time.time()
    for titulo, timestamp in historico["titulos"].items():
        if agora - timestamp < 43200:
            if len(set(nome_limpo.split()) & set(titulo.split())) >= 2:
                return True
    return False

# =========================
# CATEGORIA (ANTI REPETIÇÃO)
# =========================

def classificar_categoria(nome):
    nome = nome.lower()

    if any(p in nome for p in ["fone", "airpods", "earbud"]):
        return "fone"

    if any(p in nome for p in ["caixa de som", "speaker", "bluetooth portátil"]):
        return "som"

    if any(p in nome for p in ["calça", "camiseta", "blusa", "legging"]):
        return "roupa"

    if any(p in nome for p in ["tenis", "chinelo", "sapato"]):
        return "calcado"

    if any(p in nome for p in ["suporte", "organizador", "cozinha", "casa"]):
        return "casa"

    return "outros"

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
        "Avaliações acima da média (produto confiável)",
        "Volume de vendas alto nos últimos dias",
        "Simples, útil e direto ao ponto",
        "Custo-benefício difícil de bater",
        "Quem compra normalmente recomenda",
        "Produto funcional, sem frescura",
        "Tá girando bem dentro da plataforma",
        "Boa margem pra quem trabalha com afiliado",
        "Não é hype, é produto que resolve"
    ]

    abertura = random.choice([a for a in aberturas if a not in usadas_abertura] or aberturas)
    usadas_abertura.add(abertura)

    gatilho = random.choice(gatilhos)

    return f"""
<b>{abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço a qualquer momento

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# WHATSAPP
# =========================

def gerar_link_whatsapp_from_html(msg_html, link):
    texto = re.sub('<[^<]+?>', '', msg_html)
    texto += f"\n\n🛒 Compre aqui:\n{link}"
    return f"https://wa.me/?text={quote(texto)}"

# =========================
# API
# =========================

def get_shopee_offers(keyword=None):

    timestamp = int(time.time())

    query_body = f"""
    query {{
        productOfferV2(keyword: "{keyword or ''}", sortType: 2, limit: 20) {{
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
    """

    payload = json.dumps({"query": query_body})

    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            data = r.json()
            produtos = data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
            random.shuffle(produtos)
            return produtos
    except Exception as e:
        logging.error(e)

    return []

# =========================
# ENVIO
# =========================

async def send_shopee_offers(context: ContextTypes.DEFAULT_TYPE):

    global ULTIMO_ALERTA_DIA

    if not dentro_do_horario():
        return

    global usadas_abertura
    usadas_abertura.clear()

    hoje = datetime.now(FUSO_BR).date()

    if ULTIMO_ALERTA_DIA != hoje:
        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS LIBERADAS AGORA\nSeparei as melhores 👇"
        )
        ULTIMO_ALERTA_DIA = hoje
    else:
        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="⚠️ Alerta! Novas ofertas chegando..."
        )

    ofertas = []
    for k in keywords_inteligentes():
        ofertas += get_shopee_offers(k)

    selecionadas = []
    contagem_preco = {"barato": 0, "medio": 0, "alto": 0}
    contagem_categoria = {}

    for item in ofertas:

        link = aplicar_id_afiliado(item["productLink"])

        if link in historico["links"]:
            continue

        nome = html.escape(item["productName"])
        nome_limpo = limpar_titulo(nome)

        if produto_similar(nome_limpo):
            continue

        categoria = classificar_categoria(nome)

        if contagem_categoria.get(categoria, 0) >= 1:
            continue

        try:
            preco = float(item["priceMin"])
        except:
            continue

        if preco <= 80:
            faixa = "barato"
        elif preco <= 250:
            faixa = "medio"
        elif preco <= 800:
            faixa = "alto"
        else:
            continue

        if faixa == "barato" and contagem_preco["barato"] >= 2:
            continue
        if faixa == "medio" and contagem_preco["medio"] >= 2:
            continue
        if faixa == "alto" and contagem_preco["alto"] >= 1:
            continue

        rating = float(item.get("ratingStar", 0))
        vendas = int(item.get("sales", 0))

        if rating < 4.2 or vendas < 20:
            continue

        comissao = round(float(item.get("commissionRate", 0)) * 100, 2)

        vendas_f = f"{vendas:,}".replace(",", ".")

        msg = gerar_copy(nome, f"{preco:.2f}", vendas_f, rating, comissao, link)
        zap = gerar_link_whatsapp_from_html(msg, link)

        msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
        msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

        selecionadas.append({
            "msg": msg,
            "img": item.get("imageUrl"),
            "link": link,
            "nome_limpo": nome_limpo
        })

        contagem_preco[faixa] += 1
        contagem_categoria[categoria] = contagem_categoria.get(categoria, 0) + 1

        if len(selecionadas) >= 5:
            break

    for item in selecionadas:
        try:
            await context.bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=item["img"],
                caption=item["msg"],
                parse_mode="HTML"
            )

            historico["links"].append(item["link"])
            historico["titulos"][item["nome_limpo"]] = time.time()

            historico["links"] = historico["links"][-200:]
            if len(historico["titulos"]) > 200:
                historico["titulos"] = dict(list(historico["titulos"].items())[-200:])

            salvar_historico(historico)

            await asyncio.sleep(60)

        except Exception as e:
            logging.error(e)

# =========================
# AUX
# =========================

def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

# =========================
# START
# =========================

async def post_init(app):
    app.job_queue.run_repeating(send_shopee_offers, interval=CHECK_INTERVAL_SHOPEE, first=10)
    logging.info("🤖 Bot rodando!")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
    app.run_polling(drop_pending_updates=True)
