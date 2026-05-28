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
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

# ==========================================
# CONFIGURAÇÕES BÁSICAS
# ==========================================
print("VERSAO SHOPEE V17 - MEMÓRIA PERSISTENTE & MOTO PESADA")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Caminho para o arquivo de memória (Salva mesmo se o bot reiniciar)
HISTORICO_FILE = "historico_envios.json"

# Intervalo entre ciclos (em segundos) - 5400s = 1h30
CHECK_INTERVAL = 5400

# Filtros de Qualidade (Aumentados para evitar "produtos pobres")
PRECO_MIN = 35.0 # Aumentado para evitar quinquilharias
PRECO_MAX = 15000.0
COMISSAO_MIN = 0.07
VENDAS_MIN = 100 # Aumentado para pegar apenas o que vende muito
RATING_MIN = 4.6 # Aumentado para pegar só os melhores avaliados

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# NICHOS E SUBCATEGORIAS (TURBINADOS)
# ==========================================

KEYWORDS_ESTRUTURADAS = {
    "Casa e Eletro": {
        "TV": ["Smart TV 50 4k", "TV Samsung Crystal", "TV LG 55", "Monitor Gamer 144hz"],
        "Celulares": ["iPhone 14 Pro", "Samsung Galaxy S23", "Xiaomi Poco X6", "iPhone 13 128gb"],
        "Eletrodomesticos": ["Geladeira Frost Free", "Fogão Brastemp", "Máquina Lavar 12kg", "Ar Condicionado Inverter"],
        "Cozinha": ["Air Fryer Mondial Family", "Cafeteira Espresso", "Micro-ondas 30L", "Mixer Profissional"],
        "Tecnologia": ["Notebook Dell", "Playstation 5", "Caixa JBL Boombox", "Tablet Samsung S9"]
    },
    "Moda Feminina": {
        "Roupas": ["Vestido Festa", "Conjunto Alfaiataria", "Calça Jeans Levanta Bumbum", "Jaqueta Puffer"],
        "Calcados": ["Tênis Vert Feminino", "Bota Cano Curto", "Sandália Salto Taça"],
        "Acessorios": ["Bolsa Michael Kors Style", "Relógio Technos Feminino", "Kit Maquiagem Ruby Rose"]
    },
    "Moda Masculina": {
        "Roupas": ["Camisa Reserva", "Calça Sarja Masculina", "Jaqueta Masculina Couro", "Kit Cueca Calvin Klein"],
        "Calcados": ["Tênis Nike Shox", "Tênis Adidas Casual", "Bota Adventure Couro"],
        "Acessorios": ["Relógio Invicta", "Mochila Notebook Impermeável", "Perfume Sauvage Style"]
    },
    "Maternidade": {
        "Moveis": ["Carrinho Bebê Galzerano", "Berço Americano", "Cadeira Auto 0-36kg"],
        "Seguranca": ["Babá Eletrônica Motorola", "Câmera Wi-Fi 360"],
        "Utilidades": ["Extrator Leite Elétrico", "Kit Higiene Bebê", "Mochila Maternidade Premium"]
    },
    "Motocicleta": {
        "Capacetes": ["Capacete LS2 FF358", "Capacete Norisk Razor", "Capacete MT Helmets", "Capacete Bell"],
        "Pecas_Pesadas": ["Kit Relação DID Gold", "Pneu Pirelli Diablo", "Pneu Metzeler", "Amortecedor Cofap Moto"],
        "Performance": ["Escapamento Fortuna Tri", "Carburador Koso", "Vela Iridium NGK", "Filtro K&N Moto"],
        "Acessorios_Top": ["Intercomunicador Sena", "Baú Givi 45L", "Suporte Celular Garra", "Farol Auxiliar LED"]
    }
}

# Bloqueios para limpar o feed de itens chatos
PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "não compre", "dummy", "viseira", "adesivo", "película", 
    "capinha", "case", "filtro de papel", "brinde", "usado", "defeito"
]

# ==========================================
# GESTÃO DE MEMÓRIA PERSISTENTE
# ==========================================

def carregar_historico():
    if os.path.exists(HISTORICO_FILE):
        try:
            with open(HISTORICO_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_historico(historico):
    with open(HISTORICO_FILE, 'w') as f:
        json.dump(historico, f)

def limpar_historico_antigo():
    """Remove itens que foram enviados há mais de 10 dias."""
    historico = carregar_historico()
    agora = datetime.now()
    novo_historico = {}
    
    for link, data_str in historico.items():
        try:
            data_envio = datetime.fromisoformat(data_str)
            if agora - data_envio < timedelta(days=10):
                novo_historico[link] = data_str
        except:
            continue
            
    salvar_historico(novo_historico)
    return novo_historico

def eh_repetido_persistente(titulo, link, historico, lista_ciclo_atual):
    # 1. Verifica se está no histórico de 10 dias
    if link in historico:
        return True
    
    t_novo = normalizar_texto(titulo)
    
    # 2. Verifica similaridade com o que já foi escolhido NESTE ciclo
    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.45:
            return True
            
    return False

# ==========================================
# UTILITÁRIOS
# ==========================================

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 30) <= agora <= dt_time(21, 00)

def normalizar_texto(txt):
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt

# ==========================================
# LÓGICA DE MENSAGENS
# ==========================================

def gerar_copy_base(nome, preco, vendas, avaliacao, comissao, link, for_whatsapp=False):
    aberturas = [
        "🤯 Sério… olha esse achado!", "🚨 Isso aqui não aparece toda hora!", 
        "👀 Achei agora e vim correndo postar!", "🔥 OPORTUNIDADE QUENTE!",
        "💥 Esse aqui tá com um preço absurdo!", "🛑 PARA TUDO e olha esse desconto!",
        "⚠️ Alerta de estoque baixo!", "🚀 Esse aqui vai voar rápido!"
    ]
    
    gatilhos = [
        "Preço muito abaixo do mercado", "Avaliações excelentes dos compradores",
        "Campeão de vendas na categoria", "Custo-benefício imbatível",
        "Qualidade premium garantida", "O queridinho do momento"
    ]
    
    chamadas_acao = [
        "⚡ CLIQUE ANTES QUE O PREÇO SUBA!", "🔥 ESTOQUE LIMITADO - APROVEITE!",
        "🚀 COMPRE AGORA COM DESCONTO!", "🎯 GARANTA O SEU ANTES QUE ACABE!",
        "💰 ECONOMIA REAL SÓ HOJE!"
    ]

    abertura = random.choice(aberturas)
    gatilho = random.choice(gatilhos)
    chamada = random.choice(chamadas_acao)

    if for_whatsapp:
        return f"""{abertura}

*🔥 {nome}*

📌 {gatilho}

{chamada}

💰 *R$ {preco}*
⭐ *{avaliacao}* | 🛒 *{vendas} vendas*

⚠️ *Pode subir de preço a qualquer momento*

🛒 *COMPRAR AGORA:*
{link}

━━━━━━━━━━━━━━━
📢 *Quer mais ofertas assim?*
{LINK_GRUPO_OFERTAS}"""

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
    query_body = f'''
    query {{
        productOfferV2(sortType: 2, limit: 50, keyword: "{keyword}", isAMSOffer: true) {{
            nodes {{
                productName
                priceMin
                commissionRate
                sales
                ratingStar
                productLink
                offerLink
                imageUrl
            }}
        }}
    }}
    '''
    payload = json.dumps({"query": query_body})
    base_str = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base_str.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }

    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload, headers=headers, timeout=20)
        res = r.json()
        return res.get("data", {}).get("productOfferV2", {}).get("nodes", [])
    except Exception as e:
        logging.error(f"Erro na busca Shopee ({keyword}): {e}")
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
    historico = limpar_historico_antigo()
    ofertas_finais = []
    
    nichos = list(KEYWORDS_ESTRUTURADAS.keys())
    random.shuffle(nichos)
    
    for nicho in nichos:
        logging.info(f"Processando nicho: {nicho}")
        subs = list(KEYWORDS_ESTRUTURADAS[nicho].keys())
        subs_escolhidas = random.sample(subs, k=min(2, len(subs)))
        
        for sub in subs_escolhidas:
            kw = random.choice(KEYWORDS_ESTRUTURADAS[nicho][sub])
            produtos = buscar_shopee(kw)
            
            candidatos_sub = []
            for p in produtos:
                nome = p.get("productName", "")
                link = p.get("offerLink") or p.get("productLink")
                preco = float(p.get("priceMin", 0))
                vendas = int(p.get("sales", 0))
                rating = float(p.get("ratingStar", 0))
                comissao = float(p.get("commissionRate", 0))

                if not nome or not link: continue
                if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO): continue
                if preco < PRECO_MIN or preco > PRECO_MAX: continue
                if vendas < VENDAS_MIN: continue
                if rating < RATING_MIN: continue
                if comissao < COMISSAO_MIN: continue
                
                if eh_repetido_persistente(nome, link, historico, ofertas_finais): continue
                
                # Score de qualidade com foco em marcas e produtos quentes
                score = (vendas / 100) + (rating * 15) + (comissao * 100)
                palavras_premium = ["iphone", "brastemp", "lg", "samsung", "ls2", "pirelli", "did", "givi", "jbl", "ps5", "reserva"]
                if any(pp in nome.lower() for pp in palavras_premium):
                    score += 50
                
                p["score"] = score
                candidatos_sub.append(p)
            
            if candidatos_sub:
                candidatos_sub.sort(key=lambda x: x["score"], reverse=True)
                ofertas_finais.append(candidatos_sub[0])
                logging.info(f"Selecionado: {candidatos_sub[0]['productName']} (Sub: {sub})")
                
    return ofertas_finais

# ==========================================
# EXECUÇÃO DO BOT
# ==========================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    if not dentro_do_horario():
        logging.info("Fora do horário.")
        return

    logging.info("Iniciando ciclo V17...")
    ofertas = get_melhores_ofertas()
    
    if not ofertas:
        logging.warning("Sem ofertas qualificadas.")
        return

    await context.bot.send_message(
        chat_id=CHAT_ID_DESTINO,
        text="🚨 <b>OFERTAS SELECIONADAS DE HOJE!</b>\n<i>Produtos de alta qualidade e com o melhor preço.</i>",
        parse_mode="HTML"
    )
    await asyncio.sleep(3)

    historico = carregar_historico()
    
    for item in ofertas:
        try:
            nome = html.escape(item["productName"])
            link_original = item.get("offerLink") or item.get("productLink")
            link_afiliado = aplicar_afiliado(link_original)
            preco = f"{float(item['priceMin']):.2f}".replace(".", ",")
            vendas = f"{int(item['sales']):,}".replace(",", ".")
            rating = item.get("ratingStar", 5.0)
            comissao = round(float(item.get("commissionRate", 0)) * 100, 1)
            img = item.get("imageUrl")

            msg = gerar_copy_base(nome, preco, vendas, rating, comissao, link_afiliado)
            
            await context.bot.send_photo(
                chat_id=CHAT_ID_DESTINO,
                photo=img,
                caption=msg,
                parse_mode="HTML"
            )
            
            # Registrar no histórico persistente
            historico[link_original] = datetime.now().isoformat()
            salvar_historico(historico)
            
            await asyncio.sleep(45)
            
        except Exception as e:
            logging.error(f"Erro envio: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V17 Pronto!")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        print("ERRO: TELEGRAM_TOKEN ausente!")
    else:
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
        app.run_polling()


        


