import asyncio, requests, logging, random, hashlib, math, time, json, os, html, re
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO SHOPEE V21 - SELECAO COMPACTA")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
CHAT_ID_DESTINO, FREE_CHAT_ID = -1003848415150, -1003886228244
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400
MAX_OFERTAS, MIN_OFERTAS = 10, 4
HISTORICO_DIAS = 7
SIMILARIDADE_MAX = 0.88
VENDAS_MIN, RATING_MIN = 2, 4.0
PRECO_MIN, PRECO_MAX = 15.0, 10000.0
COMISSAO_MIN = 0.03

LIMITE_VENDEDOR = 1
LIMITE_MARCA = 2
LIMITE_FAMILIA = 1

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

FUSO_BR = ZoneInfo("America/Sao_Paulo")
ESTADO_FILE, HISTORICO_FILE = "estado_buscas.json", "historico_envios.json"

ULTIMAS_BUSCAS_SHOPEE, ULTIMOS_TITULOS = [], []
usados_no_ciclo, BASES_VISTAS = set(), set()
REJEICOES = Counter()
VENDEDORES_NO_CICLO = Counter()
MARCAS_NO_CICLO = Counter()

def lista(texto):
    return [x.strip() for x in texto.split("|") if x.strip()]

MOTOS = lista(
    "titan 150|cb 300|factor 150|titan 160|tornado|fazer 150|titan 125|"
    "bros 160|twister 250|biz 125|pop 110|xre 300|crosser 150|xre 190|"
    "fazer 250|lander 250|bros 150|tenere 250|biz 100|twister 300"
)

PECAS_MOTO = lista(
    "kit relacao|kit embreagem|bateria|refil bomba combustivel|"
    "chicote fiação principal|bucha balança|burrinho de freio|estribo|"
    "pedal de marcha|pedal de freio|rolamento virabrequim|estator|"
    "chave ignição|punho chave luz|kit pisca seta|par pneu|bloco optico|"
    "retentor de bengala|bucha amortecedor|carburador corpo de injeção|"
    "kit cilindro|jogo de juntas|biela|valvulas escape admissão|"
    "disco de freio|tubo interno|vela iridium|pastilha freio|guidao|"
    "manopla|amortecedor|retrovisor|farol|lona de freio|cabo embreagem|"
    "cabo acelerador|coroa moto|pinhao moto|corrente moto|pedaleira|"
    "carenagem|lanterna traseira|capacete"
)

PRODUTOS_NICHO = {
    "Casa": lista(
        "air fryer|fritadeira eletrica|aspirador vertical|aspirador robo|"
        "liquidificador|cafeteira|cafeteira eletrica|cafeteira dolce gusto|"
        "cafeteira nespresso|panela eletrica|panela de pressão|jogo de panelas|"
        "mop|ventilador|batedeira|umidificador|ar condicionado|filtro de barro|"
        "tapete sala|tapete antiderrapante|torneira cozinha|caixa organizadora|"
        "sapateira|guarda roupas|cama casal|lençol|cobre leito|cortina|"
        "luminaria|pipoqueira|escorredor de louça|mangueira jardim|rede de dormir"
    ),
    "Maternidade": lista(
        "carrinho bebe|berco bebe|fralda descartavel|naninha|"
        "kit bolsa maternidade|kit mamadeira|babá eletronica|ninho bebe|"
        "kit enxoval bebe|babador bebe|mordedor bebe|tapete infantil|"
        "cadeirinha bebe|almofada amamentacao|termometro infantil|banheira bebe|"
        "mosqueteiro|canguru bebe|toalha infantil|fralda de pano|"
        "coberdrom bebe|bebe reborn|kit bicos"
    ),
    "Eletroeletrônicos": lista(
        "smartwatch|relogio inteligente|fone bluetooth|headset gamer|"
        "caixa de som bluetooth|soundbar|celular|smartphone|smart tv|televisão|"
        "video game|fone sem fio|webcam|pen drive|impressora termica|notebook|"
        "tablet|ssd|mouse gamer|teclado mecanico|power bank|carregador turbo|"
        "suporte celular carro|camera de segurança|gopro|drone|"
        "aparelho medidor de pressão|balança digital|massageador|massageador portatil"
    ),
    "Moda feminina": lista(
        "vestido feminino|conjunto feminino|biquini|saida de praia|roupa academia|"
        "calça jeans|calça legging|saia longa|vestido midi|jaqueta feminina|"
        "casaco feminino|conjunto alfaiataria|short feminino|macacao feminino|"
        "tenis feminino|bolsa feminina|blazer feminino|saia jeans|top feminino|"
        "body feminino|pijama feminino|blusa regata|oculos de sol|kit sutian"
    ),
    "Moda masculina": lista(
        "camiseta masculina|bermuda masculina|camisa polo|camisa de linho|"
        "camisa social masculina|moletom masculino|jaqueta masculina|"
        "tenis masculino|carteira masculina|kit cueca|calça jeans masculina|"
        "camisa termica|sapatenis masculino|camisa tshort|kit meias|barbeador|"
        "chuteiras|calção de futebol|oculos de sol"
    ),
}

FAMILIAS_EXTRA = {
    "air_fryer": lista("air fryer|airfryer|fritadeira|fritadeira eletrica"),
    "eletro_cozinha": lista("cafeteira|liquidificador|batedeira|panela eletrica|pipoqueira|mop"),
    "aspiradores": lista("aspirador|aspirador vertical|aspirador robo"),
    "fone_bluetooth": lista("fone bluetooth|fone sem fio|fones de ouvido|headset|earbud"),
    "smartwatch": lista("smartwatch|relogio inteligente|relógio inteligente|watch"),
    "caixa_som": lista("caixa de som|speaker|soundbar"),
    "smart_tv": lista("smart tv|televisão|tv"),
    "notebook": lista("notebook|notbook|laptop"),
    "tablet": lista("tablet|ipad|galaxy tab|xiaomi pad"),
    "celular": lista("celular|smartphone|telefone|iphone|android"),
    "maternidade_bebe": lista("bebe|bebê|fralda|carrinho|berco|mamadeira|ninho|babá|baba"),
    "moda_fem": lista("vestido|conjunto|saia|bolsa|sandalia|tenis feminino|body|pijama"),
    "moda_masc": lista("camisa|camiseta|calça|tenis masculino|jaqueta|bermuda|sapatenis"),
    "casa_lar": lista("tapete|lençol|cortina|organizador|caixa organizadora|luminaria|pipoqueira|air fryer"),
    "moto_geral": lista("capacete|vela|pastilha|lona|kit relação|corrente|coroa|pinhão|guidao|guidão|retrovisor|farol|lanterna"),
}

NICHOS_FREE_ROTA = [
    "Moto",
    "Casa",
    "Moda feminina",
    "Moda masculina",
    "Maternidade",
    "Eletroeletrônicos",
]

def carregar_estado():
    try:
        with open(ESTADO_FILE, "r", encoding="utf-8") as arquivo:
            estado = json.load(arquivo) if os.path.exists(ESTADO_FILE) else {}
    except Exception:
        estado = {}

    estado.setdefault("Moto", {})
    estado["Moto"].setdefault("peca_idx", 0)
    estado["Moto"].setdefault("moto_idx", 0)
    estado["Moto"].setdefault("resultado_idx", {})

    for nicho, produtos in PRODUTOS_NICHO.items():
        estado.setdefault(nicho, {})
        estado[nicho].setdefault("resultado_idx", {})
        estado[nicho].setdefault("produto_idx", 0)
        estado[nicho].setdefault("produtos_ordem", [])

        if not estado[nicho]["produtos_ordem"]:
            estado[nicho]["produtos_ordem"] = list(range(len(produtos)))
            random.shuffle(estado[nicho]["produtos_ordem"])

    estado.setdefault("free_nicho_idx", 0)
    return estado

def salvar_estado(estado):
    try:
        with open(ESTADO_FILE, "w", encoding="utf-8") as arquivo:
            json.dump(estado, arquivo, ensure_ascii=False)
    except Exception as erro:
        logging.error(f"Erro salvando estado: {erro}")

def carregar_historico():
    try:
        if os.path.exists(HISTORICO_FILE):
            with open(HISTORICO_FILE, "r", encoding="utf-8") as arquivo:
                return json.load(arquivo)
    except Exception:
        pass
    return {}

def salvar_historico(historico):
    try:
        with open(HISTORICO_FILE, "w", encoding="utf-8") as arquivo:
            json.dump(historico, arquivo, ensure_ascii=False)
    except Exception as erro:
        logging.error(f"Erro salvando historico: {erro}")

def normalizar_texto(texto):
    texto = str(texto or "").lower().strip()
    texto = re.sub(r"[^a-z0-9à-ÿ\s]", " ", texto)
    return re.sub(r"\s+", " ", texto)

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 30) <= agora <= dt_time(21, 30)

def chave_base_titulo(titulo):
    remover = set(lista(
        "premium|novo|nova|promocao|promoção|super|original|profissional|"
        "casual|masculino|feminino|infantil|adulto|unissex|kit|com|de|"
        "para|o|a|promo|oferta|modelo|versao|versão|linha|envio|usado|"
        "branco|preto|azul|vermelho|rosa|verde|amarelo|tamanho|tamanhos|"
        "unico|único|gamer|led|usb|mini|max|pro"
    ))
    return " ".join(sorted([
        x for x in normalizar_texto(titulo).split()
        if x not in remover and len(x) > 2
    ])[:8])

def assinatura_diversidade(titulo):
    remover = set(lista(
        "novo|nova|original|premium|profissional|promocao|promo|oferta|"
        "modelo|versao|kit|com|para|de|da|do|e|branco|preto|azul|"
        "vermelho|rosa|verde|amarelo|cinza|roxo|marrom|tamanho|tamanhos|"
        "unico|unica|bivolt|110v|127v|220v|usb|led|mini|max|pro|"
        "completo|completa|unissex"
    ))

    tokens = []
    for token in normalizar_texto(titulo).split():
        token = re.sub(r"[^a-z0-9]", "", token)

        if not token or token in remover or len(token) <= 2:
            continue

        if re.fullmatch(r"\d+(gb|tb|mb|cm|mm|kg|g|w|v|a)?", token):
            continue

        tokens.append(token)

    return " ".join(sorted(set(tokens))[:10]) or normalizar_texto(titulo)

def tem_bloqueio(titulo):
    return any(x in normalizar_texto(titulo) for x in [
        "teste", "amostra", "nao compre", "produto teste", "exemplo",
        "dummy", "vela led", "vela decorativa", "decorativa", "decoracao",
        "casamento", "festa", "replica", "generico", "display",
        "mostruario", "brinde"
    ])

def titulo_duplicado_forte(titulo):
    texto = normalizar_texto(titulo)
    base = chave_base_titulo(titulo)

    return any(
        texto == anterior
        or SequenceMatcher(None, texto, anterior).ratio() >= SIMILARIDADE_MAX
        or (base and base == chave_base_titulo(anterior))
        for anterior in ULTIMOS_TITULOS
    )

def identificar_marca(titulo):
    marcas = lista(
        "samsung|motorola|xiaomi|poco|redmi|iphone|apple|philco|mondial|"
        "britania|electrolux|oster|philips|walita|lenovo|asus|dell|acer|"
        "haylou|amazfit|mibro|huawei|colcci|lovito|farm|lancome|lupo|"
        "adidas|nike|jbl|lg|consul|brastemp|arno|cadence"
    )

    texto = normalizar_texto(titulo)
    return next((marca for marca in marcas if marca in texto), "sem_marca")

def identificar_vendedor(produto):
    if produto.get("shopId"):
        return f"id:{produto['shopId']}"

    if produto.get("shopName"):
        return f"nome:{normalizar_texto(produto['shopName'])}"

    try:
        dominio = urlparse(
            str(produto.get("offerLink") or produto.get("productLink") or "")
        ).netloc.lower()

        if dominio:
            return f"dominio:{dominio}"
    except Exception:
        pass

    return "vendedor_desconhecido"

def shop_type_score(shop_type):
    try:
        if not shop_type:
            return 0
        if 1 in shop_type:
            return 3
        if 4 in shop_type:
            return 2
        if 2 in shop_type:
            return 1
    except Exception:
        pass

    return 0

def penalidade_termo_fraco(nome):
    termos = lista(
        "generico|universal|mini|infantil|brinquedo|adesivo|capa|case|"
        "pelicula|display|mostruario|decorativo|replica|dummy|refil|"
        "kit reposicao|reposicao"
    )

    return -5 if any(x in normalizar_texto(nome) for x in termos) else 0

def oferta_score(produto, termo="", nicho=None):
    try:
        vendas = int(produto.get("sales", 0) or 0)
        avaliacao = float(produto.get("ratingStar", 0) or 0)
        comissao = float(produto.get("commissionRate", 0) or 0)
        preco = float(produto.get("priceMin", 0) or 0)
        preco_max = float(produto.get("priceMax", 0) or 0)
        nome = normalizar_texto(produto.get("productName", ""))
        termo = normalizar_texto(termo)

        if nicho == "Moto":
            score = min(vendas / 6, 30)
            score += avaliacao * 2.5
            score += comissao * 100
            score += shop_type_score(produto.get("shopType", []))
            score += penalidade_termo_fraco(nome)

            if 40 <= preco <= 3000:
                score += 7
            elif 3000 < preco <= 7000:
                score += 3

            if termo and termo in nome:
                score += 10
            elif termo and any(x in nome for x in termo.split()):
                score += 4

            if vendas >= 1000:
                score += 4
            if avaliacao >= 4.7:
                score += 2
            if comissao >= 0.08:
                score += 2

            return score

        score = math.log10(vendas + 1) * 8
        score += avaliacao * 3
        score += comissao * 100
        score += shop_type_score(produto.get("shopType", []))

        pontos_marcas = {
            "apple": 12, "iphone": 12, "samsung": 10,
            "motorola": 9, "xiaomi": 8, "poco": 8,
            "philips": 8, "electrolux": 8, "mondial": 6,
            "philco": 6, "britania": 6, "oster": 6,
            "jbl": 7, "nike": 7, "adidas": 7,
        }

        score += pontos_marcas.get(
            identificar_marca(nome),
            0
        )

        score += penalidade_termo_fraco(nome)

        if any(x in nome for x in lista(
            "pulseira|alca|pelicula|case|capinha|suporte|manual|"
            "adesivo|reparo|peca|refil|cabo"
        )):
            score -= 8

        if 40 <= preco <= 3000:
            score += 7
        elif 3000 < preco <= 7000:
            score += 3
        elif preco < 25:
            score -= 4

        if preco_max > preco > 0:
            desconto = (preco_max - preco) / preco_max

            if desconto >= 0.60:
                score += 12
            elif desconto >= 0.40:
                score += 8
            elif desconto >= 0.25:
                score += 4
            elif desconto < 0.05:
                score -= 3

        if termo and termo in nome:
            score += 10
        elif termo and any(x in nome for x in termo.split()):
            score += 4

        palavras = len(nome.split())

        if 3 <= palavras <= 12:
            score += 3
        elif palavras > 20:
            score -= 4

        if avaliacao >= 4.7:
            score += 3
        if vendas >= 1000:
            score += 2
        if comissao >= 0.08:
            score += 2

        return score

    except Exception:
        return 0

def motivo_rejeicao(produto):
    try:
        titulo = str(produto.get("productName", "")).strip()
        link = str(
            produto.get("offerLink")
            or produto.get("productLink")
            or ""
        ).strip()

        preco = float(produto.get("priceMin", 0) or 0)
        comissao = float(produto.get("commissionRate", 0) or 0)
        vendas = int(produto.get("sales", 0) or 0)
        avaliacao = float(produto.get("ratingStar", 0) or 0)

        if not titulo:
            return "sem_titulo"
        if not link:
            return "sem_link"
        if tem_bloqueio(titulo):
            return "bloqueio_texto"
        if preco < PRECO_MIN:
            return "preco_baixo"
        if preco > PRECO_MAX:
            return "preco_alto"
        if comissao < COMISSAO_MIN:
            return "comissao_baixa"
        if vendas < VENDAS_MIN:
            return "vendas_baixas"
        if avaliacao and avaliacao < RATING_MIN:
            return "rating_baixo"
        if link in ULTIMAS_BUSCAS_SHOPEE or link in usados_no_ciclo:
            return "link_repetido"

        return None

    except Exception as erro:
        return f"erro_validacao:{type(erro).__name__}"

def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    return urlunparse(
        parsed._replace(query=urlencode(query, doseq=True))
    )

def buscar_produtos_da_categoria_kw(palavra_chave, categoria):
    logging.info(f"Buscando em {categoria}: {palavra_chave}")
    timestamp = int(time.time())

    query_body = f"""
    query {{
        productOfferV2(
            sortType: 2,
            limit: 50,
            keyword: "{palavra_chave}",
            isAMSOffer: true
        ) {{
            nodes {{
                productName
                priceMin
                priceMax
                commissionRate
                sales
                ratingStar
                productLink
                offerLink
                imageUrl
                shopType
                shopId
                shopName
            }}
        }}
    }}
    """

    payload = json.dumps({"query": query_body}, ensure_ascii=False)
    assinatura = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(assinatura.encode()).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "Authorization": (
            f"SHA256 Credential={SHOPEE_APP_ID}, "
            f"Timestamp={timestamp}, "
            f"Signature={signature}"
        ),
    }

    resposta = requests.post(
        SHOPEE_GRAPHQL_URL,
        data=payload.encode("utf-8"),
        headers=headers,
        timeout=20,
    )

    resposta.raise_for_status()
    dados = resposta.json()

    if dados.get("errors"):
        logging.error(f"Erro GraphQL: {dados['errors']}")

    return (
        dados.get("data", {})
        .get("productOfferV2", {})
        .get("nodes", [])
        or []
    )

def historico_bloqueia(chave):
    historico = carregar_historico()

    if chave not in historico:
        return False

    try:
        data = datetime.fromisoformat(historico[chave])
        return datetime.now(FUSO_BR) - data < timedelta(days=HISTORICO_DIAS)
    except Exception:
        return False

def registrar_historico(chave):
    historico = carregar_historico()
    historico[chave] = datetime.now(FUSO_BR).isoformat()
    salvar_historico(historico)

def parse_familia_from_title(titulo):
    texto = normalizar_texto(titulo)

    for familia, termos in FAMILIAS_EXTRA.items():
        if any(normalizar_texto(x) in texto for x in termos):
            return familia

    return "outros"

def get_proximo_termo(nicho, estado):
    catalogo = [(x, "", "") for x in PRODUTOS_NICHO[nicho]]
    ordem = estado[nicho]["produtos_ordem"]
    indice = estado[nicho]["produto_idx"]
    posicao = ordem[indice % len(ordem)]

    estado[nicho]["produto_idx"] = (
        indice + 1
    ) % len(ordem)

    if estado[nicho]["produto_idx"] == 0:
        random.shuffle(ordem)

    return catalogo[posicao], estado

def get_proximas_combinacoes_moto(estado, quantidade=2):
    dados = estado["Moto"]
    peca_idx = dados["peca_idx"]
    moto_idx = dados["moto_idx"]
    peca = PECAS_MOTO[peca_idx]
    resultado = []

    for _ in range(quantidade):
        resultado.append((MOTOS[moto_idx], peca))
        moto_idx = (moto_idx + 1) % len(MOTOS)

    dados["peca_idx"] = (peca_idx + 1) % len(PECAS_MOTO)
    dados["moto_idx"] = moto_idx

    return resultado, estado

def validar_modelo_titulo(titulo, termo):
    texto = normalizar_texto(titulo)
    palavras = [
        x for x in normalizar_texto(termo).split()
        if len(x) > 2
    ]

    if not palavras:
        return True

    encontrados = sum(x in texto for x in palavras)
    return encontrados >= max(1, min(2, len(palavras)))

def validar_relevancia_nicho(nicho, titulo, termo=None, modelo=None, peca=None):
    texto = normalizar_texto(titulo)

    if nicho == "Eletroeletrônicos":
        if (
            any(x in texto for x in ["capa", "pelicula", "case"])
            and not any(x in texto for x in [
                "celular", "tablet", "smartphone", "iphone"
            ])
        ):
            return False

        if (
            any(x in texto for x in ["smart tv", "televisao"])
            and any(x in texto for x in [
                "mouse", "teclado", "ssd", "notebook"
            ])
        ):
            return False

    if nicho == "Casa" and any(x in texto for x in ["tinta", "tintas"]):
        if not any(x in texto for x in ["parede", "spray", "esmalte"]):
            return False

    if nicho == "Moda feminina" and any(
        x in texto for x in ["masculino", "homem", "masc"]
    ):
        return False

    if nicho == "Moda masculina" and any(
        x in texto for x in ["feminino", "mulher", "menina"]
    ):
        return False

    if nicho == "Maternidade":
        proibidos = ["organizador", "cozinha", "banheiro", "carro"]
        permitidos = [
            "bebe", "infantil", "maternidade", "fralda",
            "carrinho", "mamadeira", "ninho"
        ]

        if any(x in texto for x in proibidos):
            if not any(x in texto for x in permitidos):
                return False

    if nicho == "Moto":
        if modelo and not validar_modelo_titulo(titulo, modelo):
            return False
        if peca and not validar_modelo_titulo(titulo, peca):
            return False
        if termo and not validar_modelo_titulo(titulo, termo):
            return False

    return True

def selecionar_ofertas_termo(nicho, termo, cota, estado, e_moto=False, peca=None):
    global BASES_VISTAS

    palavra_chave = termo if not e_moto else f"{peca} {termo}"
    resultados = buscar_produtos_da_categoria_kw(
        palavra_chave,
        nicho
    )

    filtrados = [
        produto for produto in resultados
        if motivo_rejeicao(produto) is None
    ]

    filtrados.sort(
        key=lambda produto: oferta_score(
            produto,
            termo,
            nicho
        ),
        reverse=True
    )

    escolhidos = []
    titulos_ciclo = []
    assinaturas_ciclo = set()
    familias_ciclo = Counter()
    motivos = Counter()

    for produto in filtrados:
        if len(escolhidos) >= cota:
            break

        titulo = str(
            produto.get("productName", "")
        ).strip()

        link = (
            produto.get("offerLink")
            or produto.get("productLink")
        )

        if not titulo or not link:
            continue

        if nicho == "Moto":
            base = chave_base_titulo(titulo)
            produto_id = hashlib.md5(
                f"{base}|{link}".encode()
            ).hexdigest()
        else:
            base = assinatura_diversidade(titulo)
            produto_id = hashlib.md5(
                base.encode()
            ).hexdigest()

        familia = parse_familia_from_title(titulo)
        vendedor = identificar_vendedor(produto)
        marca = identificar_marca(titulo)
        titulo_normalizado = normalizar_texto(titulo)

        if nicho != "Moto":
            if base in BASES_VISTAS or base in assinaturas_ciclo:
                motivos["produto_semelhante"] += 1
                continue

            if VENDEDORES_NO_CICLO[vendedor] >= LIMITE_VENDEDOR:
                motivos["vendedor_repetido"] += 1
                continue

            if MARCAS_NO_CICLO[marca] >= LIMITE_MARCA:
                motivos["marca_repetida"] += 1
                continue

            if (
                familia != "outros"
                and familias_ciclo[familia] >= LIMITE_FAMILIA
            ):
                motivos["familia_limite"] += 1
                continue

        elif base in BASES_VISTAS:
            motivos["base_repetida"] += 1
            continue

        if link in usados_no_ciclo or link in ULTIMAS_BUSCAS_SHOPEE:
            motivos["link_repetido"] += 1
            continue

        if historico_bloqueia(produto_id):
            motivos["historico"] += 1
            continue

        if titulo_duplicado_forte(titulo):
            motivos["titulo"] += 1
            continue

        if any(
            SequenceMatcher(
                None,
                titulo_normalizado,
                titulo_anterior
            ).ratio() >= SIMILARIDADE_MAX
            for titulo_anterior in titulos_ciclo
        ):
            motivos["similaridade"] += 1
            continue

        if not validar_relevancia_nicho(
            nicho,
            titulo,
            termo=termo,
            modelo=termo if e_moto else None,
            peca=peca,
        ):
            motivos["relevancia"] += 1
            continue

        limite_familia = 2 if nicho == "Moto" else LIMITE_FAMILIA

        if (
            familia != "outros"
            and familias_ciclo[familia] >= limite_familia
        ):
            motivos["familia_limite"] += 1
            continue

        escolhidos.append(produto)
        titulos_ciclo.append(titulo_normalizado)
        assinaturas_ciclo.add(base)
        familias_ciclo[familia] += 1

        BASES_VISTAS.add(base)
        usados_no_ciclo.add(link)
        ULTIMAS_BUSCAS_SHOPEE.append(link)
        ULTIMOS_TITULOS.append(titulo_normalizado)

        if nicho != "Moto":
            VENDEDORES_NO_CICLO[vendedor] += 1
            MARCAS_NO_CICLO[marca] += 1

    del ULTIMAS_BUSCAS_SHOPEE[:-300]
    del ULTIMOS_TITULOS[:-150]

    if motivos:
        logging.info(
            f"{nicho}: rejeições {dict(motivos)}"
        )

    return escolhidos, estado

def get_shopee_offers():
    global usados_no_ciclo, BASES_VISTAS
    global VENDEDORES_NO_CICLO, MARCAS_NO_CICLO

    usados_no_ciclo = set()
    BASES_VISTAS = set()
    VENDEDORES_NO_CICLO = Counter()
    MARCAS_NO_CICLO = Counter()

    estado = carregar_estado()
    candidatos = []

    nichos = [
        "Moto",
        "Casa",
        "Maternidade",
        "Eletroeletrônicos",
        "Moda feminina",
        "Moda masculina",
    ]

    random.shuffle(nichos)

    cotas = {
        "Moto": 2,
        "Casa": 2,
        "Maternidade": 2,
        "Eletroeletrônicos": 2,
        "Moda feminina": 1,
        "Moda masculina": 1,
    }

    for nicho in nichos:
        try:
            if nicho == "Moto":
                combinacoes, estado = get_proximas_combinacoes_moto(
                    estado,
                    cotas[nicho]
                )

                for moto, peca in combinacoes:
                    ofertas, estado = selecionar_ofertas_termo(
                        nicho,
                        moto,
                        1,
                        estado,
                        e_moto=True,
                        peca=peca,
                    )

                    candidatos.extend(
                        (nicho, produto)
                        for produto in ofertas
                    )

            else:
                termo_info, estado = get_proximo_termo(
                    nicho,
                    estado
                )

                ofertas, estado = selecionar_ofertas_termo(
                    nicho,
                    termo_info[0],
                    cotas[nicho],
                    estado,
                )

                candidatos.extend(
                    (nicho, produto)
                    for produto in ofertas
                )

        except Exception as erro:
            logging.error(
                f"Erro no nicho {nicho}: {erro}",
                exc_info=True
            )

    salvar_estado(estado)

    candidatos.sort(
        key=lambda item: oferta_score(
            item[1],
            nicho=item[0]
        ),
        reverse=True
    )

    return candidatos[:MAX_OFERTAS]

CHAMADAS_ACAO = [
    "👇 CORRE QUE TÁ ACABANDO!",
    "⚡ CLIQUE ANTES QUE AUMENTE!",
    "🚀 ESTOQUE LIMITADO - AGORA!",
    "💥 MELHOR PREÇO DO ANO!",
    "🎯 COMPRE ANTES DOS OUTROS!",
    "🔥 VOOU DAS PRATELEIRAS!",
    "⏰ PROMOÇÃO ACABA HOJE!",
    "💰 ECONOMIA REAL - CORRE!",
    "⭐ OFERTA QUENTE AGORA!",
    "🛒 NÃO DEIXA ESCAPAR!",
]

def gerar_link_whatsapp(mensagem):
    texto = re.sub(r"<[^>]+>", "", mensagem)
    return f"https://wa.me/?text={quote(texto)}"

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, whatsapp=False):
    abertura = random.choice([
        "🚨 Isso aqui não é comum aparecer assim",
        "👀 Achei isso aqui e fui conferir…",
        "🔥 Isso aqui tá com cara de oportunidade",
        "💥 Esse aqui tá chamando atenção de quem compra",
        "⚠️ Isso aqui pode desaparecer rápido",
    ])

    gatilho = random.choice([
        "Preço muito abaixo do que costuma aparecer",
        "Avaliações acima da média",
        "Volume de vendas alto",
        "Custo-benefício forte",
        "Tá vendendo bem",
    ])

    acao = random.choice(CHAMADAS_ACAO)

    if whatsapp:
        return f"""
{abertura}

*🔥 {nome}*

{gatilho}

{acao}

*💰 R$ {preco}*
*⭐ {avaliacao} | 🛒 {vendas} vendas*

⚠️ Pode subir de preço

🛒 COMPRAR AGORA: {link}

📢 Grupo:
{LINK_GRUPO_OFERTAS}
"""

    return f"""
{abertura}

🔥 <b>{nome}</b>

{gatilho}

{acao}

💰 <b>R$ {preco}</b>
⭐ <b>{avaliacao} | {vendas} vendas</b>
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>

<a href="{LINK_GRUPO_OFERTAS}">
📲 Entrar no grupo de ofertas
</a>
"""

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not dentro_do_horario():
            logging.info("Fora do horário permitido")
            return

        ofertas = get_shopee_offers()

        if len(ofertas) < MIN_OFERTAS:
            logging.warning(
                f"Apenas {len(ofertas)} ofertas válidas"
            )
            return

        selecionadas = []

        for nicho, item in ofertas:
            try:
                link_base = (
                    item.get("offerLink")
                    or item.get("productLink")
                )

                if not link_base:
                    continue

                link = aplicar_id_afiliado(link_base)
                link_html = html.escape(link, quote=True)

                nome = html.escape(
                    str(item.get("productName", "")),
                    quote=False
                )

                preco = float(
                    item.get("priceMin", 0) or 0
                )

                imagem = item.get("imageUrl")
                avaliacao = float(
                    item.get("ratingStar", 4.5) or 4.5
                )

                vendas = int(
                    item.get("sales", 100) or 100
                )

                comissao = round(
                    float(
                        item.get("commissionRate", 0) or 0
                    ) * 100,
                    2
                )

                vendas_texto = f"{vendas:,}".replace(",", ".")
                preco_texto = f"{preco:.2f}".replace(".", ",")

                mensagem = gerar_copy(
                    nome,
                    preco_texto,
                    vendas_texto,
                    avaliacao,
                    comissao,
                    link_html,
                )

                mensagem_zap = gerar_copy(
                    nome,
                    preco_texto,
                    vendas_texto,
                    avaliacao,
                    0,
                    link,
                    whatsapp=True,
                )

                link_zap = html.escape(
                    gerar_link_whatsapp(mensagem_zap),
                    quote=True
                )

                mensagem += (
                    f'\n📲 <a href="{link_zap}">'
                    "Compartilhar no WhatsApp</a>"
                    "\n━━━━━━━━━━━━━━━"
                    "\n📢 <b>Ofertas Secretas</b>"
                )

                if nicho == "Moto":
                    identificacao = (
                        f"{chave_base_titulo(item.get('productName', ''))}"
                        f"|{link_base}"
                    )
                else:
                    identificacao = assinatura_diversidade(
                        item.get("productName", "")
                    )

                produto_id = hashlib.md5(
                    identificacao.encode()
                ).hexdigest()

                selecionadas.append({
                    "msg": mensagem,
                    "img": imagem,
                    "produto_id": produto_id,
                    "nicho": nicho,
                })

            except Exception as erro:
                logging.error(
                    f"Erro preparando produto: {erro}",
                    exc_info=True
                )

        if not selecionadas:
            return

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 <b>OFERTAS NOVAS CHEGANDO...</b>",
            parse_mode="HTML",
        )

        await asyncio.sleep(5)

        for item in selecionadas:
            try:
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=item["msg"],
                    parse_mode="HTML",
                )

                registrar_historico(
                    item["produto_id"]
                )

                await asyncio.sleep(40)

            except Exception as erro:
                logging.error(
                    f"Erro enviando VIP: {erro}",
                    exc_info=True
                )

        estado = carregar_estado()
        indice = estado.get("free_nicho_idx", 0)
        nicho_free = NICHOS_FREE_ROTA[
            indice % len(NICHOS_FREE_ROTA)
        ]

        oferta_free = next(
            (
                item for item in selecionadas
                if item["nicho"] == nicho_free
            ),
            None,
        )

        if oferta_free:
            try:
                await context.bot.send_photo(
                    chat_id=FREE_CHAT_ID,
                    photo=oferta_free["img"],
                    caption=oferta_free["msg"],
                    parse_mode="HTML",
                )

                registrar_historico(
                    oferta_free["produto_id"]
                )

            except Exception as erro:
                logging.error(
                    f"Erro enviando FREE: {erro}",
                    exc_info=True
                )

        estado["free_nicho_idx"] = (
            indice + 1
        ) % len(NICHOS_FREE_ROTA)

        salvar_estado(estado)

    except Exception as erro:
        logging.error(
            f"ERRO CRITICO: {erro}",
            exc_info=True
        )

async def keep_alive():
    while True:
        logging.info("BOT VIVO")
        await asyncio.sleep(300)

async def post_init(application):
    application.job_queue.run_repeating(
        send_ofertas,
        interval=CHECK_INTERVAL,
        first=10,
    )

    asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTAVEL")

async def error_handler(update, context):
    logging.error(
        f"ERRO TELEGRAM: {context.error}",
        exc_info=True
    )

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN ausente")

    while True:
        try:
            app = (
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .build()
            )

            app.add_error_handler(error_handler)
            app.run_polling(allowed_updates=None)

        except Exception as erro:
            logging.error(
                f"BOT REINICIANDO: {erro}",
                exc_info=True
            )

            time.sleep(15)
 

