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
print("VERSAO SHOPEE V21 - DIVERSIDADE E ANTI-REPETIÇÃO")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

# Arquivos de memória
HISTORICO_FILE = "historico_envios_v21.json"
COOLDOWN_FILE = "cooldown_categorias.json"

# Intervalo entre ciclos (em segundos)
CHECK_INTERVAL = 5400

# Filtros de Qualidade
PRECO_MIN = 25.0 
PRECO_MAX = 15000.0
COMISSAO_MIN = 0.05
VENDAS_MIN = 50
RATING_MIN = 4.5

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

# ==========================================
# NICHOS E SUBCATEGORIAS EXPANDIDAS (RESOLVENDO REPETIÇÃO)
# ==========================================

KEYWORDS_ESTRUTURADAS = {
    "Casa e Eletro": {
        "TV_Acessórios": ["Suporte TV Articulado", "Painel TV", "Luz LED TV"], # Removido controle remoto por reclamação
        "Eletrodomesticos": ["Geladeira Frost Free", "Fogão 4 bocas", "Máquina Lavar 12kg", "Ar Condicionado Split", "Micro-ondas Inox"],
        "Cozinha_Premium": ["Air Fryer Mondial", "Cafeteira Dolce Gusto", "Liquidificador potente", "Batedeira Planetária", "Jogo Panelas Cerâmica"],
        "Tecnologia": ["Notebook i5", "Playstation 5", "Caixa Som JBL", "Tablet Samsung", "Monitor 144hz"]
    },
    "Moda Feminina": {
        "Roupas": ["Vestido Midi", "Conjunto Alfaiataria", "Calça Wide Leg", "Blazer Feminino", "Macacão Elegante"],
        "Calcados": ["Tênis Casual Feminino", "Bota Cano Curto", "Sandália Salto Bloco", "Scarpin"],
        "Acessorios": ["Bolsa Transversal", "Relógio Digital Feminino", "Kit Maquiagem Profissional", "Óculos de Sol"]
    },
    "Moda Masculina": {
        "Roupas": ["Camisa Polo Algodão", "Calça Sarja", "Jaqueta Corta Vento", "Bermuda Cargo"],
        "Calcados": ["Tênis Esportivo Masculino", "Sapato Social Couro", "Bota Adventure", "Sapatênis"],
        "Acessorios": ["Relógio Analógico", "Mochila Notebook", "Perfume Importado Masculino", "Carteira Couro"]
    },
    "Maternidade_e_Bebe": {
        "Puericultura": ["Carrinho Bebê Reclinável", "Cadeira Auto 0-36kg", "Banheira Bebê", "Andador Infantil"],
        "Higiene_Saude": ["Kit Higiene Bebê", "Termômetro Infantil", "Aspirador Nasal", "Umidificador de Ar"],
        "Enxoval_Essencial": ["Jogo de Lençol Berço", "Toalha com Capuz", "Kit Body Bebê", "Saída de Maternidade"],
        "Brinquedos_Educativos": ["Tapete Atividades", "Móbile Musical", "Brinquedo Pedagógico"]
    },
    "Motocicleta_Especialista": {
        "Equipamento_Piloto": ["Capacete LS2 Rapid", "Jaqueta Motoqueiro Proteção", "Luva Couro Moto", "Bota Motociclista"],
        "Manutencao_Performance": ["Kit Relação DID", "Pneu Pirelli Moto", "Amortecedor Cofap", "Pastilha Freio EBC", "Vela Iridium NGK"],
        "Estilo_Cuidado": ["Capa de Moto Impermeável", "Cera Cristalizadora", "Kit Limpeza Corrente"],
        "Acessorios_Viagem": ["Baú Givi", "Suporte Celular Alumínio", "Intercomunicador Bluetooth", "Bolsa de Tanque"]
    }
}

PALAVRAS_BLOQUEIO = [
    "teste", "amostra", "não compre", "dummy", "adesivo", "película", 
    "case", "filtro de papel", "brinde", "usado", "defeito", "capinha",
    "controle remoto", "controle tv" # Bloqueio explícito conforme pedido
]

# ==========================================
# GESTÃO DE MEMÓRIA E COOLDOWN
# ==========================================

def normalizar_texto(txt):
    if not txt: return ""
    txt = txt.lower().strip()
    # Remove caracteres especiais e espaços duplos
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
            # Se postou essa subcategoria nas últimas 6 horas, evita
            if datetime.now() - ultima_vez < timedelta(hours=6):
                return True
        except:
            pass
    return False

def eh_repetido_absoluto(titulo, link, historico, lista_ciclo_atual):
    h = gerar_hash_produto(titulo)
    if h in historico:
        return True
    
    t_novo = normalizar_texto(titulo)
    for key, info in historico.items():
        t_hist = normalizar_texto(info.get("titulo", ""))
        if SequenceMatcher(None, t_novo, t_hist).ratio() > 0.75: # Mais rigoroso
            return True

    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.50:
            return True
            
    return False

# ==========================================
# LÓGICA DE MENSAGENS (COPIES DINÂMICAS)
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
# INTEGRAÇÃO SHOPEE E SELEÇÃO INTELIGENTE
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
    
    # Sorteia nichos para garantir que todos apareçam
    nichos = list(KEYWORDS_ESTRUTURADAS.keys())
    random.shuffle(nichos)
    
    for nicho in nichos:
        subs = list(KEYWORDS_ESTRUTURADAS[nicho].keys())
        random.shuffle(subs)
        
        for sub in subs:
            # Pula se já postou algo desse tipo recentemente
            if esta_em_cooldown(sub):
                continue
                
            kw = random.choice(KEYWORDS_ESTRUTURADAS[nicho][sub])
            produtos = buscar_shopee(kw)
            if not produtos: continue
            
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
                
                if eh_repetido_absoluto(nome, link, historico, ofertas_finais): continue
                
                # Sistema de Score com Bônus para Marcas de Confiança
                score = (vendas / 100) + (rating * 20) + (comissao * 150)
                marcas_premium = ["iphone", "brastemp", "lg", "samsung", "ls2", "pirelli", "did", "jbl", "ps5", "mondial", "givi", "ngk", "cofap"]
                if any(mp in nome.lower() for mp in marcas_premium):
                    score += 100
                
                p["score"] = score
                p["subcategoria"] = sub
                candidatos_sub.append(p)
            
            if candidatos_sub:
                candidatos_sub.sort(key=lambda x: x["score"], reverse=True)
                ofertas_finais.append(candidatos_sub[0])
                # Limita a 1 produto por nicho principal por ciclo para máxima variedade
                break 

    return ofertas_finais[:10] # Garante no máximo 10 ofertas variadas

# ==========================================
# EXECUÇÃO DO BOT
# ==========================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(FUSO_BR).time()
    # Horário de funcionamento: 06:00 às 22:30
    if not (dt_time(6, 0) <= agora <= dt_time(22, 30)): return

    logging.info("Iniciando ciclo V21 Diversificado...")
    ofertas = get_melhores_ofertas()
    if not ofertas: return

    await context.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 <b>OFERTAS SELECIONADAS DE HOJE!</b>\n<i>Produtos de alta qualidade e com o melhor preço.</i>", parse_mode="HTML")
    await asyncio.sleep(3)

    historico = carregar_json(HISTORICO_FILE)
    for item in ofertas:
        try:
            nome = html.escape(item["productName"])
            link_afiliado = aplicar_afiliado(item.get("offerLink") or item.get("productLink"))
            preco = f"{float(item['priceMin']):.2f}".replace(".", ",")
            vendas = f"{int(item['sales']):,}".replace(",", ".")
            msg = gerar_copy_base(nome, preco, vendas, item.get("ratingStar", 5.0), round(float(item.get("commissionRate", 0)) * 100, 1), link_afiliado)
            
            await context.bot.send_photo(chat_id=CHAT_ID_DESTINO, photo=item.get("imageUrl"), caption=msg, parse_mode="HTML")
            
            # Registro de Memória e Cooldown
            h = gerar_hash_produto(item["productName"])
            historico[h] = {"data": datetime.now().isoformat(), "titulo": item["productName"]}
            registrar_cooldown(item["subcategoria"])
            
            salvar_json(historico, HISTORICO_FILE)
            await asyncio.sleep(60) # Intervalo maior para não cansar o usuário
        except Exception as e:
            logging.error(f"Erro no envio: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V21 Ativo e Diversificado!")

if __name__ == "__main__":
    if TELEGRAM_TOKEN:
        ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build().run_polling()
    else:
        print("Erro: TELEGRAM_TOKEN não configurado.")






        


