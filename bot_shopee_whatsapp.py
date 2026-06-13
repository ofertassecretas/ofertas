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
print("VERSAO SHOPEE V118 ULTRA - 2 PRODUTOS POR NICHO")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

HISTORICO_FILE = "historico_global_v118.json"
CHECK_INTERVAL = 5400
PRECO_MIN_BASE = 25.0  # Relaxed para Moto
RATING_MIN_BASE = 4.6

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# ASSUNTOS ENJOADOS (BLOQUEIO POR 24H)
# ==========================================

ASSUNTOS_ENJOADOS = [
    "lousa magica",
    "baba eletronica",
    "power bank",
    "passadeira a vapor",
    "passadeira",
    "tenis olympikus",
    "tenis de corrida",
    "repetidor wifi"
]

# ==========================================
# MODELOS DE MOTO (PARA GERAR KEYWORDS)
# ==========================================

MODELOS_MOTO_BR = [
    "Titan 125", "Titan 150", "Titan 160", "CG 100", "CG 110", "Pop 100", "Pop 110",
    "Biz 100", "Biz 125", "Factor 125", "Factor 150", "YBR 125", "YBR 150",
    "Bros 150", "Bros 160", "Twister 250", "Twister 300", "Tornado 250",
    "Sahara 300", "XRE 190", "XRE 300", "CB 300", "CB 400", "CB 500", "CB 600",
    "Crosser 150", "Fazer 150", "Fazer 250", "Neo 115", "Lead 110", "PCX 150",
    "Dafra Next 250", "Lander 250"
]

# ==========================================
# KEYWORDS DOS 5 NICHOS (2 PRODUTOS POR NICHO) - ULTRA
# ==========================================

NICHOS = {
    "Moto": [
        "acessorios moto",
        "partes moto"
    ],
    "Moda": [
        "vestido longo feminino",
        "camisa polo masculina"
    ],
    "Casa": [
        "kit cobre leito",
        "escova limpeza elétrica"
    ],
    "Maternidade": [
        "berço bebê",
        "mochila bebê"
    ],
    "Eletroeletrônicos": [
        "video game stick 4k",
        "smartphone 5g 256gb"
    ]
}

# ==========================================
# BANIMENTOS E BLOQUEIOS
# ==========================================

BLOQUEIO_RADICAL_24H = [
    "serra", "tico tico", "fralda", "fone", "capacete", "pneu", "air fryer", 
    "baba eletronica", "ferro", "batedeira", "mochila", "tenis", "sapato", 
    "furadeira", "parafusadeira", "barraca", "tapete", "patinete", "fone de ouvido"
]

BLOQUEIO_REPETICAO_CICLO = [
    "suporte", "cabo", "carregador", "retrovisor", "bau", "kit relação", "pisca", "manete", "bucha"
]

PALAVRAS_BLOQUEIO_BIKE = [
    "bike", "bicicleta", "shimano", "aro 26", "aro 29", "mtb", "vzan", 
    "mountain bike", "vmaxx", "v-max", "altus", "deore", "gts", "speed", 
    "monark", "caloi", "bmx", "ciclismo", "ciclista", "aro 20", "aro 24"
]

PALAVRAS_BLOQUEIO_BRINQUEDO = [
    "quadriciclo", "quadr", "patinete", "bicicleta", "bike", "brinquedo infantil"
]

PALAVRAS_BLOQUEIO_GERAL = [
    "teste", "amostra", "não compre", "dummy", "adesivo", "película", 
    "case", "filtro de papel", "brinde", "usado", "defeito", "capinha",
    "pano de prato", "mini processador", "ralador manual",
    "spray de pum", "pegadinha", "sal marinho", "esponja magica", "adesivo retalho",
    "bico desentupidor", "ventosa", "barra estabilizadora", "coxim", "cavalete lateral",
    "filtro refil", "tampa geladeira", "narigueira", "rede elastica", "fecho porta",
    "organizador gaveta", "caneca infantil", "suporte de baba"
] + PALAVRAS_BLOQUEIO_BIKE + PALAVRAS_BLOQUEIO_BRINQUEDO

# ==========================================
# GESTÃO DE MEMÓRIA
# ==========================================

def normalizar_texto(txt):
    if not txt: return ""
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ]", " ", txt) 
    return " ".join(txt.split())

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
        agora = datetime.now()
        limite = agora - timedelta(hours=72)
        historico_limpo = {k: v for k, v in historico.items() if datetime.fromisoformat(v.get("data", agora.isoformat())) > limite}
        with open(HISTORICO_FILE, 'w') as f:
            json.dump(historico_limpo, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
    except Exception as e:
        logging.error(f"Erro ao salvar historico: {e}")

def eh_repetido_master_fix(titulo, historico_global, lista_ciclo_atual, nicho_atual=None):
    t_novo_norm = normalizar_texto(titulo)
    
    # 1) BLOQUEIO POR ASSUNTO ENJOADO (24H)
    for assunto in ASSUNTOS_ENJOADOS:
        if assunto in t_novo_norm:
            agora = datetime.now()
            for item in historico_global.values():
                t_antigo_norm = normalizar_texto(item.get("titulo", ""))
                data_envio = datetime.fromisoformat(item.get("data", agora.isoformat()))
                if assunto in t_antigo_norm and (agora - data_envio).total_seconds() < 24 * 3600:
                    return True

    # 2) BLOQUEIO POR RADICAL EXISTENTE NO CICLO ATUAL
    for termo in BLOQUEIO_REPETICAO_CICLO + BLOQUEIO_RADICAL_24H:
        if termo in t_novo_norm:
            for p_ja_escolhido in lista_ciclo_atual:
                if termo in normalizar_texto(p_ja_escolhido.get("productName", "")):
                    return True

    # 3) SIMILARIDADE DENTRO DO CICLO ATUAL (evita itens muito parecidos na mesma rodada)
    for p_atual in lista_ciclo_atual:
        t_atual_norm = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo_norm, t_atual_norm).ratio() > 0.30:
            return True

    # 4) BLOQUEIO POR RADICAL EM HISTÓRICO (24H)
    agora = datetime.now()
    for radical in BLOQUEIO_RADICAL_24H:
        if radical in t_novo_norm:
            for item in historico_global.values():
                data_envio = datetime.fromisoformat(item.get("data", agora.isoformat()))
                if radical in normalizar_texto(item.get("titulo", "")) and (agora - data_envio).total_seconds() < 86400:
                    return True

    # 5) BLOQUEIO POR HASH / SIMILARIDADE COM HISTÓRICO (72H)
    h_novo = hashlib.md5(t_novo_norm[:60].encode()).hexdigest()
    
    # 5.1 Hash igual → já mandou esse produto
    if h_novo in historico_global:
        return True

    # 5.2 Similaridade forte com itens recentes do mesmo nicho
    for h, item in historico_global.items():
        t_hist_norm = normalizar_texto(item.get("titulo", ""))
        nicho_hist = item.get("nicho")
        ratio = SequenceMatcher(None, t_novo_norm, t_hist_norm).ratio()
        # Se for o mesmo nicho e título muito parecido, bloqueia
        if nicho_atual and nicho_hist and nicho_atual == nicho_hist and ratio > 0.70:
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

<a href="{zap_link}">📲 Compartir no WhatsApp</a>

━━━━━━━━━━━━━━━
📢 <b>Ofertas Secretas</b>"""

# ==========================================
# INTEGRAÇÃO SHOPEE (GOD MODE)
# ==========================================

def buscar_shopee_god_mode(keyword):
    timestamp = int(time.time())
    query_body = f"""
    query {{
        productOfferV2(
            keyword: "{keyword}",
            sortType: 2,
            isAMSOffer: true,
            isKeySeller: true,
            limit: 50
        ) {{
            nodes {{
                productName
                priceMin
                commissionRate
                sales
                ratingStar
                productLink
                offerLink
                imageUrl
                shopName
                shopType
            }}
        }}
    }}
    """
    payload = json.dumps({"query": query_body})
    base_str = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base_str.encode()).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }
    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=25)
        data = r.json()
        return data.get("data", {}).get("productOfferV2", {}).get("nodes", [])
    except Exception as e:
        logging.error(f"Erro na API Shopee: {e}")
        return []

def aplicar_afiliado(link):
    try:
        parsed = urlparse(link)
        query = parse_qs(parsed.query)
        query["af_siteid"] = AFILIADO_ID
        return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))
    except:
        return link

# ==========================================
# LÓGICA DE SELEÇÃO DE OFERTAS (V118 ULTRA - 2 PRODUTOS POR NICHO)
# ==========================================

def get_melhores_ofertas():
    historico_global = carregar_historico()
    ofertas_finais = []
    
    logging.info("=== INÍCIO DO CICLO V118 ULTRA - 2 PRODUTOS POR NICHO ===")
    
    for nicho, keywords in NICHOS.items():
        logging.info(f"\n=== NICHO: {nicho} (2 produtos) ===")
        
        produtos_nicho = []
        
        # Para Moto: cruza keyword genérica com modelo aleatório e filtra manualmente
        for kw in keywords:
            if nicho == "Moto":
                kw_com_modelo = f"{kw} {random.choice(MODELOS_MOTO_BR)}"
                logging.info(f"  Keyword moto com modelo: '{kw_com_modelo}'")
                produtos = buscar_shopee_god_mode(kw_com_modelo)
                # Filtra manualmente por palavras de moto
                produtos = [p for p in produtos if any(w in p.get("productName", "").lower() for w in ["moto", "freio", "relação", "coroa", "pinhão", "burrinho", "guidão", "capacete", "pneu"])]
            else:
                produtos = buscar_shopee_god_mode(kw)
            
            logging.info(f"  Keyword '{kw}': {len(produtos)} produtos da API")
            produtos_nicho.extend(produtos)
        
        if not produtos_nicho:
            logging.warning(f"  → Nenhum produto encontrado para o nicho {nicho}")
            continue
        
        # Remove duplicatas por nome
        produtos_unicos = []
        nomes_vistos = set()
        for p in produtos_nicho:
            nome = normalizar_texto(p.get("productName", ""))
            if nome and nome not in nomes_vistos:
                nomes_vistos.add(nome)
                produtos_unicos.append(p)
        
        logging.info(f"  Total único no nicho: {len(produtos_unicos)}")
        
        # Filtra por preço/vendas/rating
        produtos_filtrados = []
        for p in produtos_unicos:
            nome = p.get("productName", "")
            preco = float(p.get("priceMin", 0) or 0)
            vendas = int(p.get("sales", 0) or 0)
            rating = float(p.get("ratingStar", 0) or 0)
            
            # Bloqueio por palavra
            if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO_GERAL):
                continue
            
            # Preço mínimo
            if preco < PRECO_MIN_BASE:
                continue
            
            # Teto de preço por nicho
            if nicho == "Moto" and preco > 850:
                continue
            
            # Mínimo de vendas
            # Moto: relaxa para 5
            # Maternidade: relaxa para 10
            # Casa: relaxa para 20
            if nicho == "Moto":
                v_necessarias = 5
            elif nicho == "Maternidade":
                v_necessarias = 5 if preco > 300 else 10
            elif nicho == "Casa":
                v_necessarias = 20
            else:
                v_necessarias = 5 if preco > 300 else 35
            
            if vendas < v_necessarias:
                continue
            
            # Rating mínimo
            if rating < RATING_MIN_BASE:
                continue
            
            # Repetidos globais
            if eh_repetido_master_fix(nome, historico_global, ofertas_finais, nicho_atual=nicho):
                continue
            
            # Similaridade dentro do nicho (evita produtos quase iguais na mesma rodada)
            if produtos_filtrados:
                similar_com_nicho = False
                nome_norm = normalizar_texto(nome)
                for p_nicho in produtos_filtrados:
                    t_nicho_norm = normalizar_texto(p_nicho.get("productName", ""))
                    ratio = SequenceMatcher(None, nome_norm, t_nicho_norm).ratio()
                    
                    # Se é Eletro e já tem "game stick" ou "smartphone xiaomi/poco/redmi", evita concorrente idêntico
                    if nicho == "Eletroeletrônicos":
                        if ("game stick" in nome_norm and "game stick" in t_nicho_norm) and ratio > 0.50:
                            similar_com_nicho = True
                            break
                        if ("smartphone" in nome_norm and "smartphone" in t_nicho_norm) and ratio > 0.65:
                            similar_com_nicho = True
                            break
                    
                    # Moto: escapamentos muito parecidos
                    if nicho == "Moto" and ratio > 0.60:
                        similar_com_nicho = True
                        break
                    
                    # Casa / Maternidade: escovas/berços muito parecidos
                    if nicho in ["Casa", "Maternidade"] and ratio > 0.65:
                        similar_com_nicho = True
                        break
                
                if similar_com_nicho:
                    continue
            
            produtos_filtrados.append(p)
        
        logging.info(f"  Produtos após filtro: {len(produtos_filtrados)}")
        
        if not produtos_filtrados:
            logging.warning(f"  → Nenhum produto válido no nicho {nicho}")
            continue
        
        # Sort por vendas (desc)
        produtos_filtrados.sort(key=lambda x: int(x.get("sales", 0) or 0), reverse=True)
        
        # Pega os 2 melhores
        melhores = produtos_filtrados[:2]
        
        for p in melhores:
            p["nicho"] = nicho
            ofertas_finais.append(p)
        
        logging.info(f"  → Selecionados {len(melhores)} produtos para {nicho}")
        for mp in melhores:
            logging.info(f"      - {mp.get('productName')} | R$ {float(mp.get('priceMin',0)):.2f} | {int(mp.get('sales',0))} vendas | {float(mp.get('ratingStar',0)):.2f}⭐")
    
    logging.info(f"\n=== FINAL: Total de ofertas = {len(ofertas_finais)} ===")
    
    return ofertas_finais[:10]

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(FUSO_BR).time()
    if not (dt_time(5, 30) <= agora <= dt_time(21, 30)): return
    logging.info("Iniciando ciclo V118 ULTRA - 2 produtos por nicho...")
    ofertas = get_melhores_ofertas()
    if not ofertas:
        logging.warning("Nenhuma oferta encontrada neste ciclo.")
        return
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
            t_norm = normalizar_texto(item["productName"])
            h = hashlib.md5(t_norm[:60].encode()).hexdigest()
            historico_global[h] = {
                "data": datetime.now().isoformat(),
                "titulo": item["productName"],
                "nicho": item.get("nicho")
            }
            salvar_historico(historico_global)
            await asyncio.sleep(60) 
        except Exception as e:
            logging.error(f"Erro no envio: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V118 ULTRA - 2 Produtos Por Nicho Ativo!")

if __name__ == "__main__":
    if TELEGRAM_TOKEN:
        ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build().run_polling()
    else:
        print("Erro: TELEGRAM_TOKEN não configurado.")













        


