# PRIMEIRO — TODOS OS IMPORTS
import os
import asyncio, requests, logging, random, hashlib, time, json, html, re, tempfile, secrets
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# AGORA SIM — DEPOIS DOS IMPORTS, roda o diagnóstico
print("=" * 50)
print("🔍 VERIFICANDO VARIÁVEIS DE AMBIENTE...")
print(f"URL_DO_BANCO_DE_DADOS configurada = {bool(os.getenv('URL_DO_BANCO_DE_DADOS'))}")
print(f"DATABASE_URL configurada = {bool(os.getenv('DATABASE_URL'))}")
print("=" * 50)

print("VERSAO V57-CAKTO-CANAIS-DADOS-PERSISTENTES")

try:
    import psycopg2
    from psycopg2.extras import Json
    print("✅ psycopg2 carregado com sucesso")
except Exception as e:
    print(f"⚠️ Erro ao carregar psycopg2: {type(e).__name__}: {e}")
    psycopg2 = None
    Json = None

# =========================
# CONFIG — CORRIGIDO
# =========================
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "").strip()
SHOPEE_APP_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
CHAT_ID_FREE = -1003886228244
AFILIADO_ID = "18349740277"
CAKTO_BOT_USERNAME = (os.getenv("CAKTO_BOT_USERNAME") or "CaktoBot").strip().lstrip("@")

# ✅ Leitura ajustada — PRIORIZA URL_DO_BANCO_DE_DADOS (Railway)
_raw_db_url = os.getenv("URL_DO_BANCO_DE_DADOS") or os.getenv("DATABASE_URL")
if _raw_db_url:
    # Corrige o esquema: postgresql:// → postgres://
    DATABASE_URL = _raw_db_url.replace("postgresql://", "postgres://")
    print(f"✅ URL do banco encontrada e pronta!")
    print("🔗 Endereço do banco carregado (credenciais ocultas).")
else:
    DATABASE_URL = None
    print("⚠️ Nenhuma variável de banco encontrada!")
PLANOS_CAKTO_PRODUTOS = {
    "3092f5b9-4520-4def-8ca7-9bd3401890a5": "semanal",
    "2005e842-e78e-4093-a244-18ab2a180647": "mensal",
    "f13e47fe-2e9e-474a-83b6-d8e7dd73160d": "anual",
}
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400
MAX_OFERTAS = 10
MIN_OFERTAS = 10
OFERTA_FREE = 1
HISTORICO_DIAS = 30
SIMILARIDADE_MAX = .85
VENDAS_MIN = 1
AVALIACAO_MIN = 3.5
PRECO_MIN = 5
PRECO_MAX = 10000
COMISSAO_MIN = 3
VERSAO_RODIZIO = 43
LIMITE_POR_FAMILIA = 1
MAX_PAGINA_BUSCA = 4
TIPOS_ORDEM = [1, 2, 3, 4, 5]

FUSO_BR = ZoneInfo("America/Sao_Paulo")
ARQUIVO_ESTADO = "estado_buscas.json"
ARQUIVO_HISTORICO = "historico_envios.json"

# 🚫 PALAVRAS PROIBIDAS
PALAVRAS_PROIBIDAS = [
    "mousepad", "mouse pad", "tapete de mouse", "almofada de mouse",
    "mouse", "pad mouse", "pad para mouse"
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# =========================
# 🤖 ONBOARDING / CLIENTES
# =========================
CLIENTES_TELEGRAM = "clientes_telegram.json"
CLIENTES_CAKTO = "clientes_cakto.json"
DB_PRONTA = False
DB_AVISO_EMITIDO = False

def _db_conectar():
    if not DATABASE_URL or psycopg2 is None:
        logging.warning("⚠️ Banco indisponível — DATABASE_URL=%s | psycopg2=%s",
                   


