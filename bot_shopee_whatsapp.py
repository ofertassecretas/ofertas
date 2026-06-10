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
print("VERSAO SHOPEE V91 - FIX ERROR (BANIMENTO 24H & ROTACAO DE NICHOS)")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Arquivos de memória persistente
HISTORICO_FILE = "historico_global_v91.json"

# Intervalo entre ciclos (em segundos)
CHECK_INTERVAL = 5400

# FILTROS BASE
PRECO_MIN_BASE = 30.0
RATING_MIN_BASE = 4.6

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# ESTRATÉGIA DE BUSCA EXPERT (ROTATIVA)
# ==========================================

KEYWORDS_POOL = {
    "Motos_Real": [
        ["Capacete EBF", "Capacete Pro Tork", "Capacete Mixs"],
        ["Pneu Levorin", "Pneu Maggion", "Pneu Technic"],
        ["Kit Relação Vaz", "Kit Transmissão KMC", "Corrente Did"],
        ["Capa de Chuva Pantaneiro", "Bota Impermeável", "Luva Couro"],
        ["Óleo Mobil 10w30", "Óleo Yamalube", "Filtro Óleo Vedamotors"],
        ["Baú Pro Tork", "Retrovisor Esportivo", "Alarme Pósitron"]
    ],
    "Tecnologia_Util": [
        ["Fone Bluetooth JBL", "Fone Lenovo LP40", "Fone QCY"],
        ["Smartwatch Iwo", "Relógio Digital Casio", "Mi Band"],
        ["Carregador Turbo Samsung", "Power Bank Pineng", "Cabo USB-C Baseus"],
        ["Suporte Celular Imã", "Suporte Guidão Moto", "Intercomunicador V6"]
    ],
    "Eletro_Desejo": [
        ["Air Fryer Mondial", "Fritadeira Philco", "Air Fryer Britânia"],
        ["Batedeira Arno", "Liquidificador Oster", "Mixer Philips"],
        ["Ferro de Passar Elgin", "Vaporizador de Roupas", "Ferro Black Decker"],
        ["Ventilador Turbo Arno", "Climatizador Ventisol", "Circulador de Ar"]
    ],
    "Casa_e_Ferramentas": [
        ["Jogo de Chaves", "Furadeira Impacto", "Parafusadeira Vonder"],
        ["Mochila Notebook", "Mochila Motoboy", "Bolsa Térmica"],
        ["Lâmpada Inteligente", "Fita LED RGB", "Sensor de Presença"],
        ["Tênis Olympikus", "Sapato Social", "Bota de Segurança"]
    ],
    "Bebe_Util": [
        ["Fralda Pampers G", "Fralda Huggies M", "Fralda Babysec"],
        ["Babá Eletrônica VB601", "Câmera Monitoramento", "Babá Visão Noturna"],
        ["Carrinho Galzerano", "Cadeira de Descanso", "Cadeira Auto"],
        ["Kit Higiene Bebê", "Termômetro Digital", "Aspirador Nasal"]
    ]
}

PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "não compre", "dummy", "adesivo", "película", 
    "case", "filtro de papel", "brinde", "usado", "defeito", "capinha",
    "pano de prato", "meia", "cueca", "calcinha", "mini processador", "ralador manual",
    "spray de pum", "pegadinha", "sal marinho", "esponja magica", "adesivo retalho",
    "bico desentupidor", "ventosa", "barra estabilizadora", "coxim", "cavalete lateral",
    "filtro refil", "tampa geladeira", "narigueira", "rede elastica", "fecho porta",
    "organizador gaveta", "caneca infantil", "suporte de baba"
]

# ==========================================
# GESTÃO DE MEMÓRIA EXPERT (BANIMENTO 24H)
# ==========================================

def normalizar_texto(txt):
    if not txt: return ""
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ]", "", txt) 
    return txt

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

def eh_repetido_expert(titulo, historico_global, lista_ciclo_atual):
    t_novo = normalizar_texto(titulo)
    h = hashlib.md5(t_novo[:40].encode()).hexdigest()
    
    if h in historico_global: return True
    
    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.35:
            return True

    termos_banidos = ["fralda", "baba eletronica", "suporte", "pneu", "capacete", "air fryer", "fone", "carregador"]
    agora = datetime.now()
    for termo in termos_banidos:
        if termo in t_novo:
            for item in historico_global.values():
                data_envio = datetime.fromisoformat(item.get("data", agora.isoformat()))
                if termo in normalizar_texto(item.get("titulo", "")) and (agora - data_envio).total_seconds() < 86400:
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
    
    # CORRIGIDO: Nomes das categorias agora coincidem com o dicionário
    categorias_alvo = ["Motos_Real", "Tecnologia_Util", "Eletro_Desejo", "Casa_e_Ferramentas", "Bebe_Util"]
    
    for cat_name in categorias_alvo:
        vagas_preenchidas = 0
        
        sub_listas = KEYWORDS_POOL[cat_name].copy()
        random.shuffle(sub_listas)
        
        for sub_lista in sub_listas:
            if vagas_preenchidas >= 2: break
            
            tentativas_sub = 0
            while tentativas_sub < 5 and vagas_preenchidas < 2:
                tentativas_sub += 1
                kw = random.choice(sub_lista)
                produtos = buscar_shopee(kw)
                if not produtos: continue
                
                random.shuffle(produtos)
                for p in produtos:
                    nome = p.get("productName", "")
                    preco = float(p.get("priceMin", 0))
                    vendas = int(p.get("sales", 0))
                    
                    if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO): continue
                    if preco < PRECO_MIN_BASE: continue
                    
                    if cat_name == "Motos_Real" and preco > 480: continue
                    
                    if cat_name != "Motos_Real" and any(m in nome.lower() for m in ["moto", "capacete", "pneu"]):
                        continue

                    v_necessarias = 15 if preco > 150 else 40
                    if vendas < v_necessarias: continue
                    if float(p.get("ratingStar", 0)) < RATING_MIN_BASE: continue
                    
                    if eh_repetido_expert(nome, historico_global, ofertas_finais): continue
                    
                    p["cat"] = cat_name
                    ofertas_finais.append(p)
                    vagas_preenchidas += 1
                    break
                    
    return ofertas_finais[:10]

# ==========================================
# EXECUÇÃO DO BOT
# ==========================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(FUSO_BR).time()
    if not (dt_time(5, 30) <= agora <= dt_time(21, 30)): return

    logging.info("Iniciando ciclo V91 Fix Error...")
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
            
            t_norm = normalizar_texto(item["productName"])
            h = hashlib.md5(t_norm[:40].encode()).hexdigest()
            historico_global[h] = {"data": datetime.now().isoformat(), "titulo": item["productName"]}
            salvar_historico(historico_global)
            
            await asyncio.sleep(60) 
        except Exception as e:
            logging.error(f"Erro no envio: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V91 Ativo!")

if __name__ == "__main__":
    if TELEGRAM_TOKEN:
        ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build().run_polling()
    else:
        print("Erro: TELEGRAM_TOKEN não configurado.")














        


