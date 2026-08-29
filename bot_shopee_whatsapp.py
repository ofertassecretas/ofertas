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
PRECO_MIN = 10  # ✅ ALTERADO PARA R$ 10
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
        f"{base} barato",
        f"{base} 2025",
    ]
    return random.choice(variacoes)

GRUPO_SINONIMOS = {
    "smartwatch": {"smartwatch", "relogio inteligente"},
    "airfryer": {"air fryer", "fritadeira sem oleo", "fritadeira eletrica"},
    "fone": {"fone bluetooth", "fone ouvido", "fone sem fio"},
    "caixa_som": {"caixa de som", "alto falante"},
    "tv": {"smart tv", "televisao", "tv led"},
    "notebook": {"notebook", "laptop"},
    "tablet": {"tablet"},
    "celular": {"celular", "smartphone", "aparelho celular"}
}

MAPA_SINONIMOS = {normalizar(t): g for g, ts in GRUPO_SINONIMOS.items() for t in ts}

def termo_ja_usado(termo):
    grupo = MAPA_SINONIMOS.get(normalizar(termo))
    return bool(grupo and any(MAPA_SINONIMOS.get(normalizar(t)) == grupo for t in TERMOS_USADOS_CICLO))

# =========================
# LISTAS DE PRODUTOS
# =========================
MOTOS = ["titan 150", "cb 300", "factor 150", "titan 160", "tornado 250", "fazer 150", "bros 160", "twister 250", "biz 125", "pop 110", "xre 300", "crosser 150", "xre 190", "fazer 250", "lander 250"]
PECAS_MOTO = [
    "kit relacao", "embreagem completa", "bateria", "filtro oleo",
    "cabo embreagem", "cabo freio", "vela ignicao", "pneu dianteiro",
    "disco freio", "pastilha freio", "corrente", "pistao", "anel pistao"
]

PRODUTOS_POR_NICHO = {
    "Casa": ["fritadeira sem oleo", "aspirador", "liquidificador", "cafeteira", "panela eletrica", "ferro passar", "ventilador", "batedeira", "cortina", "tapete", "lampada led"],
    "Bebê": ["carrinho bebe", "berco", "fralda", "brinquedo bebe", "roupa bebe", "banheira bebe", "cadeirinha bebe"],
    "Eletrônicos": ["smartwatch", "fone ouvido bluetooth", "caixa som bluetooth", "carregador", "cabo usb", "pendrive", "mouse", "teclado"],
    "Moda Feminina": ["vestido", "blusa", "calca", "saia", "tenis feminino", "bolsa", "oculos sol"],
    "Moda Masculina": ["camiseta", "bermuda", "calca jeans", "tenis masculino", "bone", "cinto"]
}

FAMILIAS_PRODUTOS = {
    "fritadeira": ["fritadeira", "air fryer"],
    "smartwatch": ["smartwatch", "relogio inteligente"],
    "fone": ["fone", "ouvido", "bluetooth"],
    "tv": ["tv", "televisao"],
    "bebe": ["bebe", "infantil", "crianca"],
    "moda_fem": ["vestido", "blusa", "saia", "mulher", "feminina"],
    "moda_masc": ["camiseta", "bermuda", "masculino", "homem"],
    "casa": ["panela", "utensilio", "cozinha"]
}

ROTACAO_NICHO_GRATIS = ["Casa", "Bebê", "Eletrônicos", "Moda Feminina", "Moda Masculina"]

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
        for nicho in PRODUTOS_POR_NICHO:
            estado[nicho] = {"indice": 0, "data": hoje}
    estado.setdefault("Moto", {"data": "", "indice": 0})
    for chave in list(PRODUTOS_POR_NICHO.keys()) + ["Moto", "indice_nicho_gratis"]:
        if chave not in estado or not isinstance(estado[chave], dict):
            estado[chave] = {"indice": 0, "data": datetime.now(FUSO_BR).strftime("%Y%m%d")}
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
    ignorar = {"premium", "novo", "promocao", "promoção", "super", "original", "kit", "completo"}
    palavras = [p for p in normalizar(titulo).split() if p not in ignorar and len(p) > 2]
    return " ".join(sorted(palavras)[:8])

def tem_bloqueio(texto):
    texto = normalizar(texto)
    proibidas = ["teste", "amostra", "nao venda", "exposicao", "promocao interna"]
    return any(p in texto for p in proibidas)

def duplicata_forte(titulo):
    chave_nova = chave_titulo(titulo)
    norm_nova = normalizar(titulo)
    for t in ULTIMOS_TITULOS:
        chave_antiga = chave_titulo(t)
        norm_antiga = normalizar(t)
        if chave_nova == chave_antiga or SequenceMatcher(None, norm_nova, norm_antiga).ratio() >= SIMILARIDADE_MAX:
            return True
    return False

def produto_parecido(titulo, lista):
    chave_nova = chave_titulo(titulo)
    norm_nova = normalizar(titulo)
    for t in lista:
        if chave_titulo(t) == chave_nova or SequenceMatcher(None, norm_nova, normalizar(t)).ratio() >= .84:
            return True
    return False

def pontuar_loja(tipos):
    try:
        return 3 if tipos and 1 in tipos else 2 if tipos and 4 in tipos else 1 if tipos and 2 in tipos else 0
    except:
        return 0

def pontuar_produto(produto, termo=""):
    try:
        vendas = int(produto.get("sales_count", 0) or produto.get("sales", 0) or 0)
        nota = float(produto.get("rating_average", 0) or produto.get("ratingStar", 0) or 0)
        comissao = float(produto.get("commission_rate", 0) or 0) * 100
        preco = float(produto.get("price", 0) or produto.get("price_min", 0) or 0) / 1000
        titulo = normalizar(produto.get("name", "") or produto.get("productName", ""))
        termo_norm = normalizar(termo)
        pontuacao = min(vendas / 8, 25) + nota * 2 + comissao * 2 + pontuar_loja(produto.get("shop_type"))
        if 50 <= preco <= 500:
            pontuacao += 6
        if termo_norm:
            pontuacao += 8 if termo_norm in titulo else sum(2 for p in termo_norm.split() if p in titulo)
        return max(0, pontuacao)
    except:
        return 0

def avaliar_rejeicao(produto):
    titulo = str(produto.get("name", "") or produto.get("productName", "")).strip()
    link = str(produto.get("affiliate_link") or produto.get("url", "") or "").strip()
    preco = float(produto.get("price", 0) or produto.get("price_min", 0) or 0) / 1000
    comissao = float(produto.get("commission_rate", 0) or 0) * 100
    vendas = int(produto.get("sales_count", 0) or produto.get("sales", 0) or 0)
    nota = float(produto.get("rating_average", 0) or produto.get("ratingStar", 0) or 0)
    if not titulo: return "sem_titulo"
    if not link: return "sem_link"
    if tem_bloqueio(titulo): return "bloqueado"
    if preco < PRECO_MIN: return "preco_baixo"
    if preco > PRECO_MAX: return "preco_alto"
    if comissao < COMISSAO_MIN * 100: return "comissao_baixa"
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
    return all(p in normalizar(titulo) for p in normalizar(modelo).split() if len(p) > 2)

def validar_peca(titulo, peca):
    norm_titulo = normalizar(titulo)
    equivalencias = {
        "kit relacao": ["relacao", "corrente", "pinhão", "coroa"],
        "embreagem": ["embreagem", "disco embraiagem"]
    }
    return any(alt in norm_titulo for alt in equivalencias.get(normalizar(peca), [normalizar(peca)]))

def validar_relevancia(nicho, titulo, termo="", modelo=None, peca=None):
    norm_titulo = normalizar(titulo)
    if nicho == "Eletrônicos" and any(p in norm_titulo for p in ["capa", "pelicula"]) and not any(p in norm_titulo for p in ["celular", "tablet"]):
        return False
    if peca and not validar_peca(titulo, peca):
        return False
    if modelo and not validar_modelo(titulo, modelo):
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

    consulta = f'query {{productOfferV2(sortType:{ordem},page:{pagina},limit:50,keyword:{json.dumps(termo_busca, ensure_ascii=False)},isAMSOffer:false){{nodes{{name,productName,price,priceMin,commissionRate,salesCount,sales,ratingAverage,ratingStar,affiliateLink,url,image,shopType}}}}}}'

    payload = json.dumps({"query": consulta}, ensure_ascii=False)
    assinatura = hashlib.sha256(f"{SHOPEE_APP_ID}{ts}{payload}{SHOPEE_PASSWORD}".encode()).hexdigest()
    cabecalhos = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID},Timestamp={ts},Signature={assinatura}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        resp = requests.post(SHOPEE_GRAPHQL_URL, data=payload.encode("utf-8"), headers=cabecalhos, timeout=25)
        resp.raise_for_status()
        dados = resp.json()
        if dados.get("errors"):
            logging.error("API Erro: %s", dados["errors"])
            return []
        produto_chave = dados.get("data", {}).get("productOfferV2", {})
        produtos = produto_chave.get("nodes", []) or []
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
        titulo = str(p.get("name") or p.get("productName", "")).strip()
        link = str(p.get("affiliateLink") or p.get("url", "") or "").strip()
        chave = chave_titulo(titulo)
        familia = identificar_familia(titulo)
        id_historico = hashlib.md5(f"{chave}|{link}".encode()).hexdigest()

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
        logging.info("📋 Motivos de exclusão: %s", dict(motivos))
    return escolhidos, estado

# =========================
# MONTAR LISTA DE OFERTAS
# =========================
def obter_ofertas_shopee():
    global LINKS_CICLO_ATUAL, BASES_VISTAS, TERMOS_USADOS_CICLO
    LINKS_CICLO_ATUAL.clear()
    BASES_VISTAS.clear()
    TERMOS_USADOS_CICLO.clear()
    selecionados = []
    estado = carregar_estado()

    peca, moto, estado = proxima_busca_moto(estado)
    itens, estado = selecionar("Moto", moto, 1, estado, True, peca)
    selecionados.extend([("Moto", p) for p in itens])

    configuracao = {
        "Casa": 2,
        "Bebê": 2,
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
    "🏃 Acaba rápido, aproveita!",
    "⏰ Corre, acaba hoje!",
    "💰 Economia de verdade!",
    "⭐ Super oferta!",
    "🛒 Não perca essa chance!"
]

ABERTURAS = [
    "🚨 Isso não aparece todo dia!",
    "👀 Olha o que encontrei…",
    "🔥 Aproveita enquanto dá!",
    "💥 Difícil achar barato assim!",
    "🛑 Para tudo e olha!",
    "🤯 Preço caiu demais!",
    "⚠️ Pode sumir a qualquer hora…",
    "📉 Caiu de preço agora!",
    "🚀 Tá bombando de comprar!"
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
    "Entrega rápida garantida",
    "Loja confiável e oficial"
]

def anexar_afiliado(link):
    try:
        u = urlparse(link)
        params = parse_qs(u.query)
        params["af_siteid"] = AFILIADO_ID
        return urlunparse(u._replace(query=urlencode(params, doseq=True)))
    except:
        return link

def link_whatsai(texto):
    limpo = re.sub(r"<[^>]+>", "", texto)
    return f"https://wa.me/?text={quote(limpo)}"

def montar_mensagem_tg(nome, preco, vendas, nota, comissao, link):
    abertura = random.choice([a for a in ABERTURAS if a not in ABERTURAS_USADAS])
    gatilho = random.choice([g for g in GATILHOS if g not in GATILHOS_USADOS])
    chamada = random.choice(CHAMADAS)
    ABERTURAS_USADAS.add(abertura)
    GATILHOS_USADOS.add(gatilho)
    return (
        f"{html.escape(abertura)}\n\n"
        f"🔥 <b>Produto:</b> {html.escape(nome)}\n\n"
        f"💰 <b>Preço:</b> R$ {preco}\n"
        f"📊 <b>Vendas:</b> {vendas}\n"
        f"⭐ <b>Avaliação:</b> {nota}\n"
        f"💼 <b>Comissão:</b> {comissao}%\n\n"
        f"{html.escape(gatilho)}\n\n"
        f"{html.escape(chamada)}\n\n"
        f'<a href="{html.escape(link)}">🛒 COMPRAR AGORA</a>\n\n'
        f'<a href="{LINK_GRUPO_OFERTAS}">📲 Entrar no grupo de ofertas</a>'
    )

def mensagem_whatsai(nome, preco, vendas, nota, comissao, link):
    # ✅ Palavras-chave em NEGRITO (usa * para negrito no WhatsApp)
    # ✅ REMOVIDA a frase de margem de afiliado
    return (
        f"🔥 *Produto:* {nome}\n\n"
        f"💰 *Preço:* R$ {preco}\n"
        f"📊 *Vendas:* {vendas}\n"
        f"⭐ *Avaliação:* {nota}\n"
        f"💼 *Comissão:* {comissao}%\n\n"
        f"🛒 Aproveite pelo link:\n{link}"
    )

# =========================
# ENVIO TELEGRAM
# =========================
async def enviar_foto(contexto, item, chat_id):
    try:
        await contexto.bot.send_photo(
            chat_id=chat_id,
            photo=item["imagem"],
            caption=item["texto"],
            parse_mode="HTML"
        )
        return True
    except Exception as e:
        logging.warning("⚠️ Falha ao enviar imagem: %s", e)
    try:
        await contexto.bot.send_message(
            chat_id=chat_id,
            text=item["texto"],
            parse_mode="HTML"
        )
        return True
    except Exception as e:
        logging.error("❌ Falha ao enviar mensagem: %s", e)
    return False

async def enviar_lote(contexto, lista):
    await contexto.bot.send_message(
        chat_id=CHAT_ID_DESTINO,
        text="🚨 <b>OFERTAS NOVAS ACABARAM DE CHEGAR!</b>",
        parse_mode="HTML"
    )
    await asyncio.sleep(5)
    for item in lista:
        logging.info("📤 Enviando: %s", item["nicho"])
        enviado = await enviar_foto(contexto, item, CHAT_ID_DESTINO)
        if enviado:
            registrar_envio(item["historico"])
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
                titulo = str(produto.get("name") or produto.get("productName", "")).strip()
                link_bruto = str(produto.get("affiliateLink") or produto.get("url", "") or "").strip()
                if not titulo or not link_bruto:
                    continue
                link = anexar_afiliado(link_bruto)
                preco = float(produto.get("price", 0) or produto.get("priceMin", 0) or 0) / 1000
                vendas = int(produto.get("salesCount", 0) or produto.get("sales", 0) or 0)
                nota = float(produto.get("ratingAverage", 0) or produto.get("ratingStar", 0) or 0)
                comissao = round(float(produto.get("commissionRate", 0) or 0) * 100, 2)
                imagem = str(produto.get("image", "") or "").strip()

                str_preco = f"{preco:.2f}".replace(".", ",")
                str_vendas = f"{vendas:,}".replace(",", ".")
                str_nota = f"{nota:.1f}".replace(".", ",")

                abertura = random.choice([a for a in ABERTURAS if a not in ABERTURAS_USADAS])
                gatilho = random.choice([g for g in GATILHOS if g not in GATILHOS_USADOS])
                ABERTURAS_USADAS.add(abertura)
                GATILHOS_USADOS.add(gatilho)

                texto_tg = montar_mensagem_tg(titulo, str_preco, str_vendas, str_nota, comissao, link)
                texto_whats = mensagem_whatsai(titulo, str_preco, str_vendas, str_nota, comissao, link)
                link_compartilhar = link_whatsai(texto_whats)
                texto_tg += f'\n<a href="{link_compartilhar}">📲 Compartilhar no WhatsApp</a>'

                id_historico = hashlib.md5(f"{chave_titulo(titulo)}|{link_bruto}".encode()).hexdigest()
                mensagens.append({
                    "texto": texto_tg,
                    "imagem": imagem,
                    "historico": id_historico,
                    "nicho": nicho
                })
            except Exception as e:
                logging.error("❌ Erro ao montar mensagem: %s", e)

        if len(mensagens) < MIN_OFERTAS:
            logging.warning("⚠️ Menos de %s ofertas válidas", MIN_OFERTAS)
            return

        await enviar_lote(contexto, mensagens)

        logging.info("========== 🆓 OFERTA GRATUITA ==========")
        estado = carregar_estado()
        indice_gratis = estado.get("indice_nicho_gratis", 0)
        nicho_gratis = ROTACAO_NICHO_GRATIS[indice_gratis % len(ROTACAO_NICHO_GRATIS)]
        estado["indice_nicho_gratis"] = (indice_gratis + 1) % len(ROTACAO_NICHO_GRATIS)
        salvar_estado(estado)
        oferta_gratis = next((m for m in mensagens if m["nicho"] == nicho_gratis), None) or mensagens[0]
        if oferta_gratis and await enviar_foto(contexto, oferta_gratis, FREE_CHAT_ID):
            logging.info("✅ Grátis enviada: %s", oferta_gratis["nicho"])

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
        await asyncio.sleep(60)

async def manter_vivo():
    while True:
        logging.info("💓 Bot ativo | %s", datetime.now(FUSO_BR).strftime("%d/%m às %H:%M"))
        await asyncio.sleep(300)

# =========================
# INICIAR BOT
# =========================
def verificar_variaveis():
    obrigatorias = ["TELEGRAM_TOKEN", "SHOPEE_PASSWORD", "SHOPEE_APP_ID"]
    faltando = [v for v in obrigatorias if not os.getenv(v, "").strip()]
    if faltando:
        raise RuntimeError(f"Defina as variáveis: {', '.join(faltando)}")

async def principal():
    verificar_variaveis()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    logging.info("🤖 Bot carregado! Aguardando ciclo…")
    asyncio.create_task(manter_vivo())
    await loop(app)

def iniciar():
    try:
        asyncio.run(principal())
    except Exception as e:
        logging.error("🔄 Reiniciando em 15s: %s", e)
        time.sleep(15)
        iniciar()

if __name__ == "__main__":
    iniciar()

