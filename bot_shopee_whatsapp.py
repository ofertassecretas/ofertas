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
print("VERSAO SHOPEE V31 - PRIORIDADE MOTOS (2 POR CICLO)")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Arquivos de memória
HISTORICO_FILE = "historico_envios_v31.json"
COOLDOWN_FILE = "cooldown_categorias.json"

# Intervalo entre ciclos (em segundos)
CHECK_INTERVAL = 5400

# Filtros de Qualidade
PRECO_MIN = 15.0 
PRECO_MAX = 25000.0
VENDAS_MIN = 80   # Levemente ajustado para garantir volume em motos
RATING_MIN = 4.5   # Levemente ajustado para garantir volume em motos

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# NICHOS E BUSCA (COM FOCO EM MOTOS)
# ==========================================

KEYWORDS_ESTRUTURADAS = {
    "Casa e Tech": {
        "Organizadores": ["Organizador de Gaveta", "Caixa Organizadora", "Suporte de Pratos", "Prateleira Adesiva"],
        "Cozinha": ["Processador Manual", "Tapete de Cozinha", "Cortador de Legumes", "Pote Hermético Vidro"],
        "Smart_Home": ["Lâmpada Inteligente Alexa", "Tomada Wi-Fi", "Controle Universal Infravermelho"],
        "Acessorios_Celular": ["Cabo iPhone Turbo", "Carregador 20W", "Fone Bluetooth Original", "Suporte Veicular"]
    },
    "Beleza e Maternidade": {
        "Skincare": ["Massageador Facial", "Kit Skincare", "Sérum Vitamina C", "Protetor Solar Coreano"],
        "Cabelo": ["Escova Secadora", "Modelador de Cachos", "Óleo de Argan", "Touca de Cetim"],
        "Bebê_Utilidades": ["Copo de Treinamento", "Prato com Ventosa", "Kit Colher Silicone", "Babador Impermeável"],
        "Bebê_Seguranca": ["Trava de Gaveta", "Protetor de Quina", "Babá Eletrônica Visão Noturna"]
    },
    "Motos_Especial": { # NICHO PRIORITÁRIO
        "Equipamento": ["Capa de Chuva Motoqueiro", "Bota Impermeável Moto", "Luva de Proteção", "Balaclava", "Capacete LS2", "Jaqueta Moto"],
        "Manutencao": ["Lubrificante Corrente", "Kit Reparo Pneu", "Cera para Moto", "Escova Limpeza Corrente", "Kit Relação", "Pneu Moto"],
        "Gadgets": ["Intercomunicador V6", "Suporte Celular Antivibração", "Carregador USB Moto", "Baú Moto", "Alarme Moto"]
    }
}

PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "não compre", "dummy", "adesivo", "película", 
    "case", "filtro de papel", "brinde", "usado", "defeito", "capinha",
    "controle remoto", "controle tv"
]

# ==========================================
# GESTÃO DE MEMÓRIA E REDUNDÂNCIA
# ==========================================

def normalizar_texto(txt):
    if not txt: return ""
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ]", "", txt) 
    return txt

def gerar_hash_produto(titulo):
    texto_limpo = normalizar_texto(titulo)
    return hashlib.md5(texto_limpo.encode()).hexdigest()

def carregar_json(filename):
    if os.path.exists(filename):
        try:
            with open(filename, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def salvar_json(data, filename):
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Erro ao salvar {filename}: {e}")

def registrar_cooldown(categoria):
    cooldowns = carregar_json(COOLDOWN_FILE)
    cooldowns[categoria] = datetime.now().isoformat()
    salvar_json(cooldowns, COOLDOWN_FILE)

def esta_em_cooldown(categoria):
    cooldowns = carregar_json(COOLDOWN_FILE)
    if categoria in cooldowns:
        try:
            ultima_vez = datetime.fromisoformat(cooldowns[categoria])
            if datetime.now() - ultima_vez < timedelta(hours=3): # Reduzido para 3h para facilitar busca
                return True
        except:
            pass
    return False

def eh_repetido_ciclo_ou_hist(titulo, historico, lista_ciclo_atual):
    h = gerar_hash_produto(titulo)
    if h in historico: return True
    
    t_novo = normalizar_texto(titulo)
    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.40:
            return True
            
    termos_unicos = ["conjunto", "monitor", "bota", "tenis", "capacete", "geladeira", "mochila", "vestido", "relogio", "kit", "bolsa"]
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
        return f"{abertura}\n\n*🔥 {nome}*\n\n📌 {gatilho}\n\n{chamada}\n\n💰 *R$ {preco}*\n⭐ *{avaliacao}* | 🛒 *{vendas} vendas*\n\n⚠️ *Pode subir de preço*\n\n🛒 *COMPRAR:* {link}"

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
    historico = carregar_json(HISTORICO_FILE)
    ofertas_finais = []
    
    # --- FASE 1: GARANTIR 2 PRODUTOS DE MOTOS ---
    subs_moto = list(KEYWORDS_ESTRUTURADAS["Motos_Especial"].keys())
    random.shuffle(subs_moto)
    
    for sub in subs_moto:
        if len(ofertas_finais) >= 2: break
        kw = random.choice(KEYWORDS_ESTRUTURADAS["Motos_Especial"][sub])
        produtos = buscar_shopee(kw)
        if not produtos: continue
        
        candidatos = []
        for p in produtos:
            nome = p.get("productName", "")
            if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO): continue
            if int(p.get("sales", 0)) < 30: continue # Filtro relaxado para motos para garantir volume
            if eh_repetido_ciclo_ou_hist(nome, historico, ofertas_finais): continue
            
            p["score"] = (int(p.get("sales", 0)) / 10) + (float(p.get("ratingStar", 0)) * 50)
            p["subcategoria"] = sub
            candidatos.append(p)
        
        if candidatos:
            candidatos.sort(key=lambda x: x["score"], reverse=True)
            ofertas_finais.append(candidatos[0])

    # --- FASE 2: COMPLETAR COM OUTROS NICHOS ---
    outros_nichos = ["Casa e Tech", "Beleza e Maternidade"]
    todas_outras_subs = []
    for n in outros_nichos:
        for s in KEYWORDS_ESTRUTURADAS[n].keys():
            todas_outras_subs.append((n, s))
    
    random.shuffle(todas_outras_subs)
    
    for nicho, sub in todas_outras_subs:
        if len(ofertas_finais) >= 10: break
        if esta_em_cooldown(sub): continue
            
        kw = random.choice(KEYWORDS_ESTRUTURADAS[nicho][sub])
        produtos = buscar_shopee(kw)
        if not produtos: continue
        
        candidatos = []
        for p in produtos:
            nome = p.get("productName", "")
            if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO): continue
            if int(p.get("sales", 0)) < VENDAS_MIN: continue
            if eh_repetido_ciclo_ou_hist(nome, historico, ofertas_finais): continue
            
            p["score"] = (int(p.get("sales", 0)) / 20) + (float(p.get("ratingStar", 0)) * 50)
            p["subcategoria"] = sub
            candidatos.append(p)
            
        if candidatos:
            candidatos.sort(key=lambda x: x["score"], reverse=True)
            ofertas_finais.append(candidatos[0])

    return ofertas_finais[:10]

# ==========================================
# EXECUÇÃO DO BOT
# ==========================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(FUSO_BR).time()
    if not (dt_time(6, 0) <= agora <= dt_time(22, 30)): return

    logging.info("Iniciando ciclo V31 com Prioridade Motos...")
    ofertas = get_melhores_ofertas()
    
    if not ofertas:
        logging.warning("Nenhuma oferta encontrada.")
        return

    await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 <b>OFERTAS SELECIONADAS DE HOJE!</b>\n<i>Produtos de alta qualidade e com o melhor preço.</i>", parse_mode="HTML")
    await asyncio.sleep(3)

    historico = carregar_json(HISTORICO_FILE)
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
            historico[h] = {"data": datetime.now().isoformat(), "titulo": item["productName"]}
            registrar_cooldown(item.get("subcategoria", "Geral"))
            
            salvar_json(historico, HISTORICO_FILE)
            await asyncio.sleep(60) 
        except Exception as e:
            logging.error(f"Erro no envio: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V31 Ativo!")

if __name__ == "__main__":
    if TELEGRAM_TOKEN:
        ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build().run_polling()
    else:
        print("Erro: TELEGRAM_TOKEN não configurado.")








        


