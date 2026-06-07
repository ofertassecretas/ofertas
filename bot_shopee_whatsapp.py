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
from difflib import SequenceMatcher
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

# ==========================================
# CONFIGURAÇÕES BÁSICAS
# ==========================================
print("VERSAO SHOPEE V70 - TOTAL MEMORY & KEYWORD ROTATION")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Arquivos de memória persistente (Global)
HISTORICO_FILE = "historico_global_v70.json"

# Intervalo entre ciclos (em segundos)
CHECK_INTERVAL = 5400

# FILTROS VIP
PRECO_MIN_VIP = 50.0
RATING_MIN_VIP = 4.6

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# ESTRATÉGIA DE ROTAÇÃO DE BUSCA
# ==========================================

KEYWORDS_POOL = {
    "Tecnologia": [
        "iPhone 15", "Samsung S24", "Playstation 5", "Nintendo Switch", "Macbook M2", 
        "iPad Pro", "JBL Partybox", "Sony WH-1000XM5", "Monitor Gamer 144hz", "Placa Video RTX"
    ],
    "Eletro": [
        "Geladeira Frost Free", "Lava e Seca", "Ar Condicionado Inverter", "Microondas Inox",
        "Air Fryer Mondial", "Robo Aspirador Xiaomi", "Lava Louças", "Purificador Agua"
    ],
    "Motos": [
        "Pneu Pirelli Moto", "Capacete LS2", "Jaqueta Alpinestars", "Bau Givi", "Intercomunicador V6",
        "Kit Relação DID", "Pneu Metzeler", "Capacete Norisk", "Luva Couro Moto", "Bota Macboot"
    ],
    "Casa_Lazer": [
        "Cadeira Escritorio Ergonômica", "Bicicleta Aro 29", "Piscina Estruturada", "Churrasqueira Gourmet",
        "Cama Box Queen", "Barraca Camping 4 pessoas", "Mesa Dobravel Maleta", "Bicicleta Spinning"
    ],
    "Bebe_Elite": [
        "Carrinho Chicco", "Cadeira Auto Fisher Price", "Baba Eletronica Motorola", "Berço Burigotto"
    ]
}

PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "não compre", "dummy", "adesivo", "película", 
    "case", "filtro de papel", "brinde", "usado", "defeito", "capinha",
    "pano de prato", "meia", "cueca", "calcinha", "mini processador", "ralador manual",
    "spray de pum", "pegadinha", "sal marinho", "esponja magica", "adesivo retalho",
    "bico desentupidor", "ventosa", "barra estabilizadora", "coxim", "cavalete lateral",
    "filtro refil", "tampa geladeira", "suporte celular moto", "capa banco moto", "balaclava"
]

# ==========================================
# GESTÃO DE MEMÓRIA GLOBAL (BLINDADA)
# ==========================================

def normalizar_texto(txt):
    if not txt: return ""
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ]", "", txt) 
    return txt

def gerar_hash_produto(titulo):
    # Usamos os primeiros 30 caracteres do título normalizado para o hash
    # Isso evita que variações mínimas (ex: "Cor: Azul") burlem o bloqueio
    texto_limpo = normalizar_texto(titulo)[:30]
    return hashlib.md5(texto_limpo.encode()).hexdigest()

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_historico(historico):
    try:
        # Mantém apenas os últimos 500 produtos para não crescer infinitamente
        if len(historico) > 500:
            chaves_ordenadas = sorted(historico.keys(), key=lambda k: historico[k].get("data", ""), reverse=True)
            historico = {k: historico[k] for k in chaves_ordenadas[:500]}
            
        with open(HISTORICO_FILE, 'w') as f:
            json.dump(historico, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        logging.error(f"Erro ao salvar historico: {e}")

def eh_repetido_global(titulo, historico_global, lista_ciclo_atual):
    h = gerar_hash_produto(titulo)
    if h in historico_global: return True
    
    t_novo = normalizar_texto(titulo)
    # Bloqueio de similaridade agressivo (40%)
    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.40:
            return True
            
    # Bloqueio por palavras-chave já enviadas no ciclo (evita 2 pneus, 2 capacetes, etc)
    termos_unicos = ["pneu", "capacete", "jaqueta", "bau", "kit relação", "cadeira", "bicicleta", "air fryer", "geladeira", "iphone", "ps5"]
    for termo in termos_unicos:
        if termo in t_novo:
            for p_ja_escolhido in lista_ciclo_atual:
                if termo in normalizar_texto(p_ja_escolhido.get("productName", "")):
                    return True
    return False

# ==========================================
# LÓGICA DE MENSAGENS
# ==========================================

def gerar_copy_base(nome, preco, vendas, avaliacao, comissao, link, for_whatsapp=False):
    aberturas = ["🤯 Sério… olha esse achado!", "🚨 Isso aqui não aparece toda hora!", "👀 Achei agora e vim correndo postar!", "🔥 OPORTUNIDADE QUENTE!", "💥 Esse aqui tá com um preço absurdo!", "🛑 PARA TUDO e olha esse desconto!", "⚠️ Alerta de estoque baixo!", "🚀 Esse aqui vai voar rápido!"]
    gatilhos = ["Preço muito abaixo do mercado", "Avaliações excelentes dos compradores", "Campeão de vendas na categoria", "Custo-benefício imbatível", "Qualidade premium garantida", "O queridinho do momento"]
    chamadas_acao = ["⚡ CLIQUE ANTES QUE O PREÇO SUBA!", "🔥 ESTOQUE LIMITADO - APROVEITE!", "🚀 COMPRE AGORA COM DESCONTO!", "🎯 GARANTA O SEU ANTES QUE ACABE!", "💰 ECONOMIA REAL SÓ HOJE!"]

    abertura = random.choice(aberturas)
    gatilho = random.choice(gatilhos)
    chamada = random.choice(chamadas_acao)

    if for_whatsapp:
        return f"{abertura}\n\n*🔥 {nome}*\n\n📌 {gatilho}\n\n{chamada}\n\n💰 *R$ {preco}*\n⭐ *{avaliacao}* | 🛒 *{vendas} vendas*\n\n⚠️ *Pode subir de preço*\n\n🛒 *COMPRAR:* {link}\n\n📲 *ENTRE NO NOSSO GRUPO:* {LINK_GRUPO_OFERTAS}"

    zap_msg = gerar_copy_base(nome, preco, vendas, avaliacao, comissao, link, for_whatsapp=True)
    zap_link = f"https://wa.me/?text={quote(zap_msg)}"

    return f"""{abertura}

🔥 <b>{nome}</b>

📌 {gatilho}

{chamada}

💰 <b>R$ {preco}</b>
⭐ <b>{avaliacao} | {vendas} vendas</b>
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>

<a href="{LINK_GRUPO_OFERTAS}">📲 Entrar no grupo de ofertas</a>

<a href="{zap_link}">📲 Compartilhar no WhatsApp</a>

━━━━━━━━━━━━━━━
📢 <b>Ofertas Secretas</b>"""

# ==========================================
# INTEGRAÇÃO SHOPEE
# ==========================================

def buscar_shopee(keyword):
    timestamp = int(time.time())
    query_body = f'query {{ productOfferV2(sortType: 2, limit: 50, keyword: "{keyword}", isAMSOffer: true) {{ nodes {{ productName priceMin commissionRate sales ratingStar productLink offerLink imageUrl }} }} }}'
    payload = json.dumps({"query": query_body})
    base_str = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base_str.encode()).hexdigest()
    headers = {"Content-Type": "application/json", "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"}
    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        return r.json().get("data", {}).get("productOfferV2", {}).get("nodes", [])
    except:
        return []

def aplicar_afiliado(link):
    try:
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        query["af_siteid"] = AFILIADO_ID
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    except:
        return link

def get_melhores_ofertas():
    historico_global = carregar_historico()
    ofertas_finais = []
    
    # 1. Escolhe 10 categorias aleatórias para garantir rotação (sempre incluindo Motos)
    categorias_para_ciclo = ["Motos", "Motos"] # Garante 2 vagas de motos
    outras_opcoes = ["Tecnologia", "Eletro", "Casa_Lazer", "Bebe_Elite"]
    while len(categorias_para_ciclo) < 10:
        categorias_para_ciclo.append(random.choice(outras_opcoes))
    
    random.shuffle(categorias_para_ciclo)

    for cat in categorias_para_ciclo:
        # Pega uma keyword aleatória daquela categoria
        kw = random.choice(KEYWORDS_POOL[cat])
        produtos = buscar_shopee(kw)
        if not produtos: continue
        
        # Embaralha os resultados da Shopee para não pegar sempre o primeiro
        random.shuffle(produtos)
        
        for p in produtos:
            nome = p.get("productName", "")
            preco = float(p.get("priceMin", 0))
            vendas = int(p.get("sales", 0))
            
            if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO): continue
            if preco < PRECO_MIN_VIP: continue
            
            # Filtro Proporcional
            v_necessarias = 5 if preco > 200 else 50
            if vendas < v_necessarias: continue
            if float(p.get("ratingStar", 0)) < RATING_MIN_VIP: continue
            
            if eh_repetido_global(nome, historico_global, ofertas_finais): continue
            
            ofertas_finais.append(p)
            break # Encontrou um bom para esta vaga, pula para a próxima categoria
            
    return ofertas_finais[:10]

# ==========================================
# EXECUÇÃO DO BOT
# ==========================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(FUSO_BR).time()
    if not (dt_time(5, 30) <= agora <= dt_time(21, 00)): return

    logging.info("Iniciando ciclo V70 Total Memory...")
    ofertas = get_melhores_ofertas()
    if not ofertas: return

    await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 <b>OFERTAS SELECIONADAS DE HOJE!</b>\n<i>Produtos de alta qualidade e com o melhor preço.</i>", parse_mode="HTML")
    await asyncio.sleep(3)

    historico_global = carregar_historico()
    for item in ofertas:
        try:
            nome = html.escape(item["productName"])
            link_afiliado = aplicar_afiliado(item.get("offerLink") or item.get("productLink"))
            preco = f"{float(item['priceMin']):.2f}".replace(".", ",")
            vendas = f"{int(item['sales']):,}".replace(",", ".")
            comissao_val = round(float(item.get("commissionRate", 0)) * 100, 1)
            msg = gerar_copy_base(nome, preco, vendas, item.get("ratingStar", 5.0), comissao_val, link_afiliado)
            
            await context.bot.send_photo(chat_id=CHAT_ID_DESTINO, photo=item.get("imageUrl"), caption=msg, parse_mode="HTML")
            
            h = gerar_hash_produto(item["productName"])
            historico_global[h] = {"data": datetime.now().isoformat(), "titulo": item["productName"]}
            salvar_historico(historico_global)
            
            await asyncio.sleep(60) 
        except Exception as e:
            logging.error(f"Erro no envio: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V70 Ativo!")

if __name__ == "__main__":
    if TELEGRAM_TOKEN:
        ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build().run_polling()
    else:
        print("Erro: TELEGRAM_TOKEN não configurado.")










        


