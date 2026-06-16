import asyncio
import requests
import logging
import random
import hashlib
import time
import json
import os
import re
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

print("VERSAO SHOPEE V120 CURADORA - VARIEDADE REAL + ANTI-REPETICAO (FIXED)")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
AFILIADO_ID = "18349740277"

HISTORICO_FILE = "historico_global_v120.json"
CHECK_INTERVAL = 5400

MAX_OFERTAS = 10
MIN_OFERTAS = 6

MIN_PRECO = 12.0
MAX_PRECO = 1000.0

# 🔧 AJUSTE IMPORTANTE (menos agressivo)
MIN_RATING = 4.3
MIN_VENDAS = 5

MAX_POR_NICHO = 2
MAX_POR_FAMILIA = 2   # antes 1 (estava matando variedade)
MAX_POR_MARCA = 1

JANELA_FAMILIA_DIAS = 3   # antes 10
JANELA_MARCA_DIAS = 2     # antes 7
JANELA_HISTORICO_DIAS = 15

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# =========================
# NICHOS (mantido igual)
# =========================
NICHOS = {
    "Moto": [
        "escapamento moto", "pneu moto", "retrovisor moto",
        "capacete moto", "bateria moto", "kit relacao moto"
    ],
    "Moda Masculina": [
        "camisa social masculina", "camisa polo masculina",
        "calca jeans masculina", "tenis masculino"
    ],
    "Moda Feminina": [
        "vestido feminino", "blusa feminina", "saia feminina",
        "bolsa feminina", "tenis feminino"
    ],
    "Casa": [
        "air fryer", "aspirador", "mop",
        "organizador cozinha", "cafeteira"
    ],
    "Maternidade": [
        "mochila maternidade", "carrinho bebe",
        "berco bebe", "chocalho bebe"
    ],
    "Eletroeletrônicos": [
        "smartwatch", "fone bluetooth",
        "ssd", "power bank"
    ]
}

PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "dummy", "brinde", "usado", "defeito",
    "película", "capinha", "adesivo"
]

HISTORICO = {}

# =========================
# HISTÓRICO
# =========================
def carregar_historico():
    global HISTORICO
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                HISTORICO = json.load(f)
        except:
            HISTORICO = {}

def salvar_historico():
    agora = datetime.now(FUSO_BR)
    limite = agora - timedelta(days=JANELA_HISTORICO_DIAS)

    limpo = {}
    for k, v in HISTORICO.items():
        try:
            if datetime.fromisoformat(v["data"]) >= limite:
                limpo[k] = v
        except:
            continue

    with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
        json.dump(limpo, f, ensure_ascii=False, indent=2)

# =========================
# NORMALIZAÇÃO
# =========================
def normalizar(txt):
    if not txt:
        return ""
    txt = txt.lower()
    txt = re.sub(r"[^a-z0-9à-ÿ\s]", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()

def titulo_similar(a, b):
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()

# =========================
# EXTRAÇÃO
# =========================
def extrair_familia(titulo):
    t = normalizar(titulo)

    grupos = {
        "vestido": ["vestido"],
        "camisa": ["camisa", "polo"],
        "calca": ["calca"],
        "tenis": ["tenis"],
        "moto": ["escapamento", "capacete", "pneu"],
        "casa": ["air fryer", "aspirador", "mop"],
        "bebe": ["berco", "chocalho", "carrinho"]
    }

    for fam, termos in grupos.items():
        if any(x in t for x in termos):
            return fam

    return "outros"

def extrair_marca(titulo):
    t = normalizar(titulo)
    marcas = ["nike", "adidas", "honda", "yamaha", "xiaomi", "samsung", "lovito"]
    for m in marcas:
        if m in t:
            return m
    return ""

# =========================
# FILTROS
# =========================
def passa_filtros_basicos(oferta):
    titulo = normalizar(oferta.get("productName", ""))
    if not titulo:
        return False

    if any(p in titulo for p in PALAVRAS_BLOQUEIO):
        return False

    preco = float(oferta.get("price", 0) or 0)
    rating = float(oferta.get("ratingStar", 0) or 0)
    vendas = int(oferta.get("soldCount", 0) or 0)

    comissao = oferta.get("commissionRate", 0)
    try:
        comissao = float(str(comissao).replace("%", ""))
    except:
        comissao = 0

    if preco < MIN_PRECO or preco > MAX_PRECO:
        return False
    if rating < MIN_RATING:
        return False
    if vendas < MIN_VENDAS:
        return False
    if comissao < 3:
        return False

    return True

# =========================
# REPETIÇÃO (MENOS AGRESSIVA)
# =========================
def ja_enviado(oferta):
    titulo = oferta.get("productName", "")
    fam = extrair_familia(titulo)
    marca = extrair_marca(titulo)

    for item in HISTORICO.values():
        if titulo_similar(titulo, item.get("titulo", "")) >= 0.92:
            return True

        if fam and fam == item.get("familia"):
            dt = datetime.fromisoformat(item["data"])
            if datetime.now(FUSO_BR) - dt < timedelta(days=JANELA_FAMILIA_DIAS):
                return True

        if marca and marca == item.get("marca"):
            dt = datetime.fromisoformat(item["data"])
            if datetime.now(FUSO_BR) - dt < timedelta(days=JANELA_MARCA_DIAS):
                return True

    return False

# =========================
# SCORE
# =========================
def score_oferta(oferta):
    vendas = int(oferta.get("soldCount", 0))
    rating = float(oferta.get("ratingStar", 0))
    comissao = float(oferta.get("commissionRate", 0) or 0)

    score = 0
    score += min(vendas, 5000) / 60   # ajustado
    score += rating * 18
    score += comissao * 60

    return score

# =========================
# API (placeholder)
# =========================
def buscar_ofertas(keyword, page=1, limit=50):
    return []

# =========================
# COLETA
# =========================
def coletar_candidatos():
    candidatos = []
    nichos = list(NICHOS.keys())   # FIX: usa todos

    for nicho in nichos:
        keywords = random.sample(NICHOS[nicho], len(NICHOS[nicho]))

        for kw in keywords:
            resultados = buscar_ofertas(kw)

            for o in resultados:
                o["nicho"] = nicho

                if passa_filtros_basicos(o) and not ja_enviado(o):
                    candidatos.append(o)

    return candidatos

# =========================
# SELEÇÃO FINAL
# =========================
def escolher_final(candidatos):
    candidatos.sort(key=score_oferta, reverse=True)

    finais = []
    cont_nicho = Counter()
    cont_fam = Counter()
    cont_marca = Counter()

    for o in candidatos:
        titulo = o.get("productName", "")
        nicho = o.get("nicho", "")
        fam = extrair_familia(titulo)
        marca = extrair_marca(titulo)

        if cont_nicho[nicho] >= MAX_POR_NICHO:
            continue
        if cont_fam[fam] >= MAX_POR_FAMILIA:
            continue
        if marca and cont_marca[marca] >= MAX_POR_MARCA:
            continue

        if any(titulo_similar(titulo, x["productName"]) > 0.92 for x in finais):
            continue

        finais.append(o)
        cont_nicho[nicho] += 1
        cont_fam[fam] += 1
        if marca:
            cont_marca[marca] += 1

        if len(finais) >= MAX_OFERTAS:
            break

    return finais

# =========================
# EXECUÇÃO
# =========================
def gerar_lote():
    candidatos = coletar_candidatos()
    finais = escolher_final(candidatos)

    for f in finais:
        chave = hashlib.md5(normalizar(f["productName"]).encode()).hexdigest()
        HISTORICO[chave] = {
            "titulo": f["productName"],
            "familia": extrair_familia(f["productName"]),
            "marca": extrair_marca(f["productName"]),
            "data": datetime.now(FUSO_BR).isoformat()
        }

    salvar_historico()
    return finais

def main():
    carregar_historico()

    while True:
        try:
            ofertas = gerar_lote()
            logging.info(f"Total selecionado: {len(ofertas)}")

            for i, o in enumerate(ofertas, 1):
                logging.info(f"{i}. {o.get('productName')}")

            time.sleep(CHECK_INTERVAL)

        except Exception as e:
            logging.exception(e)
            time.sleep(60)

if __name__ == "__main__":
    main()













        


