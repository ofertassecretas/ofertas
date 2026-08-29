import asyncio, requests, logging, random, hashlib, time, json, os, html, re, tempfile
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder

print("VERSAO V30-SEM-REPETICAO")
# =========================
# CONFIG
# =========================
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "").strip()
CHAT_ID_DESTINO = -1003848415150
FREE_CHAT_ID = -1003886228244
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400
MAX_OFERTAS = 10
MIN_OFERTAS = 4
HISTORICO_DIAS = 30
HISTORICO_PROLONGADO = True
SIMILARIDADE_MAX = .88
SIMILARIDADE_FORTE = .94
VENDAS_MIN = 2
AVALIACAO_MIN = 4.0
PRECO_MIN = 15
PRECO_MAX = 10000
COMISSAO_MIN = .03
VERSAO_RODIZIO = 10
LIMITE_POR_FAMILIA = 1
MAX_PAGINA_BUSCA = 4
TIPOS_ORDEM = [1, 2, 3, 4, 5]

FUSO_BR = ZoneInfo("America/Sao_Paulo")
ARQUIVO_ESTADO = "estado_buscas.json"
ARQUIVO_HISTORICO = "historico_envios.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

ULTIMOS_LINKS = []
ULTIMOS_TITULOS = []
ABERTURAS_USADAS = set()
GATILHOS_USADOS = set()
LINKS_CICLO_ATUAL = set()
BASES_VISTAS = set()
TERMOS_USADOS_CICLO = set()
CONTADOR_REJEICOES = Counter()

# =========================
# FUNÇÕES BÁSICAS
# =========================
def normalizar(texto):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9à-ÿ\s]", " ", str(texto or "").lower().strip()))

def horario_valido():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 30) <= agora <= dt_time(21, 30)

def variar_termo(termo):
    base = termo.strip()
    variacoes = [
        base,
        f"{base} promocao",
        f"{base} oferta",
        f"{base} novo",
        f"{base} original",
        f"{base} barato",
        f"{base} premium",
        f"{base} 2025",
    ]
    return random.choice(variacoes)

GRUPO_SINONIMOS = {
    "smartwatch": {"smartwatch", "relogio inteligente"},
    "airfryer": {"air fryer", "airfryer", "fritadeira eletrica"},
    "fone": {"fone bluetooth", "fones de ouvido", "headset"},
    "caixa_som": {"caixa de som", "speaker", "soundbar"},
    "tv": {"smart tv", "televisao", "tv"},
    "notebook": {"notebook", "laptop"},
    "tablet": {"tablet", "ipad"},
    "celular": {"celular", "smartphone", "iphone"}
}

MAPA_SINONIMOS = {normalizar(t): g for g, ts in GRUPO_SINONIMOS.items() for t in ts}

def termo_ja_usado(termo):
    grupo = MAPA_SINONIMOS.get(normalizar(termo))
    return bool(grupo and any(MAPA_SINONIMOS.get(normalizar(t)) == grupo for t in TERMOS_USADOS_CICLO))

# =========================
# LISTAS DE PRODUTOS
# =========================
MOTOS = ["titan 150", "cb 300", "factor 150", "titan 160", "tornado 250", "fazer 150", "titan 125", "bros 160", "twister 250", "biz 125", "pop 110", "xre 300", "crosser 150", "xre 190", "fazer 250", "lander 250", "bros 150", "tenere 250", "biz 100", "twister 300"]
PECAS_MOTO = [
    "kit relacao", "kit embreagem", "bateria", "refil bomba combustivel",
    "chicote fiação principal", "bucha balança", "burrinho de freio",
    "estribo", "pedal de marcha", "pedal de freio", "rolamento virabrequim",
    "estator", "chave ignição", "punho chave luz", "kit pisca seta",
    "par pneu", "bloco óptico", "retentor de bengala", "bucha amortecedor",
    "carburador corpo de injeção", "kit cilindro", "jogo de juntas", "biela",
    "válvulas escape admissão", "kit freio a disco", "disco de freio",
    "tubo interno", "vela iridium", "pastilha freio", "guidao", "manopla",
    "amortecedor", "retrovisor", "farol", "lona de freio", "cabo embreagem",
    "cabo acelerador", "coroa moto", "pinhao moto", "corrente moto",
    "pedaleira", "carenagem", "lanterna traseira", "capacete"
]

PRODUTOS_POR_NICHO = {
    "Casa": ["air fryer", "aspirador", "liquidificador", "cafeteira", "panela eletrica", "panela de pressão", "capa para colchão", "jogo de pratos", "jogo de copos", "copo stanley", "talher", "panos de prato", "toalhas de banho", "coberta manta", "lençol", "mangueira de jardim", "tapete", "torneira de cozinha", "filtro de barro", "guarda roupas casal", "cama casal", "forma de silicone", "sapateira", "umidificador", "ar condicionado", "jogo de panelas", "cortinas", "tinta spray", "frigideiras", "rede de dormir", "pipoqueira", "mop", "ventilador", "batedeira", "escorredor de louça", "caixa organizadora", "papel de parede", "luminária"],
    "Maternidade": ["carrinho bebe", "berço bebe", "fralda descartavel", "fralda de pano", "naninha", "sapatinho", "kit toalha umedecida", "banheira", "kit bolsa maternidade", "canguru", "kit mamadeira", "babá eletronica", "ninho bebe", "kit enxoval bebe", "babador bebe", "mordedor bebe", "tapete infantil", "cadeirinha bebe", "almofada amamentação", "termometro infantil"],
    "Eletrônicos": ["smartwatch", "fone bluetooth", "caixa de som bluetooth", "bastão pau de selfie", "celular", "smart tv", "videogame", "capinha celular", "pelicula celular", "balança digital", "aparelho medidor de pressão", "webcam", "pen drive", "impressora termica", "computador", "notebook", "drone", "camera de segurança", "tablet", "ssd", "mouse gamer", "teclado mecanico", "power bank", "carregador turbo", "suporte celular carro"],
    "Moda Feminina": ["vestido feminino", "conjunto feminino", "kit calcinhas", "biquines", "saída de praia", "maquiagens", "roupa academia", "calça jeans", "calça legging", "saia longa", "sandalias", "pijamas", "blusa regata", "kit sutiã", "bermuda modeladora", "óculos de sol", "calça social", "vestido midi", "jaqueta feminina", "casaco feminino", "conjunto alfaiataria", "short feminino", "tenis feminino", "bolsa feminina", "blazer", "saia jeans", "top", "body"],
    "Moda Masculina": ["camiseta masculina", "bermuda jeans", "camiseta gola polo", "camisa de botão", "terno", "blazer", "kit meias", "barbeador", "meias esportivas", "óculos de sol", "bermuda", "tenis masculino", "chuteiras", "camisa térmica", "jaqueta masculina", "carteira", "kit cuecas", "calça jeans", "camisa social", "moletom", "sapato social"]
}

FAMILIAS_PRODUTOS = {
    "air_fryer": ["air fryer", "airfryer", "fritadeira"],
    "fone_bluetooth": ["fone bluetooth", "fones de ouvido", "headset"],
    "smartwatch": ["smartwatch", "relogio inteligente"],
    "caixa_som": ["caixa de som", "speaker"],
    "tv": ["smart tv", "televisao", "tv"],
    "notebook": ["notebook", "laptop"],
    "tablet": ["tablet", "ipad"],
    "celular": ["celular", "smartphone", "iphone"],
    "bebe": ["bebe", "fralda", "carrinho", "berço", "mamadeira", "ninho"],
    "moda_fem": ["vestido", "conjunto", "saia", "bolsa", "sandalia", "tenis feminino", "body"],
    "moda_masc": ["camisa", "camiseta", "calça", "tenis masculino", "jaqueta", "bermuda"],
    "casa": ["tapete", "lençol", "cortina", "organizadora", "luminária"],
    "moto": ["capacete", "vela", "pastilha", "lona", "corrente", "coroa", "pinhao", "guidao", "retrovisor", "farol"]
}

ROTACAO_NICHO_GRATIS = ["Moto", "Casa", "Moda Feminina", "Moda Masculina", "Maternidade", "Eletrônicos"]

# =========================
# ARQUIVOS DE ESTADO
# =========================
def salvar_json(caminho, dados):
    try:
        pasta = os.path.dirname(os.path.abspath(caminho)) or "."
        fd, temp = tempfile.mkstemp(dir=pasta)
        with os.fdopen(fd, "w", encoding="utf-8") as arq:
            json.dump(dados, arq, ensure_ascii=False, indent=2)
        os.replace(temp, caminho)
    except Exception as e:
        logging.error("Erro ao salvar %s: %s", caminho, e)

def carregar_json(caminho, padrao):
    try:
        if not os.path.exists(caminho):
            return padrao
        with open(caminho, "r", encoding="utf-8") as arq:
            return json.load(arq)
    except Exception as e:
        logging.error("Erro ao ler %s: %s", caminho, e)
        return padrao

def carregar_estado():
    estado = carregar_json(ARQUIVO_ESTADO, {})
    if estado.get("versao_rodizio") != VERSAO_RODIZIO:
        hoje = datetime.now(FUSO_BR).strftime("%Y%m%d")
        estado = {
            "versao_rodizio": VERSAO_RODIZIO,
            "Moto": {"data": hoje, "indice": 0}
        }
        for nicho, itens in PRODUTOS_POR_NICHO.items():
            estado[nicho] = {"indice": 0, "data": hoje}
    estado.setdefault("Moto", {"data": "", "indice": 0})
    estado["Moto"].setdefault("indice", 0)
    estado["Moto"].setdefault("data", "")
    for nicho in PRODUTOS_POR_NICHO:
        estado.setdefault(nicho, {"indice": 0, "data": ""})
        estado[nicho].setdefault("indice", 0)
        estado[nicho].setdefault("data", "")
    estado.setdefault("indice_nicho_gratis", 0)
    return estado

def salvar_estado(estado):
    salvar_json(ARQUIVO_ESTADO, estado)

def carregar_historico():
    return carregar_json(ARQUIVO_HISTORICO, {})

def salvar_historico(dados):
    salvar_json(ARQUIVO_HISTORICO, dados)

# =========================
# ROTAÇÃO MOTO
# =========================
def proxima_busca_moto(estado):
    indice = estado["Moto"]["indice"]
    peca = PECAS_MOTO[indice % len(PECAS_MOTO)]
    moto = MOTOS[indice % len(MOTOS)]
    estado["Moto"]["indice"] = (indice + 1) % (len(PECAS_MOTO) * len(MOTOS))
    logging.info("🏍️ Peça: [%s] | Moto: [%s]", peca, moto)
    return peca, moto, estado

# =========================
# ROTAÇÃO DEMAIS PRODUTOS
# =========================
def proximo_termo(nicho, estado):
    itens = PRODUTOS_POR_NICHO[nicho]
    controle = estado[nicho]
    for _ in range(len(itens)):
        termo = itens[controle["indice"] % len(itens)]
        controle["indice"] += 1
        if termo_ja_usado(termo):
            logging.info("🛑 Pulado (sinônimo): %s", termo)
            continue
        TERMOS_USADOS_CICLO.add(termo)
        return termo, estado
    return itens[controle["indice"] % len(itens)], estado

# =========================
# FILTROS E PONTUAÇÃO
# =========================
def chave_titulo(titulo):
    ignorar = {"premium", "novo", "promocao", "promoção", "super", "original", "profissional", "casual", "masculino", "feminino", "infantil", "adulto", "unissex", "kit", "com", "de", "para", "o", "a", "promo", "oferta", "modelo", "versao", "versão", "linha", "envio", "usado", "branco", "preto", "azul", "vermelho", "rosa", "verde", "amarelo", "tamanho", "gamer", "led", "usb"}
    palavras = [p for p in normalizar(titulo).split() if p not in ignorar and len(p) > 2]
    return " ".join(sorted(palavras)[:8])

def tem_bloqueio(texto):
    texto = normalizar(texto)
    palavras_proibidas = ["teste", "amostra", "não compre", "nao compre", "produto teste", "exemplo", "dummy", "vela led", "vela decorativa", "decorativa", "decoração", "casamento", "festa"]
    return any(p in texto for p in palavras_proibidas)

def duplicata_forte(titulo):
    normal = normalizar(titulo)
    chave = chave_titulo(titulo)
    for t in ULTIMOS_TITULOS:
        n = normalizar(t)
        c = chave_titulo(t)
        if normal == n or SequenceMatcher(None, normal, n).ratio() >= SIMILARIDADE_MAX or (chave and chave == c):
            return True
    return False

def produto_parecido(titulo, lista):
    alvo = normalizar(titulo)
    chave_alvo = chave_titulo(titulo)
    for t in lista:
        atual = normalizar(t)
        chave_atual = chave_titulo(t)
        if SequenceMatcher(None, alvo, atual).ratio() >= .84 or (chave_alvo and chave_alvo == chave_atual):
            return True
    return False

def pontuar_loja(tipos):
    try:
        return 3 if 1 in tipos else 2 if 4 in tipos else 1 if 2 in tipos else 0
    except:
        return 0

def pontuar_produto(produto, termo=""):
    try:
        vendas = int(produto.get("sales", 0) or 0)
        nota = float(produto.get("ratingStar", 0) or 0)
        comissao = float(produto.get("commissionRate", 0) or 0)
        preco = float(produto.get("priceMin", 0) or 0)
        titulo = normalizar(produto.get("productName", ""))
        termo_norm = normalizar(termo)
        pontuacao = min(vendas / 8, 25) + nota * 2 + comissao * 100 + pontuar_loja(produto.get("shopType", []))
        if 50 <= preco <= 5000:
            pontuacao += 6
        if termo_norm:
            pontuacao += 8 if termo_norm in titulo else sum(2 for p in termo_norm.split() if p in titulo)
        return pontuacao
    except:
        return 0

def avaliar_rejeicao(produto):
    titulo = str(produto.get("productName", "")).strip()
    link = str(produto.get("offerLink") or produto.get("productLink") or "").strip()
    preco = float(produto.get("priceMin", 0) or 0)
    comissao = float(produto.get("commissionRate", 0) or 0)
    vendas = int(produto.get("sales", 0) or 0)
    nota = float(produto.get("ratingStar", 0) or 0)
    if not titulo: return "sem_titulo"
    if not link: return "sem_link"
    if tem_bloqueio(titulo): return "bloqueado"
    if preco < PRECO_MIN: return "preco_baixo"
    if preco > PRECO_MAX: return "preco_alto"
    if comissao < COMISSAO_MIN: return "comissao_baixa"
    if vendas < VENDAS_MIN: return "poucas_vendas"
    if nota and nota < AVALIACAO_MIN: return "nota_baixa"
    if link in ULTIMOS_LINKS or link in LINKS_CICLO_ATUAL: return "link_repetido"
    return None

def enviado_anteriormente(chave):
    historico = carregar_historico()
    if chave in historico:
        try:
            data = datetime.fromisoformat(historico[chave]).replace(tzinfo=FUSO_BR)
            return (datetime.now(FUSO_BR) - data) < timedelta(days=HISTORICO_DIAS)
        except:
            return False
    return False

def registrar_envio(chave):
    historico = carregar_historico()
    historico[chave] = datetime.now(FUSO_BR).isoformat()
    limite = datetime.now(FUSO_BR) - timedelta(days=HISTORICO_DIAS * 3)
    historico_limpo = {k: v for k, v in historico.items() if datetime.fromisoformat(v).replace(tzinfo=FUSO_BR) >= limite}
    salvar_historico(historico_limpo)

def identificar_familia(titulo):
    norm = normalizar(titulo)
    for familia, palavras in FAMILIAS_PRODUTOS.items():
        if any(normalizar(p) in norm for p in palavras):
            return familia
    return "outros"

# =========================
# VALIDAÇÃO DE RELEVÂNCIA
# =========================
def validar_modelo(titulo, modelo):
    norm_titulo = normalizar(titulo)
    norm_modelo = normalizar(modelo)
    return all(p in norm_titulo for p in norm_modelo.split() if len(p) > 2)

def validar_peca(titulo, peca):
    norm_titulo = normalizar(titulo)
    norm_peca = normalizar(peca)
    equivalencias = {
        "kit relacao": ["kit relacao", "relação completa", "kit transmissão"],
        "jogo de juntas": ["jogo de juntas", "juntas"],
        "burrinho de freio": ["burrinho de freio", "cilindro mestre"],
        "par pneu": ["par pneu", "kit pneu", "pneus"]
    }
    return any(normalizar(alt) in norm_titulo for alt in equivalencias.get(norm_peca, [norm_peca]))

def validar_relevancia(nicho, titulo, termo="", modelo=None, peca=None):
    norm_titulo = normalizar(titulo)
    if nicho == "Eletrônicos" and any(p in norm_titulo for p in ["capa", "pelicula"]) and not any(p in norm_titulo for p in ["celular", "tablet", "iphone"]):
        return False
    if nicho == "Casa" and "tinta" in norm_titulo and not any(p in norm_titulo for p in ["parede", "spray"]):
        return False
    if nicho == "Moda Feminina" and any(p in norm_titulo for p in ["masculino", "homem"]):
        return False
    if nicho == "Moda Masculina" and any(p in norm_titulo for p in ["feminino", "mulher"]):
        return False
    if nicho == "Maternidade" and any(p in norm_titulo for p in ["organizadora", "cozinha"]) and not any(p in norm_titulo for p in ["bebe", "infantil"]):
        return False
    if nicho == "Moto":
        if modelo and not validar_modelo(titulo, modelo):
            return False
        if peca and not validar_peca(titulo, peca):
            return False
    return True

# =========================
# BUSCA NA API DA SHOPEE
# =========================
def buscar_produtos(termo, nicho):
    logging.info("🔍 Buscando em %s: %s", nicho, termo)
    ts = int(time.time())
    ordem = random.choice(TIPOS_ORDEM)
    pagina = random.randint(1, MAX_PAGINA_BUSCA)
    termo_busca = variar_termo(termo)
    logging.info("   ↳ Ordem=%s | Página=%s | Buscando: %s", ordem, pagina, termo_busca)

    consulta = f'query {{productOfferV2(sortType:{ordem},page:{pagina},limit:50,keyword:{json.dumps(termo_busca, ensure_ascii=False)},isAMSOffer:true){{nodes{{productName,priceMin,priceMax,commissionRate,sales,ratingStar,productLink,offerLink,imageUrl,shopType}}}}}}'

    payload = json.dumps({"query": consulta}, ensure_ascii=False)
    assinatura = hashlib.sha256(f"{SHOPEE_APP_ID}{ts}{payload}{SHOPEE_PASSWORD}".encode()).hexdigest()
    cabecalhos = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={ts}, Signature={assinatura}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        resp = requests.post(SHOPEE_GRAPHQL_URL, data=payload.encode("utf-8"), headers=cabecalhos, timeout=25)
        resp.raise_for_status()
        dados = resp.json()
        if dados.get("errors"):
            logging.error("API Erro: %s", dados["errors"])
            return []
        produtos = dados.get("data", {}).get("productOfferV2", {}).get("nodes", []) or []
        logging.info("✅ %s produtos encontrados (página %s, ordem %s)", len(produtos), pagina, ordem)
        return produtos
    except Exception as e:
        logging.error("❌ Falha na busca: %s", e)
        return []

# =========================
# SELECIONA OS PRODUTOS
# =========================
def selecionar(nicho, termo, quantidade, estado, moto=False, peca=None):
    termo_completo = f"{peca} {termo}" if moto else termo
    resposta = buscar_produtos(termo_completo, nicho)
    validos = []
    motivos = Counter()

    for p in resposta:
        motivo = avaliar_rejeicao(p)
        if motivo:
            motivos[motivo] += 1
            CONTADOR_REJEICOES[motivo] += 1
        else:
            validos.append(p)

    logging.info("📊 %s [%s]: %s brutos / %s válidos", nicho, termo_completo, len(resposta), len(validos))

    if validos:
        com_pontuacao = [(p, pontuar_produto(p, termo)) for p in validos]
        pesos = [max(1, nota ** 1.5) for _, nota in com_pontuacao]
        indices = random.choices(range(len(com_pontuacao)), weights=pesos, k=len(com_pontuacao))
        validos = [com_pontuacao[i][0] for i in indices]

    escolhidos = []
    titulos_usados = []
    familias = Counter()

    for p in validos:
        if len(escolhidos) >= quantidade:
            break
        titulo = str(p.get("productName", "")).strip()
        link = str(p.get("offerLink") or p.get("productLink") or "").strip()
        chave = chave_titulo(titulo)
        familia = identificar_familia(titulo)
        id_historico = hashlib.md5(f"{chave}|{link}".encode()).hexdigest()

        if link in LINKS_CICLO_ATUAL or link in ULTIMOS_LINKS:
            continue
        if duplicata_forte(titulo) or produto_parecido(titulo, titulos_usados):
            continue
        if not validar_relevancia(nicho, titulo, termo, termo if moto else None, peca):
            motivos["irrelevante"] += 1
            continue
        if familias[familia] >= LIMITE_POR_FAMILIA:
            continue
        if enviado_anteriormente(id_historico):
            continue

        escolhidos.append(p)
        titulos_usados.append(titulo)
        familias[familia] += 1
        LINKS_CICLO_ATUAL.add(link)
        ULTIMOS_LINKS.append(link)
        ULTIMOS_TITULOS.append(titulo)
        registrar_envio(id_historico)
        logging.info("🏆 Selecionado | %s | família: %s", titulo[:60], familia)

    del ULTIMOS_LINKS[:-300]
    del ULTIMOS_TITULOS[:-150]
    if motivos:
        logging.info("📋 Motivos da rejeição: %s", dict(motivos))
    return escolhidos, estado

# =========================
# MONTAR LISTA DE OFERTAS
# =========================
def obter_ofertas_shopee():
    global LINKS_CICLO_ATUAL, BASES_VISTAS, TERMOS_USADOS_CICLO
    LINKS_CICLO_ATUAL = set()
    BASES_VISTAS = set()
    TERMOS_USADOS_CICLO = set()
    selecionados = []
    estado = carregar_estado()

    peca, moto, estado = proxima_busca_moto(estado)
    itens, estado = selecionar("Moto", moto, 1, estado, True, peca)
    selecionados.extend([("Moto", p) for p in itens])

    configuracao = {
        "Casa": 2,
        "Maternidade": 2,
        "Eletrônicos": 2,
        "Moda Feminina": 1,
        "Moda Masculina": 1
    }
    for nicho, qtd in configuracao.items():
        for _ in range(qtd):
            termo, estado = proximo_termo(nicho, estado)
            itens, estado = selecionar(nicho, termo, 1, estado)
            selecionados.extend([(nicho, p) for p in itens])

    salvar_estado(estado)
    selecionados.sort(key=lambda x: pontuar_produto(x[1], x[0]), reverse=True)
    logging.info("✅ Total: %s | Enviando: %s/%s", len(selecionados), min(len(selecionados), MAX_OFERTAS), MAX_OFERTAS)
    return selecionados[:MAX_OFERTAS]

# =========================
# TEXTOS E MENSAGENS
# =========================
CHAMADAS = [
    "👇 Corre antes que acabe!",
    "⚡ Clique antes de aumentar!",
    "🚀 Estoque limitado!",
    "💥 Melhor preço do ano!",
    "🎯 Compre antes dos outros!",
    "🏃 Corra, acabando rápido!",
    "⏰ Acaba hoje!",
    "💰 Economia real!",
    "⭐ Super oferta!",
    "🛒 Não perca!"
]

ABERTURAS = [
    "🚨 Isso não aparece todo dia!",
    "👀 Olha o que encontrei…",
    "🔥 Aproveita enquanto dá!",
    "💥 Ninguém esperava isso…",
    "🛑 Para tudo e olha!",
    "🤯 Difícil de achar barato assim!",
    "⚠️ Pode sumir a qualquer hora…",
    "👁️ Pouca gente viu ainda…",
    "📉 Preço caiu de verdade!",
    "🚀 Tá começando a bombar!"
]

GATILHOS = [
    "Bem abaixo do preço normal",
    "Avaliações excelentes",
    "Muita gente comprando",
    "Simples e funciona bem",
    "Custo-benefício impressionante",
    "Quem compra recomenda",
    "Produto confiável",
    "Saindo muito rápido",
    "Boa comissão pra afiliado",
    "Resolve o problema direto"
]

def anexar_afiliado(link):
    try:
        u = urlparse(link)
        parametros = parse_qs(u.query)
        parametros["af_siteid"] = AFILIADO_ID
        return urlunparse(u._replace(query=urlencode(parametros, doseq=True)))
    except:
        return link

def link_whatsai(texto):
    limpo = re.sub(r"<[^>]+>", "", texto)
    return f"https://wa.me/?text={quote(limpo)}"

def montar_mensagem(nome, preco, vendas, nota, comissao, link):
    abertura = random.choice([a for a in ABERTURAS if a not in ABERTURAS_USADAS])
    gatilho = random.choice([g for g in GATILHOS if g not in GATILHOS_USADOS])
    chamada = random.choice(CHAMADAS)
    ABERTURAS_USADAS.add(abertura)
    GATILHOS_USADOS.add(gatilho)
    return (
        f"{html.escape(abertura)}\n\n"
        f"🔥 <b>{html.escape(nome)}</b>\n\n"
        f"{html.escape(gatilho)}\n\n"
        f"{html.escape(chamada)}\n\n"
        f"💰 <b>R$ {preco}</b>\n"
        f"⭐ <b>{nota} | {vendas} vendas</b>\n"
        f"💸 Comissão: <b>{comissao}%</b>\n\n"
        f"⚠️ Pode alterar de preço\n\n"
        f'<a href="{html.escape(link)}">🛒 COMPRAR AGORA</a>\n\n'
        f'<a href="{LINK_GRUPO_OFERTAS}">📲 Entrar no grupo</a>'
    )

def mensagem_whatsai(nome, preco, vendas, nota, link, abertura, gatilho, chamada):
    return (
        f"{abertura}\n🔥 {nome}\n{gatilho}\n{chamada}\n💰 R$ {preco}\n⭐ {nota} | {vendas} vendas\n⚠️ Pode variar\n🛒 {link}\n📲 Grupo: {LINK_GRUPO_OFERTAS}"
    )

# =========================
# ENVIO TELEGRAM
# =========================
async def enviar_foto(contexto, item, chat_id):
    try:
        await contexto.bot.send_photo(chat_id=chat_id, photo=item["imagem"], caption=item["texto"], parse_mode="HTML")
        return True
    except Exception as e:
        logging.warning("⚠️ Falha ao enviar imagem: %s", e)
    try:
        await contexto.bot.send_message(chat_id=chat_id, text=item["texto"], parse_mode="HTML")
        return True
    except Exception as e:
        logging.error("❌ Falha ao enviar mensagem: %s", e)
    return False

async def enviar_lote(contexto, lista):
    await contexto.bot.send_message(chat_id=CHAT_ID_DESTINO, text="🚨 <b>OFERTAS NOVAS CHEGANDO…</b>", parse_mode="HTML")
    await asyncio.sleep(5)
    for item in lista:
        logging.info("📤 Enviando: %s", item["nicho"])
        enviado = await enviar_foto(contexto, item, CHAT_ID_DESTINO)
        if enviado:
            chave = item["historico"]
            registrar_envio(chave)
        await asyncio.sleep(40)

# =========================
# CICLO PRINCIPAL
# =========================
async def ciclo_envio(contexto):
    try:
        logging.info("========== 🔄 INÍCIO DO CICLO ==========")
        if not horario_valido():
            logging.info("⏹️ Fora do horário permitido (05:30–21:30)")
            return
        ABERTURAS_USADAS.clear()
        GATILHOS_USADOS.clear()
        ofertas = obter_ofertas_shopee()
        if len(ofertas) < MIN_OFERTAS:
            logging.warning("⚠️ Apenas %s ofertas (mínimo %s)", len(ofertas), MIN_OFERTAS)
            return

        mensagens = []
        for nicho, produto in ofertas:
            try:
                titulo = str(produto.get("productName", "")).strip()
                link_bruto = str(produto.get("offerLink") or produto.get("productLink") or "").strip()
                if not titulo or not link_bruto:
                    continue
                link = anexar_afiliado(link_bruto)
                preco = float(produto.get("priceMin", 0) or 0)
                vendas = int(produto.get("sales", 0) or 0)
                nota = float(produto.get("ratingStar", 4.5) or 4.5)
                comissao = round(float(produto.get("commissionRate", 0) or 0) * 100, 2)
                imagem = str(produto.get("imageUrl") or "").strip()

                str_preco = f"{preco:.2f}".replace(".", ",")
                str_vendas = f"{vendas:,}".replace(",", ".")
                str_nota = f"{nota:.1f}".replace(".", ",")

                abertura = random.choice([a for a in ABERTURAS if a not in ABERTURAS_USADAS])
                gatilho = random.choice([g for g in GATILHOS if g not in GATILHOS_USADOS])
                chamada = random.choice(CHAMADAS)
                ABERTURAS_USADAS.add(abertura)
                GATILHOS_USADOS.add(gatilho)

                texto = montar_mensagem(titulo, str_preco, str_vendas, str_nota, comissao, link)
                link_whats = link_whatsai(mensagem_whatsai(titulo, str_preco, str_vendas, str_nota, link, abertura, gatilho, chamada))
                texto += f'\n<a href="{link_whats}">📲 Compartilhar WhatsApp</a>\n━━━━━━━━━━━━━━━━\n📢 <b>Ofertas do Dia</b>'

                id_historico = hashlib.md5(f"{chave_titulo(titulo)}|{link_bruto}".encode()).hexdigest()
                mensagens.append({"texto": texto, "imagem": imagem, "historico": id_historico, "nicho": nicho})
            except Exception as e:
                logging.error("❌ Erro ao montar mensagem: %s", e)

        if len(mensagens) < MIN_OFERTAS:
            logging.warning("⚠️ Menos de %s ofertas válidas após formatação", MIN_OFERTAS)
            return

        await enviar_lote(contexto, mensagens)

        logging.info("========== 🆓 OFERTA GRATUITA ==========")
        estado = carregar_estado()
        indice_gratis = estado.get("indice_nicho_gratis", 0)
        nicho_gratis = ROTACAO_NICHO_GRATIS[indice_gratis % len(ROTACAO_NICHO_GRATIS)]
        estado["indice_nicho_gratis"] = (indice_gratis + 1) % len(ROTACAO_NICHO_GRATIS)
        salvar_estado(estado)
        oferta_gratis = next((m for m in mensagens if m["nicho"] == nicho_gratis), None) or (mensagens[0] if mensagens else None)
        if oferta_gratis and await enviar_foto(contexto, oferta_gratis, FREE_CHAT_ID):
            logging.info("✅ Enviado gratuito: %s", oferta_gratis["nicho"])
        else:
            logging.warning("⚠️ Sem oferta grátis para %s", nicho_gratis)

        logging.info("========== ✅ CICLO FINALIZADO ==========")
    except Exception as e:
        logging.error("❌ ERRO NO CICLO: %s", e, exc_info=True)

# =========================
# LOOP PRINCIPAL
# =========================
async def loop(aplicativo):
    logging.info("🔄 Ciclo automático iniciado")
    ultima_execucao = 0
    while True:
        agora = time.time()
        if agora - ultima_execucao >= CHECK_INTERVAL:
            await ciclo_envio(type("Contexto", (), {"bot": aplicativo.bot})())
            ultima_execucao = agora
        logging.info("💚 Aguardando… | %s", datetime.now(FUSO_BR).strftime("%d/%m às %H:%M"))
        await asyncio.sleep(60)

async def manter_vivo():
    while True:
        logging.info("💓 Bot ativo | %s", datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M"))
        await asyncio.sleep(300)

# =========================
# INICIAR BOT
# =========================
def verificar_variaveis():
    obrigatorias = ["TELEGRAM_TOKEN", "SHOPEE_PASSWORD", "SHOPEE_APP_ID"]
    faltando = [v for v in obrigatorias if not globals().get(v, "")]
    if faltando:
        raise RuntimeError(f"Variáveis obrigatórias faltando: {', '.join(faltando)}")

def iniciar():
    verificar_variaveis()
    logging.info("=" * 45)
    logging.info("🚀 SHOPEE BOT V30 — SEM REPETIÇÃO")
    logging.info("🔄 Ordem, página e termo variam por busca")
    logging.info("📦 Histórico 30 dias + 1 por família")
    logging.info("=" * 45)

    async def principal():
        app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
        logging.info("🤖 Bot carregado com sucesso")
        asyncio.create_task(manter_vivo())
        await loop(app)

    try:
        asyncio.run(principal())
    except Exception as e:
        logging.error("🔄 Reiniciando em 15s: %s", e)
        time.sleep(15)
        iniciar()

if __name__ == "__main__":
    iniciar()
