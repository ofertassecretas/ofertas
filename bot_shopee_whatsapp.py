import asyncio
import hashlib
import html
import json
import logging
import math
import os
import random
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, time as dt_time, timedelta
from difflib import SequenceMatcher
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

import requests
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO SHOPEE V22 - SELECAO INTELIGENTE")

# =========================================================
# CONFIGURACAO
# =========================================================
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
CHAT_ID_DESTINO = -1003848415150
FREE_CHAT_ID = -1003886228244
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400                 # 1h30
MAX_OFERTAS = 10
MIN_OFERTAS = 4
HORARIO_INICIO = dt_time(5, 30)
HORARIO_FIM = dt_time(21, 30)

# Filtros minimos: devem proteger qualidade sem estrangular o pool.
HISTORICO_DIAS = 5
SIMILARIDADE_MAX = 0.90
VENDAS_MIN = 2
RATING_MIN = 4.0
PRECO_MIN = 15.0
PRECO_MAX = 10000.0
COMISSAO_MIN = 0.03

# Limites agora sao usados como penalizacao, nao como bloqueio precoce.
LIMITE_VENDEDOR_PENALIDADE = 1
LIMITE_MARCA_PENALIDADE = 1
LIMITE_FAMILIA_PENALIDADE = 1

# Quantas buscas tentamos por nicho em cada ciclo.
BUSCAS_POR_NICHO = {
    "Moto": 4,
    "Casa": 4,
    "Maternidade": 4,
    "Eletroeletronicos": 5,
    "Moda feminina": 3,
    "Moda masculina": 3,
}

# Meta de distribuicao. Nao e uma cota rigida.
META_NICHO = {
    "Moto": 2,
    "Casa": 2,
    "Maternidade": 1,
    "Eletroeletronicos": 2,
    "Moda feminina": 1,
    "Moda masculina": 1,
}

# Termos estrategicos recebem maior prioridade de exploracao.
TERMOS_ESTRATEGICOS = {
    "Eletroeletronicos": [
        "smart tv", "televisao", "celular", "smartphone", "notebook", "tablet",
        "iphone", "smartwatch", "fone bluetooth", "caixa de som bluetooth",
        "video game", "impressora termica", "camera de seguranca", "ssd",
    ],
    "Casa": [
        "air fryer", "fritadeira eletrica", "aspirador vertical", "aspirador robo",
        "cafeteira", "liquidificador", "ventilador", "ar condicionado", "mop",
    ],
    "Maternidade": [
        "carrinho bebe", "berco bebe", "fralda descartavel", "baba eletronica",
        "kit bolsa maternidade", "kit enxoval bebe", "canguru bebe",
    ],
    "Moda feminina": [
        "vestido feminino", "conjunto feminino", "tenis feminino", "bolsa feminina",
        "calca jeans", "roupa academia", "blazer feminino",
    ],
    "Moda masculina": [
        "camiseta masculina", "bermuda masculina", "camisa polo", "tenis masculino",
        "calca jeans masculina", "moletom masculino", "camisa social masculina",
    ],
    "Moto": [
        "kit relacao", "kit embreagem", "bateria", "estator", "pastilha freio",
        "vela iridium", "amortecedor", "kit pisca seta", "capacete", "pneu",
    ],
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")
ESTADO_FILE = "estado_buscas.json"
HISTORICO_FILE = "historico_envios.json"

# Estado em memoria do ciclo.
usados_no_ciclo = set()
BASES_VISTAS = set()
ULTIMAS_BUSCAS_SHOPEE = []
ULTIMOS_TITULOS = []
VENDEDORES_NO_CICLO = Counter()
MARCAS_NO_CICLO = Counter()
FAMILIAS_NO_CICLO = Counter()

# =========================================================
# CATALOGOS
# =========================================================
def lista(texto):
    return [x.strip() for x in texto.split("|") if x.strip()]

MOTOS = lista(
    "titan 150|cb 300|factor 150|titan 160|tornado|fazer 150|titan 125|"
    "bros 160|twister 250|biz 125|pop 110|xre 300|crosser 150|xre 190|"
    "fazer 250|lander 250|bros 150|tenere 250|biz 100|twister 300"
)

PECAS_MOTO = lista(
    "kit relacao|kit embreagem|bateria|refil bomba combustivel|chicote fiacao principal|"
    "bucha balanca|burrinho de freio|estribo|pedal de marcha|pedal de freio|"
    "rolamento virabrequim|estator|chave ignicao|punho chave luz|kit pisca seta|"
    "par pneu|bloco optico|retentor de bengala|bucha amortecedor|carburador corpo de injecao|"
    "kit cilindro|jogo de juntas|biela|valvulas escape admissao|disco de freio|"
    "tubo interno|vela iridium|pastilha freio|guidao|manopla|amortecedor|retrovisor|"
    "farol|lona de freio|cabo embreagem|cabo acelerador|coroa moto|pinhao moto|"
    "corrente moto|pedaleira|carenagem|lanterna traseira|capacete|pneu"
)

PRODUTOS_NICHO = {
    "Casa": lista(
        "air fryer|fritadeira eletrica|aspirador vertical|aspirador robo|liquidificador|"
        "cafeteira|cafeteira eletrica|cafeteira dolce gusto|cafeteira nespresso|panela eletrica|"
        "panela de pressao|jogo de panelas|mop|ventilador|batedeira|umidificador|ar condicionado|"
        "filtro de barro|tapete sala|tapete antiderrapante|torneira cozinha|caixa organizadora|"
        "sapateira|guarda roupas|cama casal|lencol|cobre leito|cortina|luminaria|pipoqueira|"
        "escorredor de louca|mangueira jardim|rede de dormir"
    ),
    "Maternidade": lista(
        "carrinho bebe|berco bebe|fralda descartavel|naninha|kit bolsa maternidade|kit mamadeira|"
        "baba eletronica|ninho bebe|kit enxoval bebe|babador bebe|mordedor bebe|tapete infantil|"
        "cadeirinha bebe|almofada amamentacao|termometro infantil|banheira bebe|mosqueteiro|"
        "canguru bebe|toalha infantil|fralda de pano|coberdrom bebe|bebe reborn|kit bicos"
    ),
    "Eletroeletronicos": lista(
        "smartwatch|relogio inteligente|fone bluetooth|headset gamer|caixa de som bluetooth|"
        "soundbar|celular|smartphone|smart tv|televisao|video game|fone sem fio|webcam|pen drive|"
        "impressora termica|notebook|tablet|ssd|mouse gamer|teclado mecanico|power bank|"
        "carregador turbo|suporte celular carro|camera de seguranca|gopro|drone|"
        "aparelho medidor de pressao|balanca digital|massageador|massageador portatil"
    ),
    "Moda feminina": lista(
        "vestido feminino|conjunto feminino|biquini|saida de praia|roupa academia|calca jeans|"
        "calca legging|saia longa|vestido midi|jaqueta feminina|casaco feminino|conjunto alfaiataria|"
        "short feminino|macacao feminino|tenis feminino|bolsa feminina|blazer feminino|saia jeans|"
        "top feminino|body feminino|pijama feminino|blusa regata|oculos de sol|kit sutia"
    ),
    "Moda masculina": lista(
        "camiseta masculina|bermuda masculina|camisa polo|camisa de linho|camisa social masculina|"
        "moletom masculino|jaqueta masculina|tenis masculino|carteira masculina|kit cueca|"
        "calca jeans masculina|camisa termica|sapatenis masculino|camisa tshirt|kit meias|"
        "barbeador|chuteiras|calcao de futebol|oculos de sol"
    ),
}

FAMILIAS_EXTRA = {
    "air_fryer": lista("air fryer|airfryer|fritadeira|fritadeira eletrica"),
    "eletro_cozinha": lista("cafeteira|liquidificador|batedeira|panela eletrica|pipoqueira|mop"),
    "aspiradores": lista("aspirador|aspirador vertical|aspirador robo"),
    "fone_bluetooth": lista("fone bluetooth|fone sem fio|fones de ouvido|headset|earbud"),
    "smartwatch": lista("smartwatch|relogio inteligente|relogio inteligente|watch"),
    "caixa_som": lista("caixa de som|speaker|soundbar"),
    "smart_tv": lista("smart tv|televisao|tv"),
    "notebook": lista("notebook|notbook|laptop"),
    "tablet": lista("tablet|ipad|galaxy tab|xiaomi pad"),
    "celular": lista("celular|smartphone|telefone|iphone|android"),
    "maternidade_bebe": lista("bebe|bebe|fralda|carrinho|berco|mamadeira|ninho|baba|baba"),
    "moda_fem": lista("vestido|conjunto|saia|bolsa|sandalia|tenis feminino|body|pijama"),
    "moda_masc": lista("camisa|camiseta|calca|tenis masculino|jaqueta|bermuda|sapatenis"),
    "casa_lar": lista("tapete|lencol|cortina|organizador|caixa organizadora|luminaria|pipoqueira|air fryer"),
    "moto_geral": lista("capacete|vela|pastilha|lona|kit relacao|corrente|coroa|pinhao|guidao|retrovisor|farol|lanterna"),
}

NICHOS = list(PRODUTOS_NICHO.keys()) + ["Moto"]
NICHOS_FREE_ROTA = ["Moto", "Casa", "Moda feminina", "Moda masculina", "Maternidade", "Eletroeletronicos"]

# =========================================================
# ESTADO / HISTORICO
# =========================================================
def carregar_estado():
    try:
        if os.path.exists(ESTADO_FILE):
            with open(ESTADO_FILE, "r", encoding="utf-8") as f:
                estado = json.load(f)
        else:
            estado = {}
    except Exception as e:
        logging.warning(f"Erro lendo estado: {e}")
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
        if not estado[nicho]["produtos_ordem"] or len(estado[nicho]["produtos_ordem"]) != len(produtos):
            estado[nicho]["produtos_ordem"] = list(range(len(produtos)))
            random.shuffle(estado[nicho]["produtos_ordem"])

    estado.setdefault("free_nicho_idx", 0)
    estado.setdefault("ciclos", 0)
    return estado


def salvar_estado(estado):
    try:
        tmp = ESTADO_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ESTADO_FILE)
    except Exception as e:
        logging.error(f"Erro salvando estado: {e}")


def carregar_historico():
    try:
        if os.path.exists(HISTORICO_FILE):
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"Erro lendo historico: {e}")
    return {}


def salvar_historico(historico):
    try:
        tmp = HISTORICO_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False, indent=2)
        os.replace(tmp, HISTORICO_FILE)
    except Exception as e:
        logging.error(f"Erro salvando historico: {e}")


def historico_bloqueia(chave):
    historico = carregar_historico()
    valor = historico.get(chave)
    if not valor:
        return False
    try:
        data = datetime.fromisoformat(valor)
        if data.tzinfo is None:
            data = data.replace(tzinfo=FUSO_BR)
        return datetime.now(FUSO_BR) - data < timedelta(days=HISTORICO_DIAS)
    except Exception:
        return False


def registrar_historico(chave):
    historico = carregar_historico()
    historico[chave] = datetime.now(FUSO_BR).isoformat()
    salvar_historico(historico)

# =========================================================
# TEXTO / IDENTIDADE
# =========================================================
def normalizar_texto(texto):
    texto = str(texto or "").lower().strip()
    texto = re.sub(r"[^a-z0-9à-ÿ\s]", " ", texto)
    return re.sub(r"\s+", " ", texto)


def sem_acento(texto):
    mapa = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüç", "aaaaaeeeeiiiiooooouuuuc")
    return normalizar_texto(texto).translate(mapa)


def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return HORARIO_INICIO <= agora <= HORARIO_FIM


def chave_base_titulo(titulo):
    remover = set(lista(
        "premium|novo|nova|promocao|super|original|profissional|casual|masculino|feminino|infantil|adulto|"
        "unissex|kit|com|de|para|o|a|promo|oferta|modelo|versao|linha|envio|usado|branco|preto|azul|"
        "vermelho|rosa|verde|amarelo|tamanho|tamanhos|unico|gamer|led|usb|mini|max|pro|bivolt|completo"
    ))
    tokens = [x for x in sem_acento(titulo).split() if x not in remover and len(x) > 2]
    return " ".join(sorted(tokens)[:10])


def assinatura_diversidade(titulo):
    remover = set(lista(
        "novo|nova|original|premium|profissional|promocao|promo|oferta|modelo|versao|kit|com|para|de|da|do|"
        "e|branco|preto|azul|vermelho|rosa|verde|amarelo|cinza|roxo|marrom|tamanho|tamanhos|unico|unica|"
        "bivolt|110v|127v|220v|usb|led|mini|max|pro|completo|completa|unissex"
    ))
    tokens = []
    for token in sem_acento(titulo).split():
        token = re.sub(r"[^a-z0-9]", "", token)
        if not token or token in remover or len(token) <= 2:
            continue
        if re.fullmatch(r"\d+(gb|tb|mb|cm|mm|kg|g|w|v|a)?", token):
            continue
        tokens.append(token)
    return " ".join(sorted(set(tokens))[:12]) or sem_acento(titulo)


def chave_produto(produto, nicho):
    titulo = str(produto.get("productName", ""))
    link = str(produto.get("offerLink") or produto.get("productLink") or "")
    if nicho == "Moto":
        base = chave_base_titulo(titulo)
        return hashlib.md5(f"{base}|{link}".encode()).hexdigest()
    return hashlib.md5(assinatura_diversidade(titulo).encode()).hexdigest()


def tem_bloqueio(titulo):
    texto = sem_acento(titulo)
    bloqueios = [
        "teste", "amostra", "nao compre", "produto teste", "exemplo", "dummy",
        "vela led", "vela decorativa", "decorativa", "decoracao", "casamento",
        "festa", "replica", "generico", "display", "mostruario", "brinde",
    ]
    return any(x in texto for x in bloqueios)


def identificar_marca(titulo):
    marcas = lista(
        "samsung|motorola|xiaomi|poco|redmi|iphone|apple|philco|mondial|britania|electrolux|"
        "oster|philips|walita|lenovo|asus|dell|acer|haylou|amazfit|mibro|huawei|colcci|lovito|"
        "farm|lancome|lupo|adidas|nike|jbl|lg|consul|brastemp|arno|cadence|tcl|aoc|realme|"
        "infinix|multilaser|midea|suggar|wap|cofap|scud|ngk|heliar|yuasa|cobreq|riffel"
    )
    texto = sem_acento(titulo)
    return next((marca for marca in marcas if sem_acento(marca) in texto), "sem_marca")


def identificar_vendedor(produto):
    if produto.get("shopId"):
        return f"id:{produto['shopId']}"
    if produto.get("shopName"):
        return f"nome:{sem_acento(produto['shopName'])}"
    try:
        dominio = urlparse(str(produto.get("offerLink") or produto.get("productLink") or "")).netloc.lower()
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
        "generico|universal|mini|infantil|brinquedo|adesivo|capa|case|pelicula|display|mostruario|"
        "decorativo|replica|dummy|refil|kit reposicao|reposicao|peca de reposicao|manual"
    )
    return -5 if any(x in sem_acento(nome) for x in termos) else 0

# =========================================================
# RELEVANCIA / FAMILIA
# =========================================================
def parse_familia_from_title(titulo):
    texto = sem_acento(titulo)
    for familia, termos in FAMILIAS_EXTRA.items():
        if any(sem_acento(x) in texto for x in termos):
            return familia
    return "outros"


def validar_modelo_titulo(titulo, termo):
    texto = sem_acento(titulo)
    palavras = [x for x in sem_acento(termo).split() if len(x) > 2]
    if not palavras:
        return True
    encontrados = sum(x in texto for x in palavras)
    return encontrados >= max(1, min(2, len(palavras)))


def validar_relevancia_nicho(nicho, titulo, termo=None, modelo=None, peca=None):
    texto = sem_acento(titulo)

    if nicho == "Eletroeletronicos":
        if any(x in texto for x in ["capa", "pelicula", "case"]):
            if not any(x in texto for x in ["celular", "tablet", "smartphone", "iphone"]):
                return False
        if any(x in texto for x in ["smart tv", "televisao"]):
            if any(x in texto for x in ["mouse", "teclado", "ssd", "notebook"]):
                return False

    if nicho == "Casa" and any(x in texto for x in ["tinta", "tintas"]):
        if not any(x in texto for x in ["parede", "spray", "esmalte"]):
            return False

    if nicho == "Moda feminina" and any(x in texto for x in ["masculino", "homem", "masc"]):
        return False

    if nicho == "Moda masculina" and any(x in texto for x in ["feminino", "mulher", "menina"]):
        return False

    if nicho == "Maternidade":
        proibidos = ["organizador", "cozinha", "banheiro", "carro"]
        permitidos = ["bebe", "infantil", "maternidade", "fralda", "carrinho", "mamadeira", "ninho"]
        if any(x in texto for x in proibidos) and not any(x in texto for x in permitidos):
            return False

    if nicho == "Moto":
        if modelo and not validar_modelo_titulo(titulo, modelo):
            return False
        if peca and not validar_modelo_titulo(titulo, peca):
            return False
        if termo and not validar_modelo_titulo(titulo, termo):
            return False

    return True

# =========================================================
# SCORE COMERCIAL
# =========================================================
PONTOS_MARCAS = {
    "apple": 12, "iphone": 12, "samsung": 10, "motorola": 9, "xiaomi": 8, "poco": 8,
    "philips": 8, "electrolux": 8, "mondial": 6, "philco": 6, "britania": 6, "oster": 6,
    "jbl": 7, "nike": 7, "adidas": 7, "tcl": 8, "aoc": 7, "lg": 9, "lenovo": 8,
    "asus": 8, "dell": 9, "acer": 7, "midea": 7, "wap": 6,
}

TERMOS_ESTRELA = {
    "smart tv", "televisao", "celular", "smartphone", "notebook", "iphone", "tablet",
    "air fryer", "fritadeira eletrica", "aspirador vertical", "cafeteira", "smartwatch",
    "fone bluetooth", "kit relacao", "kit embreagem", "bateria", "carrinho bebe",
    "fralda descartavel", "vestido feminino", "tenis feminino", "tenis masculino",
}


def valor_comissao(preco, comissao):
    return max(0.0, preco * comissao)


def oferta_score(produto, termo="", nicho=None):
    try:
        vendas = int(produto.get("sales", 0) or 0)
        avaliacao = float(produto.get("ratingStar", 0) or 0)
        comissao = float(produto.get("commissionRate", 0) or 0)
        preco = float(produto.get("priceMin", 0) or 0)
        preco_max = float(produto.get("priceMax", 0) or 0)
        nome = sem_acento(produto.get("productName", ""))
        termo_n = sem_acento(termo)

        # Base de demanda: log evita que 100 mil vendas esmaguem todo o resto.
        score = math.log10(vendas + 1) * 8.0
        score += avaliacao * 3.2
        score += shop_type_score(produto.get("shopType", []))
        score += PONTOS_MARCAS.get(identificar_marca(nome), 0)
        score += penalidade_termo_fraco(nome)

        # Comissao importa, mas nao pode dominar vendas/qualidade.
        score += min(comissao * 100, 18)

        # Potencial de comissao em reais.
        comissao_r = valor_comissao(preco, comissao)
        if comissao_r >= 100:
            score += 7
        elif comissao_r >= 50:
            score += 5
        elif comissao_r >= 20:
            score += 3
        elif comissao_r >= 10:
            score += 1

        # Preco razoavel para compra por impulso / oportunidade.
        if 40 <= preco <= 3000:
            score += 5
        elif 3000 < preco <= 7000:
            score += 2
        elif preco < 25:
            score -= 2

        # Desconto aparente. So usa quando priceMax parece referencia valida.
        if preco_max > preco > 0:
            desconto = (preco_max - preco) / preco_max
            if desconto >= 0.60:
                score += 10
            elif desconto >= 0.40:
                score += 7
            elif desconto >= 0.25:
                score += 4
            elif desconto < 0.05:
                score -= 2

        # Relevancia do termo.
        if termo_n and termo_n in nome:
            score += 8
        elif termo_n and any(x in nome for x in termo_n.split() if len(x) > 2):
            score += 3

        # Produto estrategico.
        if any(t in nome for t in TERMOS_ESTRELA):
            score += 5

        # Qualidade.
        if avaliacao >= 4.7:
            score += 3
        if vendas >= 1000:
            score += 2
        if vendas >= 10000:
            score += 2
        if comissao >= 0.08:
            score += 2

        palavras = len(nome.split())
        if 3 <= palavras <= 14:
            score += 2
        elif palavras > 22:
            score -= 4

        # Acessorios muito pequenos perdem prioridade, mas nao sao automaticamente mortos.
        if any(x in nome for x in ["pelicula", "manual", "adesivo", "display", "refil"]):
            score -= 6

        return round(score, 3)
    except Exception:
        return 0.0

# =========================================================
# API SHOPEE
# =========================================================
def buscar_produtos_da_categoria_kw(palavra_chave, categoria):
    logging.info(f"Buscando em {categoria}: {palavra_chave}")
    timestamp = int(time.time())
    palavra_chave = str(palavra_chave).replace('"', " ").strip()

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
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}",
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

    return dados.get("data", {}).get("productOfferV2", {}).get("nodes", []) or []

# =========================================================
# VALIDACAO BASICA
# =========================================================
def motivo_rejeicao(produto):
    try:
        titulo = str(produto.get("productName", "")).strip()
        link = str(produto.get("offerLink") or produto.get("productLink") or "").strip()
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
        if link in usados_no_ciclo:
            return "link_repetido"
        return None
    except Exception as e:
        return f"erro_validacao:{type(e).__name__}"

# =========================================================
# MEMORIA E PENALIZACOES
# =========================================================
def penalidade_diversidade(produto, nicho, familia, vendedor, marca, titulo, bases_candidatas):
    penal = 0.0

    # Repeticao no ciclo: penaliza progressivamente.
    if marca != "sem_marca":
        penal += max(0, MARCAS_NO_CICLO[marca] - LIMITE_MARCA_PENALIDADE) * 5
    penal += max(0, VENDEDORES_NO_CICLO[vendedor] - LIMITE_VENDEDOR_PENALIDADE) * 4
    penal += max(0, FAMILIAS_NO_CICLO[familia] - LIMITE_FAMILIA_PENALIDADE) * 7

    # Similaridade com o que ja foi escolhido no ciclo.
    titulo_n = sem_acento(titulo)
    for anterior in list(ULTIMOS_TITULOS)[-30:]:
        ratio = SequenceMatcher(None, titulo_n, anterior).ratio()
        if ratio >= SIMILARIDADE_MAX:
            penal += 16
            break
        if ratio >= 0.82:
            penal += 5

    # Base ja vista em memoria recente: nao bloqueia automaticamente, mas pesa.
    base = assinatura_diversidade(titulo) if nicho != "Moto" else chave_base_titulo(titulo)
    if base in BASES_VISTAS:
        penal += 12

    # Produto que acabou de ser buscado e nao foi enviado: pequena penalidade.
    link = str(produto.get("offerLink") or produto.get("productLink") or "")
    if link in ULTIMAS_BUSCAS_SHOPEE:
        penal += 2

    return penal


def oferta_e_estrela(produto, nicho, termo):
    nome = sem_acento(produto.get("productName", ""))
    vendas = int(produto.get("sales", 0) or 0)
    rating = float(produto.get("ratingStar", 0) or 0)
    comissao = float(produto.get("commissionRate", 0) or 0)
    preco = float(produto.get("priceMin", 0) or 0)
    score = oferta_score(produto, termo, nicho)
    comissao_r = valor_comissao(preco, comissao)

    return (
        score >= 80
        and rating >= 4.6
        and vendas >= 500
        and (comissao >= 0.05 or comissao_r >= 30)
    ) or (
        any(t in nome for t in TERMOS_ESTRELA)
        and score >= 78
        and vendas >= 1000
    )

# =========================================================
# BUSCA E POOL DE CANDIDATOS
# =========================================================
def get_proximo_termo(nicho, estado):
    produtos = PRODUTOS_NICHO[nicho]
    ordem = estado[nicho]["produtos_ordem"]
    indice = estado[nicho]["produto_idx"]
    posicao = ordem[indice % len(ordem)]
    estado[nicho]["produto_idx"] = (indice + 1) % len(ordem)
    if estado[nicho]["produto_idx"] == 0:
        random.shuffle(ordem)
    return produtos[posicao], estado


def escolher_termos_nicho(nicho, estado, quantidade):
    escolhidos = []
    estrategicos = list(dict.fromkeys(TERMOS_ESTRATEGICOS.get(nicho, [])))

    # A cada ciclo, garante exploracao de estrategicos sem abandonar a rotacao.
    if estrategicos:
        historico_idx = estado.setdefault("estrategicos_idx", {})
        idx = historico_idx.get(nicho, 0)
        janela = []
        for i in range(min(len(estrategicos), max(2, quantidade))):
            janela.append(estrategicos[(idx + i) % len(estrategicos)])
        historico_idx[nicho] = (idx + max(1, quantidade - 1)) % len(estrategicos)
        escolhidos.extend(janela)

    while len(escolhidos) < quantidade:
        termo, estado = get_proximo_termo(nicho, estado)
        if termo not in escolhidos:
            escolhidos.append(termo)

    return escolhidos[:quantidade], estado


def get_proximas_combinacoes_moto(estado, quantidade=4):
    dados = estado["Moto"]
    peca_idx = dados["peca_idx"]
    moto_idx = dados["moto_idx"]
    resultado = []

    # Faz um pequeno salto para evitar repetir sempre o mesmo modelo.
    for _ in range(quantidade):
        resultado.append((MOTOS[moto_idx], PECAS_MOTO[peca_idx]))
        moto_idx = (moto_idx + 1) % len(MOTOS)
        if moto_idx == 0:
            peca_idx = (peca_idx + 1) % len(PECAS_MOTO)

    dados["peca_idx"] = peca_idx
    dados["moto_idx"] = moto_idx
    return resultado, estado


def coletar_pool_nicho(nicho, estado):
    resultados = []
    motivos = Counter()
    buscas = []

    if nicho == "Moto":
        combinacoes, estado = get_proximas_combinacoes_moto(estado, BUSCAS_POR_NICHO["Moto"])
        buscas = [(f"{peca} {modelo}", modelo, peca) for modelo, peca in combinacoes]
    else:
        termos, estado = escolher_termos_nicho(nicho, estado, BUSCAS_POR_NICHO[nicho])
        buscas = [(termo, None, None) for termo in termos]

    for termo_busca, modelo, peca in buscas:
        try:
            brutos = buscar_produtos_da_categoria_kw(termo_busca, nicho)
            logging.info(f"{nicho}: {termo_busca} -> {len(brutos)} brutos")
            for produto in brutos:
                motivo = motivo_rejeicao(produto)
                if motivo:
                    motivos[motivo] += 1
                    continue
                titulo = str(produto.get("productName", "")).strip()
                if not validar_relevancia_nicho(nicho, titulo, termo=termo_busca, modelo=modelo, peca=peca):
                    motivos["relevancia"] += 1
                    continue

                produto = dict(produto)
                produto["_termo_busca"] = termo_busca
                produto["_score_base"] = oferta_score(produto, termo_busca, nicho)
                produto["_familia"] = parse_familia_from_title(titulo)
                produto["_marca"] = identificar_marca(titulo)
                produto["_vendedor"] = identificar_vendedor(produto)
                produto["_nicho"] = nicho
                resultados.append(produto)
        except Exception as e:
            logging.error(f"Erro buscando {nicho}/{termo_busca}: {e}", exc_info=True)
            motivos["erro_busca"] += 1

    # Remove duplicatas exatas antes da selecao.
    unicos = {}
    for produto in resultados:
        chave = chave_produto(produto, nicho)
        anterior = unicos.get(chave)
        if anterior is None or produto["_score_base"] > anterior["_score_base"]:
            unicos[chave] = produto
    resultados = list(unicos.values())

    logging.info(
        f"{nicho}: pool={len(resultados)} | buscas={len(buscas)} | rejeicoes={dict(motivos)}"
    )
    return resultados, estado, motivos

# =========================================================
# SELECAO DIVERSIFICADA
# =========================================================
def selecionar_do_pool(pool, nicho, quantidade, candidatos_global=None):
    if not pool or quantidade <= 0:
        return []

    selecionados = []
    restantes = list(pool)
    candidatos_global = candidatos_global or []

    # Ordena inicialmente por score, mas a cada rodada aplica penalidade de diversidade.
    while restantes and len(selecionados) < quantidade:
        ranking = []
        for produto in restantes:
            familia = produto["_familia"]
            marca = produto["_marca"]
            vendedor = produto["_vendedor"]
            titulo = produto.get("productName", "")
            base = assinatura_diversidade(titulo) if nicho != "Moto" else chave_base_titulo(titulo)

            penal = penalidade_diversidade(
                produto, nicho, familia, vendedor, marca, titulo, BASES_VISTAS
            )

            # Se ja temos outra oferta muito parecida dentro desta selecao local, penaliza forte.
            for item in selecionados:
                r = SequenceMatcher(None, sem_acento(titulo), sem_acento(item.get("productName", ""))).ratio()
                if r >= SIMILARIDADE_MAX:
                    penal += 20
                elif r >= 0.82:
                    penal += 7

            score = produto["_score_base"] - penal
            estrela = oferta_e_estrela(produto, nicho, produto.get("_termo_busca", ""))
            if estrela:
                score += 4

            ranking.append((score, produto, base))

        ranking.sort(key=lambda x: x[0], reverse=True)
        _, escolhido, base = ranking[0]

        # Evita repetir exatamente a mesma base, salvo produto estrela claramente superior.
        if base in {assinatura_diversidade(x.get("productName", "")) if nicho != "Moto" else chave_base_titulo(x.get("productName", "")) for x in selecionados}:
            if not oferta_e_estrela(escolhido, nicho, escolhido.get("_termo_busca", "")):
                restantes.remove(escolhido)
                continue

        selecionados.append(escolhido)
        restantes.remove(escolhido)
        usados_no_ciclo.add(str(escolhido.get("offerLink") or escolhido.get("productLink") or ""))
        BASES_VISTAS.add(base)
        ULTIMOS_TITULOS.append(sem_acento(escolhido.get("productName", "")))
        ULTIMAS_BUSCAS_SHOPEE.append(str(escolhido.get("offerLink") or escolhido.get("productLink") or ""))
        MARCAS_NO_CICLO[escolhido["_marca"]] += 1
        VENDEDORES_NO_CICLO[escolhido["_vendedor"]] += 1
        FAMILIAS_NO_CICLO[escolhido["_familia"]] += 1

    return selecionados


def selecionar_final_global(pools, max_ofertas=10):
    # Monta uma lista unica com todos os candidatos e escolhe por valor + diversidade.
    todos = []
    for nicho, pool in pools.items():
        for produto in pool:
            produto = dict(produto)
            produto["_nicho"] = nicho
            todos.append(produto)

    if not todos:
        return []

    # Remove produtos que ja estao no historico apenas se nao forem estrelas.
    candidatos = []
    for produto in todos:
        pid = chave_produto(produto, produto["_nicho"])
        estrela = oferta_e_estrela(produto, produto["_nicho"], produto.get("_termo_busca", ""))
        if historico_bloqueia(pid) and not estrela:
            continue
        candidatos.append(produto)

    selecionados = []
    usados_familia = Counter()
    usados_marca = Counter()
    usados_vendedor = Counter()
    usados_nicho = Counter()
    bases = set()

    for rodada in range(max_ofertas):
        if not candidatos:
            break

        ranking = []
        for produto in candidatos:
            nicho = produto["_nicho"]
            familia = produto["_familia"]
            marca = produto["_marca"]
            vendedor = produto["_vendedor"]
            titulo = produto.get("productName", "")
            base = assinatura_diversidade(titulo) if nicho != "Moto" else chave_base_titulo(titulo)
            score = produto["_score_base"]

            # Diversidade por nicho: respeita meta sem transformar em cota obrigatoria.
            meta = META_NICHO.get(nicho, 1)
            if usados_nicho[nicho] >= meta:
                score -= 10

            # Se um nicho ainda nao apareceu, ganha prioridade moderada.
            if usados_nicho[nicho] == 0:
                score += 5

            # Marca/familia/vendedor: penalizacao progressiva.
            if usados_marca[marca] >= 1 and marca != "sem_marca":
                score -= 4 * usados_marca[marca]
            if usados_familia[familia] >= 1 and familia != "outros":
                score -= 7 * usados_familia[familia]
            if usados_vendedor[vendedor] >= 1:
                score -= 4 * usados_vendedor[vendedor]

            if base in bases:
                score -= 18

            # Similaridade com selecionados.
            for item in selecionados:
                ratio = SequenceMatcher(
                    None,
                    sem_acento(titulo),
                    sem_acento(item.get("productName", "")),
                ).ratio()
                if ratio >= SIMILARIDADE_MAX:
                    score -= 25
                elif ratio >= 0.82:
                    score -= 8

            # Produto estrela pode furar parte das penalidades.
            if oferta_e_estrela(produto, nicho, produto.get("_termo_busca", "")):
                score += 8

            # Eletronicos estrategicos: garante presenca sem forcar qualquer produto ruim.
            if nicho == "Eletroeletronicos":
                nome = sem_acento(titulo)
                if any(t in nome for t in ["smart tv", "televisao", "celular", "smartphone", "notebook", "iphone"]):
                    score += 5

            ranking.append((score, produto, base))

        ranking.sort(key=lambda x: x[0], reverse=True)
        score_escolha, escolhido, base = ranking[0]

        # Se score ficou muito ruim, fazemos uma rodada de recuperacao depois.
        if score_escolha < 35 and len(selecionados) >= MIN_OFERTAS:
            break

        selecionados.append(escolhido)
        candidatos.remove(escolhido)
        usados_nicho[escolhido["_nicho"]] += 1
        usados_marca[escolhido["_marca"]] += 1
        usados_familia[escolhido["_familia"]] += 1
        usados_vendedor[escolhido["_vendedor"]] += 1
        bases.add(base)

    return selecionados

# =========================================================
# RECUPERACAO PARA COMPLETAR 10
# =========================================================
def recuperar_ofertas(pools, selecionados, estado):
    if len(selecionados) >= MAX_OFERTAS:
        return selecionados, estado

    logging.info(f"RECUPERACAO: faltam {MAX_OFERTAS - len(selecionados)} ofertas")

    # Faz novas buscas usando termos rotativos. Menos filtros de diversidade, mantendo filtros de qualidade.
    for nicho in random.sample(NICHOS, len(NICHOS)):
        if len(selecionados) >= MAX_OFERTAS:
            break

        if nicho == "Moto":
            combinacoes, estado = get_proximas_combinacoes_moto(estado, 2)
            buscas = [(f"{peca} {modelo}", modelo, peca) for modelo, peca in combinacoes]
        else:
            termos, estado = escolher_termos_nicho(nicho, estado, 2)
            buscas = [(t, None, None) for t in termos]

        for termo_busca, modelo, peca in buscas:
            if len(selecionados) >= MAX_OFERTAS:
                break
            try:
                brutos = buscar_produtos_da_categoria_kw(termo_busca, nicho)
                novos = []
                for produto in brutos:
                    if motivo_rejeicao(produto):
                        continue
                    titulo = str(produto.get("productName", "")).strip()
                    if not validar_relevancia_nicho(nicho, titulo, termo=termo_busca, modelo=modelo, peca=peca):
                        continue
                    produto = dict(produto)
                    produto["_termo_busca"] = termo_busca
                    produto["_score_base"] = oferta_score(produto, termo_busca, nicho)
                    produto["_familia"] = parse_familia_from_title(titulo)
                    produto["_marca"] = identificar_marca(titulo)
                    produto["_vendedor"] = identificar_vendedor(produto)
                    produto["_nicho"] = nicho
                    pid = chave_produto(produto, nicho)
                    if pid in {chave_produto(x, x["_nicho"]) for x in selecionados}:
                        continue
                    if historico_bloqueia(pid) and not oferta_e_estrela(produto, nicho, termo_busca):
                        continue
                    novos.append(produto)

                if novos:
                    # Escolhe um de cada busca de recuperacao e reavalia o conjunto.
                    novos.sort(key=lambda x: x["_score_base"], reverse=True)
                    escolhido = novos[0]
                    selecionados.append(escolhido)
                    usados_no_ciclo.add(str(escolhido.get("offerLink") or escolhido.get("productLink") or ""))
                    if len(selecionados) >= MAX_OFERTAS:
                        break
            except Exception as e:
                logging.error(f"Erro na recuperacao {nicho}/{termo_busca}: {e}", exc_info=True)

    return selecionados[:MAX_OFERTAS], estado

# =========================================================
# MOTOR PRINCIPAL
# =========================================================
def get_shopee_offers():
    global usados_no_ciclo, BASES_VISTAS
    global ULTIMAS_BUSCAS_SHOPEE, ULTIMOS_TITULOS
    global VENDEDORES_NO_CICLO, MARCAS_NO_CICLO, FAMILIAS_NO_CICLO

    usados_no_ciclo = set()
    BASES_VISTAS = set()
    VENDEDORES_NO_CICLO = Counter()
    MARCAS_NO_CICLO = Counter()
    FAMILIAS_NO_CICLO = Counter()

    # Limita memorias de processo para nao crescer indefinidamente.
    ULTIMAS_BUSCAS_SHOPEE = ULTIMAS_BUSCAS_SHOPEE[-300:]
    ULTIMOS_TITULOS = ULTIMOS_TITULOS[-150:]

    estado = carregar_estado()
    estado["ciclos"] = int(estado.get("ciclos", 0)) + 1
    pools = {}

    ordem_nichos = NICHOS[:]
    random.shuffle(ordem_nichos)

    logging.info("=" * 55)
    logging.info(f"INICIO CICLO V22 #{estado['ciclos']}")
    logging.info("=" * 55)

    for nicho in ordem_nichos:
        try:
            pool, estado, _ = coletar_pool_nicho(nicho, estado)
            pools[nicho] = pool
        except Exception as e:
            logging.error(f"Erro no pool de {nicho}: {e}", exc_info=True)
            pools[nicho] = []

    candidatos_total = sum(len(x) for x in pools.values())
    logging.info(f"POOL TOTAL: {candidatos_total} candidatos")

    selecionados = selecionar_final_global(pools, MAX_OFERTAS)

    if len(selecionados) < MAX_OFERTAS:
        selecionados, estado = recuperar_ofertas(pools, selecionados, estado)

    # Ultima ordenacao: score + diversidade ja aplicada.
    selecionados = selecionados[:MAX_OFERTAS]

    logging.info("=" * 55)
    logging.info(f"RESULTADO CICLO: {len(selecionados)}/{MAX_OFERTAS}")
    for i, item in enumerate(selecionados, 1):
        logging.info(
            f"{i:02d}. [{item.get('_nicho')}] {item.get('productName')} | "
            f"score={item.get('_score_base', 0):.1f} | "
            f"vendas={item.get('sales', 0)} | "
            f"comissao={float(item.get('commissionRate', 0) or 0) * 100:.1f}%"
        )
    logging.info("=" * 55)

    salvar_estado(estado)
    return [
        (item.get("_nicho", ""), item)
        for item in selecionados
    ]

# =========================================================
# COPY / LINKS
# =========================================================
CHAMADAS_ACAO = [
    "👇 CORRE QUE TÁ ACABANDO!", "⚡ CLIQUE ANTES QUE AUMENTE!", "🚀 ESTOQUE LIMITADO - AGORA!",
    "💥 MELHOR PREÇO DO ANO!", "🎯 COMPRE ANTES DOS OUTROS!", "🔥 VOOU DAS PRATELEIRAS!",
    "⏰ PROMOÇÃO ACABA HOJE!", "💰 ECONOMIA REAL - CORRE!", "⭐ OFERTA QUENTE AGORA!",
    "🛒 NÃO DEIXA ESCAPAR!",
]


def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))


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

<a href="{LINK_GRUPO_OFERTAS}">📲 Entrar no grupo de ofertas</a>
"""

# =========================================================
# ENVIO
# =========================================================
async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not dentro_do_horario():
            logging.info("Fora do horário permitido")
            return

        ofertas = get_shopee_offers()
        if len(ofertas) < MIN_OFERTAS:
            logging.warning(f"Apenas {len(ofertas)} ofertas válidas. Ciclo não enviado.")
            return

        selecionadas = []
        for nicho, item in ofertas:
            try:
                link_base = item.get("offerLink") or item.get("productLink")
                if not link_base:
                    continue

                link = aplicar_id_afiliado(link_base)
                link_html = html.escape(link, quote=True)
                nome = html.escape(str(item.get("productName", "")), quote=False)
                preco = float(item.get("priceMin", 0) or 0)
                imagem = item.get("imageUrl")
                avaliacao = float(item.get("ratingStar", 4.5) or 4.5)
                vendas = int(item.get("sales", 100) or 100)
                comissao = round(float(item.get("commissionRate", 0) or 0) * 100, 2)
                vendas_texto = f"{vendas:,}".replace(",", ".")
                preco_texto = f"{preco:.2f}".replace(".", ",")

                if not imagem:
                    logging.warning(f"Produto sem imagem: {nome}")
                    continue

                mensagem = gerar_copy(nome, preco_texto, vendas_texto, avaliacao, comissao, link_html)
                mensagem_zap = gerar_copy(nome, preco_texto, vendas_texto, avaliacao, 0, link, whatsapp=True)
                link_zap = html.escape(gerar_link_whatsapp(mensagem_zap), quote=True)
                mensagem += (
                    f'\n📲 <a href="{link_zap}">Compartilhar no WhatsApp</a>'
                    "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"
                )

                produto_id = chave_produto(item, nicho)
                selecionadas.append({
                    "msg": mensagem,
                    "img": imagem,
                    "produto_id": produto_id,
                    "nicho": nicho,
                })
            except Exception as e:
                logging.error(f"Erro preparando produto: {e}", exc_info=True)

        if len(selecionadas) < MIN_OFERTAS:
            logging.warning(f"Somente {len(selecionadas)} ofertas possuem imagem/dados para envio")
            return

        logging.info(f"ENVIANDO {len(selecionadas)} OFERTAS PARA VIP")

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 <b>OFERTAS NOVAS CHEGANDO...</b>",
            parse_mode="HTML",
        )
        await asyncio.sleep(5)

        enviadas = []
        for item in selecionadas:
            try:
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=item["msg"],
                    parse_mode="HTML",
                )
                registrar_historico(item["produto_id"])
                enviadas.append(item)
                await asyncio.sleep(40)
            except Exception as e:
                logging.error(f"Erro enviando VIP: {e}", exc_info=True)

        # FREE: pega uma oferta do nicho da rodada, sem retirar as demais do VIP.
        estado = carregar_estado()
        indice = int(estado.get("free_nicho_idx", 0))
        nicho_free = NICHOS_FREE_ROTA[indice % len(NICHOS_FREE_ROTA)]
        oferta_free = next((x for x in enviadas if x["nicho"] == nicho_free), None)

        # Se o nicho alvo nao estiver no ciclo, usa a primeira oferta ainda nao enviada ao FREE.
        if not oferta_free and enviadas:
            oferta_free = enviadas[0]

        if oferta_free:
            try:
                await context.bot.send_photo(
                    chat_id=FREE_CHAT_ID,
                    photo=oferta_free["img"],
                    caption=oferta_free["msg"],
                    parse_mode="HTML",
                )
                registrar_historico(oferta_free["produto_id"])
            except Exception as e:
                logging.error(f"Erro enviando FREE: {e}", exc_info=True)

        estado["free_nicho_idx"] = (indice + 1) % len(NICHOS_FREE_ROTA)
        salvar_estado(estado)
        logging.info(f"CICLO FINALIZADO: VIP={len(enviadas)} | FREE={'1' if oferta_free else '0'}")

    except Exception as e:
        logging.error(f"ERRO CRITICO: {e}", exc_info=True)

# =========================================================
# RUNTIME
# =========================================================
async def keep_alive():
    while True:
        logging.info("BOT VIVO")
        await asyncio.sleep(300)


async def post_init(application):
    application.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTAVEL - V22")
    logging.info(f"Intervalo: {CHECK_INTERVAL}s | Janela: {HORARIO_INICIO} - {HORARIO_FIM}")


async def error_handler(update, context):
    logging.error(f"ERRO TELEGRAM: {context.error}", exc_info=True)


if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN ausente")
    if not SHOPEE_PASSWORD:
        raise RuntimeError("SHOPEE_PASSWORD ausente")

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
            logging.error(f"BOT REINICIANDO: {erro}", exc_info=True)
            time.sleep(15)

 

