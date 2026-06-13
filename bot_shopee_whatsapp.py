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
print("VERSAO SHOPEE V117 - ALL NICHOS INTELIGENTE + MOTO FIX + LOGS DE MOTO")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

HISTORICO_FILE = "historico_global_v116.json"
CHECK_INTERVAL = 5400
PRECO_MIN_BASE = 35.0
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
# MODELOS DE MOTO (AJUSTADO PARA A SHOPEE)
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
# A LISTA DE OURO DO MECÂNICO + TODOS OS NICHOS PRO
# ==========================================

KEYWORDS_POOL = {
    "Motos_Tecnico": [
        # Motor e Transmissão (Alto Giro)
        ["Kit Relação Vaz", "Kit Embreagem", "Kit Cilindro Moto", "Biela Moto", "Kit Pistão com Anéis", "Jogo de Juntas Moto"],
        ["Vela Iridium Moto", "Cabo de Vela Moto", "Cachimbo de Vela", "Carburador Moto", "Bomba Combustível Moto"],
        ["Corrente Comando Moto", "Esticador Corrente Comando", "Válvula Escape", "Válvula Admissão", "Guarnição Tampa Válvulas"],
        ["Motor de Partida Moto", "Escova de Arranque", "Placa de Partida Moto", "Engrenagem Placa Partida"],
        # Injeção e Elétrica
        ["Sensor TPS Moto", "Sensor Híbrido Moto", "Sensor Lenta Moto", "Sensor Borboleta", "Corpo de Injeção Moto"],
        ["CDI Moto", "Estator Moto", "Bobina de Pulso", "Bobina de Faísca", "Chicote Principal Moto", "Regulador de Voltagem"],
        ["Painel Completo Moto", "Relé de Pisca", "Pisca Completo Moto", "Bloco Óptico Moto"],
        # Chassis, Suspensão e Freios
        ["Kit Freio a Disco Moto", "Pastilha e Disco Freio", "Espelho de Freio", "Burrinho de Freio", "Pedal de Freio Moto"],
        ["Amortecedor Traseiro Moto", "Tubo Interno Moto", "Retentores Bengala", "Caixa de Direção Moto", "Bucha Balança Moto"],
        ["Mesa Superior Moto", "Mesa Inferior Moto", "Quadro Elástico Moto", "Eixo Moto", "Coxim Coroa Moto"],
        # Pneus (Medidas Exatas)
        ["Pneu 90/90-18 Moto", "Pneu 2.75-18 Moto", "Pneu 110/70-17 Moto", "Pneu 140/70-17 Moto", "Câmara de Ar Moto"],
        # Estética e Acessórios Profissionais
        ["Paralama Dianteiro Moto", "Paralama Traseiro Moto", "Aba Tanque Moto", "Tampa Lateral Moto", "Rabeta Moto"],
        ["Capa Banco Moto", "Guidão Moto", "Retrovisores Moto", "Manete Esportiva Moto", "Pedal de Marcha"],
        ["Capacete LS2", "Capacete Norisk", "Baú Moto", "Suporte Baú", "Luvas Moto", "Jaqueta Moto", "Bala Clava Moto"]
    ],
    "Tecnologia_e_Utilidades": [
        ["Fone Bluetooth JBL", "Fone Lenovo", "Smartwatch Iwo", "Alexa Echo Dot"],
        ["Carregador Turbo", "Power Bank Pineng", "Cabo Baseus", "Câmera Segurança"],
        ["Intercomunicador V6", "Roteador Wifi", "Mochila Motoboy Impermeável"]
    ],
    "Eletro_Desejo": [
        ["Air Fryer Mondial", "Fritadeira Philco", "Batedeira Arno", "Liquidificador Oster"],
        ["Ferro de Passar", "Vaporizador Roupas", "Ventilador Turbo", "Máquina de Café"]
    ],
    "Casa_e_Ferramentas": [
        ["Jogo de Chaves", "Furadeira Impacto", "Parafusadeira Vonder", "Serra Tico Tico"],
        ["Mochila Notebook", "Lâmpada Inteligente", "Refletor LED", "Tênis Olympikus"]
    ],
    "Bebe_Util": [
        ["Fralda Pampers", "Fralda Huggies", "Babá Eletrônica", "Monitor Bebê"],
        ["Carrinho Galzerano", "Cadeira Auto", "Patinete Infantil", "Kit Higiene Bebê"],
        ["Blocos de Montar", "Quebra Cabeça Madeira", "Lousa Mágica", "Barraca Infantil"]
    ],
    "Moda_Masculina": [
        ["Camiseta básica masculina", "Camiseta oversized masculina", "Camisa polo masculina", "Camisa social masculina", "Camisa de linho masculina", "Camisa xadrez masculina"],
        ["Jaqueta jeans masculina", "Jaqueta corta vento masculina", "Moletom masculino", "Blusa de frio masculina"],
        ["Calça jeans masculina", "Calça cargo masculina", "Calça jogger masculina", "Bermuda jeans masculina", "Bermuda moletom masculina"],
        ["Cueca boxer masculina", "Cueca sem costura masculina", "Meia esportiva masculina", "Meia social masculina"],
        ["Tênis casual masculino", "Tênis esportivo masculino", "Tênis corrida masculino", "Sapatênis masculino"],
        ["Chinelo slide masculino", "Chinelo havaiana masculino", "Bota masculina", "Sapato social masculino"],
        ["Carteira masculina", "Relógio masculino", "Óculos de sol masculino", "Boné masculino", "Cinto de couro masculino"],
        ["Pulseira masculina", "Mochila masculina", "Bolsa transversal masculina", "Corrente masculina", "Anel masculino"]
    ],
    "Moda_Feminina": [
        ["Vestido longo feminino", "Vestido midi feminino", "Vestido tubinho feminino", "Vestido floral feminino"],
        ["Cropped feminino", "Body feminino", "Conjunto feminino", "Macacão feminino"],
        ["Calça jeans feminina", "Calça flare feminina", "Calça pantalona feminina", "Legging feminina", "Shorts jeans feminino"],
        ["Saia midi feminina", "Saia plissada feminina", "Blazer feminino", "Jaqueta jeans feminina", "Moletom feminino"],
        ["Tênis feminino", "Sandália rasteira feminina", "Sandália salto feminino", "Tamanco feminino"],
        ["Chinelo feminino", "Bota feminina", "Sapatilha feminina"],
        ["Bolsa feminina", "Mochila feminina", "Óculos feminino", "Relógio feminino"],
        ["Kit brincos feminino", "Colar feminino", "Pulseiras femininas", "Presilhas de cabelo femininas", "Scrunchies femininos", "Necessaire feminina"],
        ["Escova secadora feminina", "Chapinha feminina", "Modelador de cachos feminino", "Kit maquiagem feminino"],
        ["Espelho LED feminino", "Organizador de maquiagem feminino"]
    ],
    "Maternidade_Pro": [
        ["Carrinho de bebê", "Bebê conforto", "Cadeirinha automotiva", "Berço portátil", "Cercadinho infantil"],
        ["Banheira de bebê", "Trocador portátil", "Bolsa maternidade", "Mochila maternidade"],
        ["Fralda descartável", "Fralda ecológica", "Babador infantil", "Chupeta infantil", "Mamadeira infantil"],
        ["Esterilizador de mamadeira", "Aquecedor de mamadeira"],
        ["Cadeira de alimentação infantil", "Prato infantil", "Copo antivazamento", "Talheres infantis", "Triturador de alimentos"],
        ["Tapete educativo infantil", "Piano infantil", "Chocalhos infantis", "Mordedores infantis", "Brinquedos Montessori", "Livros sensoriais"],
        ["Sutiã amamentação", "Almofada amamentação", "Extrator de leite elétrico", "Faixa pós-parto", "Cinta modeladora"]
    ],
    "Casa_EletroPro": [
        ["Air Fryer", "Liquidificador", "Batedeira", "Cafeteira", "Panela elétrica", "Grill elétrico", "Sanduicheira", "Mixer", "Processador de alimentos", "Espremedor de frutas"],
        ["Organizador de geladeira", "Organizador de gavetas", "Sapateira", "Organizador multiuso", "Cesto organizador", "Caixa organizadora"],
        ["Aspirador de pó", "Aspirador robô", "Mop giratório", "Lavadora portátil", "Vassoura mágica", "Escova elétrica limpeza"],
        ["Jogo de cama", "Edredom", "Cobertor", "Travesseiro", "Protetor de colchão", "Cortina blackout"],
        ["Organizador de banheiro", "Prateleira adesiva", "Toalhas de banho", "Tapete banheiro", "Kit acessórios banheiro"]
    ],
    "EletroEletronicos_Pro": [
        ["Smart TV", "Soundbar", "Caixa de som bluetooth", "Home Theater", "Projetor"],
        ["Notebook", "Mouse gamer", "Teclado gamer", "Webcam", "Monitor", "SSD", "HD externo", "Impressora"],
        ["Câmera Wi-Fi", "Fechadura digital", "Vídeo porteiro", "Campainha inteligente"],
        ["Fita LED", "Lâmpada inteligente", "Refletor solar", "Abajur LED"]
    ],
    "Uso_Pessoal": [
        ["Smartphone Samsung", "Smartphone Xiaomi", "Smartpoint Motorola", "iPhone", "Película celular", "Capinha celular", "Carregador turbo", "Cabo USB"],
        ["Fone Bluetooth", "Fone Gamer", "Headset gamer", "Caixa JBL", "Microfone"],
        ["Halteres", "Corda de pular", "Faixa elástica", "Colchonete", "Roda abdominal", "Smartwatch", "Garrafa térmica", "Balança digital"],
        ["Medidor pressão arterial", "Oxímetro", "Massageador", "Pistola massageadora", "Umidificador"],
        ["Livro desenvolvimento pessoal", "Livro finanças", "Livro negócios", "Livro marketing digital", "Livro relacionamentos", "Livro saúde mental", "Livro educação financeira"]
    ],
    "Games_Pro": [
        ["Playstation 5", "Playstation 4", "Xbox Series S", "Xbox Series X", "Nintendo Switch"],
        ["Controle sem fio", "Headset gamer", "Mouse gamer", "Teclado gamer", "Cadeira gamer", "Mesa gamer", "Volante gamer"]
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

PALAVRAS_BLOQUEIO_GERAL = [
    "teste", "amostra", "não compre", "dummy", "adesivo", "película", 
    "case", "filtro de papel", "brinde", "usado", "defeito", "capinha",
    "pano de prato", "mini processador", "ralador manual",
    "spray de pum", "pegadinha", "sal marinho", "esponja magica", "adesivo retalho",
    "bico desentupidor", "ventosa", "barra estabilizadora", "coxim", "cavalete lateral",
    "filtro refil", "tampa geladeira", "narigueira", "rede elastica", "fecho porta",
    "organizador gaveta", "caneca infantil", "suporte de baba"
] + PALAVRAS_BLOQUEIO_BIKE

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

def eh_repetido_master_fix(titulo, historico_global, lista_ciclo_atual):
    t_novo = normalizar_texto(titulo)
    
    # 1) BLOQUEIO POR ASSUNTO ENJOADO (24H)
    for assunto in ASSUNTOS_ENJOADOS:
        if assunto in t_novo:
            agora = datetime.now()
            for item in historico_global.values():
                t_antigo = normalizar_texto(item.get("titulo", ""))
                data_envio = datetime.fromisoformat(item.get("data", agora.isoformat()))
                if assunto in t_antigo and (agora - data_envio).total_seconds() < 24 * 3600:
                    return True

    # 2) BLOQUEIO POR RADICAL EXISTENTE
    for termo in BLOQUEIO_REPETICAO_CICLO + BLOQUEIO_RADICAL_24H:
        if termo in t_novo:
            for p_ja_escolhido in lista_ciclo_atual:
                if termo in normalizar_texto(p_ja_escolhido.get("productName", "")):
                    return True

    # 3) SIMILARIDADE NO CICLO
    for p_atual in lista_ciclo_atual:
        t_atual = normalizar_texto(p_atual.get("productName", ""))
        if SequenceMatcher(None, t_novo, t_atual).ratio() > 0.30:
            return True

    # 4) BLOQUEIO POR RADICAL EM HISTÓRICO (24H)
    agora = datetime.now()
    for radical in BLOQUEIO_RADICAL_24H:
        if radical in t_novo:
            for item in historico_global.values():
                data_envio = datetime.fromisoformat(item.get("data", agora.isoformat()))
                if radical in normalizar_texto(item.get("titulo", "")) and (agora - data_envio).total_seconds() < 86400:
                    return True

    # 5) HASH DO TÍTULO
    h = hashlib.md5(t_novo[:45].encode()).hexdigest()
    if h in historico_global: return True

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
# MODO DIAGNÓSTICO DE KEYWORDS
# ==========================================

def diagnostico_keyword(keyword, cat_name=None, limite=50):
    logging.info("==========================================")
    logging.info(f"[DIAGNÓSTICO] Keyword: '{keyword}' | Categoria lógica: {cat_name or 'N/A'}")
    logging.info("==========================================")

    produtos = buscar_shopee_god_mode(keyword)

    total = len(produtos)
    logging.info(f"[DIAGNÓSTICO] Total de produtos retornados pela API: {total}")

    if total == 0:
        logging.warning("[DIAGNÓSTICO] Nenhum produto retornado para esta keyword.")
        return

    # Limita para análise
    analisados = produtos[:limite]

    # Coletas básicas
    precos = []
    vendas_lista = []
    ratings_lista = []
    categorias_contagem = {}
    exemplos = []

    for p in analisados:
        nome = p.get("productName", "").strip()
        preco = float(p.get("priceMin", 0) or 0)
        vendas = int(p.get("sales", 0) or 0)
        rating = float(p.get("ratingStar", 0) or 0)

        precos.append(preco)
        vendas_lista.append(vendas)
        ratings_lista.append(rating)

        # Categoria não vem explícita na resposta da API de afiliados,
        # mas podemos tentar inferir por palavras do nome.
        categoria_inferida = "Indefinida"
        nome_lower = nome.lower()

        if any(x in nome_lower for x in ["moto", "capacete", "guidão", "pneu", "freio", "coroa", "kit relação"]):
            categoria_inferida = "Possível Moto"
        elif any(x in nome_lower for x in ["vestido", "calça", "camisa", "polo", "jeans", "blusa", "saia"]):
            categoria_inferida = "Possível Moda"
        elif any(x in nome_lower for x in ["cortina", "cobre leito", "lençol", "kit cama", "escova", "limpeza"]):
            categoria_inferida = "Possível Casa"
        elif any(x in nome_lower for x in ["carrinho de bebê", "canguru", "fralda", "mamadeira", "babá eletrônica"]):
            categoria_inferida = "Possível Maternidade/Bebê"
        elif any(x in nome_lower for x in ["smartphone", "celular", "video game", "console", "xbox", "playstation", "ps4", "ps5"]):
            categoria_inferida = "Possível Eletro/Eletrônicos"

        categorias_contagem[categoria_inferida] = categorias_contagem.get(categoria_inferida, 0) + 1

        exemplos.append({
            "nome": nome,
            "preco": preco,
            "vendas": vendas,
            "rating": rating,
            "categoria_inferida": categoria_inferida,
            "comissao": float(p.get("commissionRate", 0) or 0) * 100,
            "link": p.get("offerLink") or p.get("productLink")
        })

    # Estatísticas simples
    precos_ordenados = sorted(precos)
    vendas_ordenadas = sorted(vendas_lista)
    ratings_ordenadas = sorted(ratings_lista)

    def mediana(lista):
        if not lista:
            return 0
        n = len(lista)
        meio = n // 2
        if n % 2 == 1:
            return lista[meio]
        else:
            return (lista[meio - 1] + lista[meio]) / 2

    preco_min = precos_ordenados[0]
    preco_max = precos_ordenados[-1]
    preco_mediana = mediana(precos_ordenados)

    vendas_min = vendas_ordenadas[0]
    vendas_max = vendas_ordenadas[-1]
    vendas_mediana = mediana(vendas_ordenadas)

    rating_min = ratings_ordenadas[0]
    rating_max = ratings_ordenadas[-1]
    rating_mediana = mediana(ratings_ordenadas)

    logging.info(f"[DIAGNÓSTICO] Preço: min={preco_min:.2f} | mediana={preco_mediana:.2f} | max={preco_max:.2f}")
    logging.info(f"[DIAGNÓSTICO] Vendas: min={vendas_min} | mediana={vendas_mediana} | max={vendas_max}")
    logging.info(f"[DIAGNÓSTICO] Rating: min={rating_min:.2f} | mediana={rating_mediana:.2f} | max={rating_max:.2f}")

    # Distribuição por "categoria inferida"
    logging.info("[DIAGNÓSTICO] Distribuição por categoria inferida (pelo nome do produto):")
    for cat_inf, count in categorias_contagem.items():
        logging.info(f"    - {cat_inf}: {count} produtos")

    # Top 5 por vendas
    top_por_vendas = sorted(exemplos, key=lambda x: x["vendas"], reverse=True)[:5]
    logging.info("[DIAGNÓSTICO] Top 5 por vendas:")
    for idx, ex in enumerate(top_por_vendas, start=1):
        logging.info(
            f"    {idx}) {ex['nome']} | R$ {ex['preco']:.2f} | vendas={ex['vendas']} | rating={ex['rating']:.2f} | "
            f"comissão={ex['comissao']:.1f}% | cat_inf={ex['categoria_inferida']}"
        )

    # Top 5 por rating
    top_por_rating = sorted(exemplos, key=lambda x: x["rating"], reverse=True)[:5]
    logging.info("[DIAGNÓSTICO] Top 5 por rating:")
    for idx, ex in enumerate(top_por_rating, start=1):
        logging.info(
            f"    {idx}) {ex['nome']} | R$ {ex['preco']:.2f} | vendas={ex['vendas']} | rating={ex['rating']:.2f} | "
            f"comissão={ex['comissao']:.1f}% | cat_inf={ex['categoria_inferida']}"
        )

    logging.info("==========================================")
    logging.info(f"[DIAGNÓSTICO] FIM DA ANÁLISE DA KEYWORD: '{keyword}'")
    logging.info("==========================================")

# ==========================================
# LÓGICA DE SELEÇÃO DE OFERTAS (INTELIGENTE + MOTO + LOGS)
# ==========================================

def get_melhores_ofertas():
    historico_global = carregar_historico()
    ofertas_finais = []
    
    categorias_alvo = [
        "Motos_Tecnico",
        "Tecnologia_e_Utilidades",
        "Eletro_Desejo",
        "Casa_e_Ferramentas",
        "Bebe_Util",
        "Moda_Masculina",
        "Moda_Feminina",
        "Maternidade_Pro",
        "Casa_EletroPro",
        "EletroEletronicos_Pro",
        "Uso_Pessoal",
        "Games_Pro"
    ]
    
    logging.info("=== INÍCIO DO CICLO DE SELEÇÃO DE OFERTAS (V117) ===")
    
    for cat_name in categorias_alvo:
        vagas_preenchidas = 0
        # MOTO: 4 vagas por ciclo; outros: 1 vaga
        if cat_name == "Motos_Tecnico":
            vagas_limite = 4
        else:
            vagas_limite = 1
        
        sub_listas = KEYWORDS_POOL[cat_name].copy()
        random.shuffle(sub_listas)
        
        logging.info(f"Categoria: {cat_name} | vagas_limite={vagas_limite}")
        
        for idx_sub, sub_lista in enumerate(sub_listas):
            if vagas_preenchidas >= vagas_limite:
                break
            
            tentativas_sub = 0
            while tentativas_sub < 15 and vagas_preenchidas < vagas_limite:
                tentativas_sub += 1
                kw_base = random.choice(sub_lista)
                
                # Se for moto, cruza com um modelo aleatório
                kw = f"{kw_base} {random.choice(MODELOS_MOTO_BR)}" if cat_name == "Motos_Tecnico" else kw_base
                
                if cat_name == "Motos_Tecnico":
                    logging.info(f"  Sublista {idx_sub+1} | Tentativa {tentativas_sub} | Keyword moto: {kw}")
                else:
                    logging.info(f"  Sublista {idx_sub+1} | Tentativa {tentativas_sub} | Keyword: {kw}")
                
                produtos = buscar_shopee_god_mode(kw)
                
                if not produtos:
                    if cat_name == "Motos_Tecnico":
                        logging.warning(f"    -> API retornou 0 produtos para moto: {kw}")
                    continue
                
                if cat_name == "Motos_Tecnico":
                    logging.info(f"    -> API retornou {len(produtos)} produtos para moto: {kw}")
                
                top_produtos = produtos[:20]
                random.shuffle(top_produtos)
                
                passou_preco = 0
                passou_vendas = 0
                passou_rating = 0
                passou_bloqueio = 0
                passou_repetido = 0
                
                for p in top_produtos:
                    nome = p.get("productName", "")
                    preco = float(p.get("priceMin", 0))
                    vendas = int(p.get("sales", 0))
                    
                    # Bloqueio por palavra
                    if any(b in nome.lower() for b in PALAVRAS_BLOQUEIO_GERAL):
                        passed_bloqueio = True
                        passou_bloqueio += 1
                        continue
                    
                    # Preço mínimo
                    if preco < PRECO_MIN_BASE:
                        passou_preco += 1
                        continue
                    
                    # Teto de preço por categoria
                    if cat_name == "Motos_Tecnico" and preco > 850:
                        continue
                    if cat_name != "Motos_Tecnico" and any(m in nome.lower() for m in ["moto", "capacete", "pneu", "retrovisor"]):
                        continue
                    
                    # Mínimo de vendas
                    v_necessarias = 5 if preco > 300 else 35
                    if vendas < v_necessarias:
                        passou_vendas += 1
                        continue
                    
                    # Rating mínimo
                    if float(p.get("ratingStar", 0)) < RATING_MIN_BASE:
                        passou_rating += 1
                        continue
                    
                    # Repetidos
                    if eh_repetido_master_fix(nome, historico_global, ofertas_finais):
                        passou_repetido += 1
                        continue
                    
                    p["cat"] = cat_name
                    ofertas_finais.append(p)
                    vagas_preenchidas += 1
                    break
                
                if cat_name == "Motos_Tecnico" and tentativas_sub >= 1:
                    logging.info(f"    -> Passou preço: {passou_preco} | vendas: {passou_vendas} | rating: {passou_rating} | bloqueio: {passou_bloqueio} | repetido: {passou_repetido}")
    
    logging.info(f"=== FINAL: Ofertas seleccionadas = {len(ofertas_finais)} ===")
    
    return ofertas_finais[:10]

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    agora = datetime.now(FUSO_BR).time()
    if not (dt_time(5, 30) <= agora <= dt_time(21, 30)): return
    logging.info("Iniciando ciclo V117 All Nichos Inteligente...")
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
            h = hashlib.md5(t_norm[:45].encode()).hexdigest()
            historico_global[h] = {"data": datetime.now().isoformat(), "titulo": item["productName"]}
            salvar_historico(historico_global)
            await asyncio.sleep(60) 
        except Exception as e:
            logging.error(f"Erro no envio: {e}")

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    logging.info("Bot Shopee V117 All Nichos Inteligente Ativo!")

if __name__ == "__main__":
    # MODO DIAGNÓSTICO – RODAR UMA VEZ
    logging.info("Iniciando MODO DIAGNÓSTICO de keywords...")

    diagnostico_keyword("kit relação titan 160", cat_name="Moto")
    diagnostico_keyword("burrinho de freio honda biz 125", cat_name="Moto")

    diagnostico_keyword("vestido lovito", cat_name="Moda")
    diagnostico_keyword("camisa polo masculina", cat_name="Moda")

    diagnostico_keyword("escova limpeza pesada", cat_name="Casa")
    diagnostico_keyword("kit cobre leito", cat_name="Casa")

    diagnostico_keyword("carrinho de bebê", cat_name="Maternidade")
    diagnostico_keyword("canguru bebê passeio", cat_name="Maternidade")

    diagnostico_keyword("smartphone", cat_name="EletroEletrônicos")
    diagnostico_keyword("video game", cat_name="EletroEletrônicos")

    logging.info("MODO DIAGNÓSTICO finalizado. Veja os detalhes no log da Railway.")
















        


