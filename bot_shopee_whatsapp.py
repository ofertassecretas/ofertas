import asyncio
import requests
import logging
import random
import hashlib
import time
import json
import os
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

print("VERSAO SHOPEE V120 CURADORA - VARIEDADE REAL + ANTI-REPETICAO")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

HISTORICO_FILE = "historico_global_v120.json"
CHECK_INTERVAL = 5400
MAX_OFERTAS = 10
MIN_OFERTAS = 6
MIN_PRECO = 12.0
MAX_PRECO = 1000.0
MIN_RATING = 4.5
MIN_VENDAS = 10
MAX_POR_NICHO = 2
MAX_POR_FAMILIA = 1
MAX_POR_MARCA = 1
MAX_POR_TITULO_SIMILAR = 1
JANELA_HISTORICO_DIAS = 15
JANELA_FAMILIA_DIAS = 10
JANELA_MARCA_DIAS = 7

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

NICHOS = {
    "Moto": [
        "escapamento moto", "pneu moto", "aba tanque moto", "retrovisor moto",
        "farol moto", "guidao moto", "bateria moto", "kit relacao moto",
        "capacete moto", "bau moto", "manopla moto", "protetor manete moto",
        "suspensao moto", "carenagem moto", "pedaleira moto", "protetor motor moto"
    ],
    "Moda Masculina": [
        "camisa social masculina", "camisa manga curta masculina", "camisa polo masculina",
        "bermuda masculina", "calca jeans masculina", "calca cargo masculina",
        "jaqueta masculina", "moletom masculino", "tenis masculino", "sapatenis masculino",
        "boné masculino", "relógio masculino", "carteira masculina", "cinto masculino"
    ],
    "Moda Feminina": [
        "vestido feminino", "vestido longo feminino", "blusa feminina", "camisa feminina",
        "conjunto feminino", "saia feminina", "shorts feminino", "calcinha feminina",
        "top feminino", "sandalia feminina", "bolsa feminina", "tenis feminino"
    ],
    "Casa": [
        "air fryer", "aspirador", "mop", "escova eletrica limpeza", "organizador cozinha",
        "jogo de cama", "edredom", "travesseiro", "tapete", "ventilador",
        "umidificador", "cafeteira", "liquidificador", "batedeira", "panela eletrica"
    ],
    "Maternidade": [
        "mochila maternidade", "carrinho bebe", "berco bebe", "chocalho bebe",
        "mordedor bebe", "babador bebe", "cadeirinha bebe", "babá eletronica",
        "kit higiene bebe", "roupa bebe", "ninho bebe"
    ],
    "Eletroeletrônicos": [
        "smartwatch", "fone bluetooth", "headset gamer", "ssd", "carregador turbo",
        "power bank", "caixa de som bluetooth", "tablet", "mouse gamer", "teclado mecanico"
    ]
}

PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "dummy", "brinde", "usado", "defeito", "película", "capinha",
    "adesivo", "selo", "pano de prato", "esponja magica", "filtro de papel",
    "fone", "bike", "bicicleta", "quadriciclo", "patinete", "brinquedo infantil"
]

HISTORICO = {}

def carregar_historico():
    global HISTORICO
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                HISTORICO = json.load(f)
        except:
            HISTORICO = {}
    else:
        HISTORICO = {}

def salvar_historico():
    agora = datetime.now(FUSO_BR)
    limite = agora - timedelta(days=JANELA_HISTORICO_DIAS)
    limpo = {}
    for k, v in HISTORICO.items():
        try:
            dt = datetime.fromisoformat(v.get("data"))
            if dt >= limite:
                limpo[k] = v
        except:
            continue
    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(limpo, f, ensure_ascii=False, indent=2)

def normalizar(txt):
    if not txt:
        return ""
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt

def extrair_marca(titulo):
    t = normalizar(titulo)
    marcas = ["nike", "adidas", "olympikus", "fila", "mizuno", "lovito", "pro tork", "honda", "yamaha", "it s"]
    for m in marcas:
        if m in t:
            return m
    return ""

def extrair_familia(titulo):
    t = normalizar(titulo)
    grupos = {
        "escova eletrica limpeza": ["escova eletrica", "escova de limpeza", "esfregao eletrico", "escova magica"],
        "vestido feminino": ["vestido", "longo feminino", "vestido longo"],
        "camisa polo": ["camisa polo", "polo masculina", "polo feminino"],
        "escapamento moto": ["escapamento", "escape moto", "pro tork mini", "gemoto"],
        "chocalho bebe": ["chocalho", "mordedor", "brinquedo bebe", "pelucia bebe"],
    }
    for familia, termos in grupos.items():
        if any(term in t for term in termos):
            return familia
    tokens = t.split()
    return " ".join(tokens[:3])

def titulo_similar(a, b):
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()

def passa_filtros_basicos(oferta):
    titulo = normalizar(oferta.get("productName", ""))
    if not titulo:
        return False
    if any(p in titulo for p in PALAVRAS_BLOQUEIO):
        return False
    if len(titulo) < 12:
        return False

    preco = float(oferta.get("price", 0) or 0) / 100 if int(oferta.get("price", 0) or 0) > 1000 else float(oferta.get("price", 0) or 0)
    rating = float(oferta.get("ratingStar", 0) or 0)
    vendas = int(oferta.get("soldCount", 0) or 0)
    comissao = oferta.get("commissionRate", "0")
    try:
        comissao = float(str(comissao).replace("%", "").replace(",", ".")) / 100 if float(str(comissao).replace("%", "").replace(",", ".")) > 1 else float(str(comissao).replace("%", "").replace(",", "."))
    except:
        comissao = 0.0

    if preco < MIN_PRECO or preco > MAX_PRECO:
        return False
    if rating < MIN_RATING:
        return False
    if vendas < MIN_VENDAS:
        return False
    if comissao < 0.06:
        return False
    return True

def score_oferta(oferta):
    preco = float(oferta.get("price", 0) or 0) / 100 if int(oferta.get("price", 0) or 0) > 1000 else float(oferta.get("price", 0) or 0)
    rating = float(oferta.get("ratingStar", 0) or 0)
    vendas = int(oferta.get("soldCount", 0) or 0)
    comissao = oferta.get("commissionRate", "0")
    try:
        comissao = float(str(comissao).replace("%", "").replace(",", ".")) / 100 if float(str(comissao).replace("%", "").replace(",", ".")) > 1 else float(str(comissao).replace("%", "").replace(",", "."))
    except:
        comissao = 0.0

    score = 0
    score += min(vendas, 5000) / 80
    score += rating * 18
    score += comissao * 120
    if 20 <= preco <= 250:
        score += 12
    if 250 < preco <= 800:
        score += 8
    if vendas > 200:
        score += 8
    return score

def ja_enviado(oferta):
    titulo = oferta.get("productName", "")
    link = oferta.get("offerLink", "")
    fam = extrair_familia(titulo)
    marca = extrair_marca(titulo)
    chave = hashlib.md5(normalizar(titulo).encode()).hexdigest()

    if chave in HISTORICO:
        return True

    for _, item in HISTORICO.items():
        if titulo_similar(titulo, item.get("titulo", "")) >= 0.82:
            return True
        if fam and fam == item.get("familia"):
            dt = datetime.fromisoformat(item.get("data"))
            if datetime.now(FUSO_BR) - dt <= timedelta(days=JANELA_FAMILIA_DIAS):
                return True
        if marca and marca == item.get("marca"):
            dt = datetime.fromisoformat(item.get("data"))
            if datetime.now(FUSO_BR) - dt <= timedelta(days=JANELA_MARCA_DIAS):
                return True
    return False

def registrar_oferta(oferta, nicho):
    titulo = oferta.get("productName", "")
    chave = hashlib.md5(normalizar(titulo).encode()).hexdigest()
    HISTORICO[chave] = {
        "titulo": titulo,
        "familia": extrair_familia(titulo),
        "marca": extrair_marca(titulo),
        "nicho": nicho,
        "data": datetime.now(FUSO_BR).isoformat(),
        "link": oferta.get("offerLink", "")
    }

def aplicar_id_afiliado(link):
    if not link:
        return link
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = [AFILIADO_ID]
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

def formatar_preco(oferta):
    preco = oferta.get("price", 0) or 0
    try:
        preco = float(preco)
    except:
        preco = 0
    if preco > 1000:
        preco = preco / 100
    return f"R$ {preco:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def buscar_ofertas(keyword, page=1, limit=50):
    # aqui entra sua chamada real na API
    return []

def coletar_candidatos():
    candidatos = []
    nichos = list(NICHOS.keys())
    random.shuffle(nichos)
    nichos_escolhidos = nichos[:4]

    for nicho in nichos_escolhidos:
        keywords = random.sample(NICHOS[nicho], min(4, len(NICHOS[nicho])))
        for kw in keywords:
            resultados = buscar_ofertas(kw, page=1, limit=50)
            for oferta in resultados:
                oferta["nicho"] = nicho
                if passa_filtros_basicos(oferta) and not ja_enviado(oferta):
                    candidatos.append(oferta)

    return candidatos

def escolher_final(candidatos):
    candidatos.sort(key=score_oferta, reverse=True)
    finais = []
    familias = Counter()
    marcas = Counter()
    nichos = Counter()

    for oferta in candidatos:
        titulo = oferta.get("productName", "")
        familia = extrair_familia(titulo)
        marca = extrair_marca(titulo)
        nicho = oferta.get("nicho", "")

        if nichos[nicho] >= MAX_POR_NICHO:
            continue
        if familias[familia] >= MAX_POR_FAMILIA:
            continue
        if marca and marcas[marca] >= MAX_POR_MARCA:
            continue
        if any(titulo_similar(titulo, x.get("productName", "")) >= 0.82 for x in finais):
            continue

        finais.append(oferta)
        nichos[nicho] += 1
        familias[familia] += 1
        if marca:
            marcas[marca] += 1

        if len(finais) >= MAX_OFERTAS:
            break

    return finais

def gerar_copy(oferta):
    titulo = oferta.get("productName", "")
    preco = formatar_preco(oferta)
    rating = oferta.get("ratingStar", 0)
    vendas = oferta.get("soldCount", 0)
    comissao = oferta.get("commissionRate", "0")
    try:
        comissao = float(str(comissao).replace("%", "").replace(",", ".")) * 100 if float(str(comissao).replace("%", "").replace(",", ".")) <= 1 else float(str(comissao).replace("%", "").replace(",", "."))
    except:
        comissao = 0

    gancho = {
        "Moto": "🏍️ Olha esse achado de moto",
        "Moda Masculina": "👔 Achado forte de moda masculina",
        "Moda Feminina": "👗 Esse destaque de moda feminina está bom demais",
        "Casa": "🏠 Achado de casa que vale a pena",
        "Maternidade": "👶 Oferta de maternidade que costuma girar bem",
        "Eletroeletrônicos": "📱 Eletrônico com boa procura"
    }.get(oferta.get("nicho", ""), "🔥 Oferta selecionada")

    return (
        f"{gancho}!\n\n"
        f"*{titulo}*\n\n"
        f"💰 {preco}\n"
        f"⭐ {rating} | 🛒 {vendas} vendas\n"
        f"Comissão: {comissao}%\n\n"
        f"[COMPRAR AGORA]({aplicar_id_afiliado(oferta.get('offerLink', ''))})\n\n"
        f"[Entrar no grupo de ofertas]({LINK_GRUPO_OFERTAS})"
    )

def gerar_lote():
    candidatos = coletar_candidatos()
    finais = escolher_final(candidatos)
    for oferta in finais:
        registrar_oferta(oferta, oferta.get("nicho", ""))
    salvar_historico()
    return finais

def main():
    carregar_historico()
    while True:
        try:
            ofertas = gerar_lote()
            logging.info(f"Total selecionado: {len(ofertas)}")
            for i, o in enumerate(ofertas, 1):
                logging.info(f"{i}. {o.get('productName', '')}")
            time.sleep(CHECK_INTERVAL)
        except Exception as e:
            logging.exception(e)
            time.sleep(60)

if __name__ == "__main__":
    main()













        


