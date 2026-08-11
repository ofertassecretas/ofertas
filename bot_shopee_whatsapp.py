import asyncio, hashlib, html, json, logging, math, os, random, re, time
from collections import Counter
from datetime import datetime, time as dt_time, timedelta
from difflib import SequenceMatcher
from urllib.parse import parse_qs, quote, urlencode, urlparse, urlunparse
from zoneinfo import ZoneInfo

import requests
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO SHOPEE V24 - MOTOR RELEVANCIA + DIVERSIDADE + COMISSAO FLEXIVEL")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")
CHAT_ID_DESTINO = -1003848415150
FREE_CHAT_ID = -1003886228244
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"
CHECK_INTERVAL = 5400
MAX_OFERTAS = 10
MIN_OFERTAS = 4
HORARIO_INICIO = dt_time(5, 30)
HORARIO_FIM = dt_time(21, 30)

HISTORICO_DIAS = 7
SIMILARIDADE_MAX = 0.90
VENDAS_MIN = 2
RATING_MIN = 4.0
PRECO_MIN = 15.0
PRECO_MAX = 10000.0

Comissão NÃO bloqueio.

COMISSAO_MIN = 0.0

Penalidades de diversidade.

LIMITE_VENDEDOR_PENALIDADE = 1
LIMITE_MARCA_PENALIDADE = 1
LIMITE_FAMILIA_PENALIDADE = 1

BUSCAS_POR_NICHO = {
"Moto": 5, "Casa": 4, "Maternidade": 4,
"Eletroeletronicos": 5, "Moda feminina": 3, "Moda masculina": 3,
}

META_NICHO = {
"Moto": 2, "Casa": 2, "Maternidade": 2,
"Eletroeletronicos": 2, "Moda feminina": 1, "Moda masculina": 1,
}

TERMOS_ESTRATEGICOS = {
"Eletroeletronicos": [
"smart tv", "televisao", "celular", "smartphone", "notebook", "tablet",
"iphone", "smartwatch", "fone bluetooth", "caixa de som bluetooth",
"video game", "impressora termica", "camera de seguranca", "ssd"
],
"Casa": [
"air fryer", "fritadeira eletrica", "aspirador vertical", "aspirador robo",
"cafeteira", "liquidificador", "ventilador", "ar condicionado", "mop"
],
"Maternidade": [
"carrinho bebe", "berco bebe", "fralda descartavel", "baba eletronica",
"kit bolsa maternidade", "kit enxoval bebe", "canguru bebe"
],
"Moda feminina": [
"vestido feminino", "conjunto feminino", "tenis feminino", "bolsa feminina",
"calca jeans", "roupa academia", "blazer feminino"
],
"Moda masculina": [
"camiseta masculina", "bermuda masculina", "camisa polo", "tenis masculino",
"calca jeans masculina", "moletom masculino", "camisa social masculina"
],
"Moto": [
"kit relacao", "kit embreagem", "bateria", "estator", "pastilha freio",
"vela iridium", "amortecedor", "kit pisca seta", "capacete", "pneu"
],
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

FUSO_BR = ZoneInfo("America/Sao_Paulo")
ESTADO_FILE = "estado_buscas.json"
HISTORICO_FILE = "historico_envios.json"

usados_no_ciclo = set()
BASES_VISTAS = set()
ULTIMAS_BUSCAS_SHOPEE = []
ULTIMOS_TITULOS = []
VENDEDORES_NO_CICLO = Counter()
MARCAS_NO_CICLO = Counter()
FAMILIAS_NO_CICLO = Counter()

=========================================================
CATALOGOS
=========================================================

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
"smartwatch": lista("smartwatch|relogio inteligente|watch"),
"caixa_som": lista("caixa de som|speaker|soundbar"),
"smart_tv": lista("smart tv|televisao|tv"),
"notebook": lista("notebook|notbook|laptop"),
"tablet": lista("tablet|ipad|galaxy tab|xiaomi pad"),
"celular": lista("celular|smartphone|telefone|iphone|android"),
"maternidade_bebe": lista("bebe|fralda|carrinho|berco|mamadeira|ninho|baba"),
"moda_fem": lista("vestido|conjunto|saia|bolsa|sandalia|tenis feminino|body|pijama"),
"moda_masc": lista("camisa|camiseta|calca|tenis masculino|jaqueta|bermuda|sapatenis"),
"casa_lar": lista("tapete|lencol|cortina|organizador|caixa organizadora|luminaria|pipoqueira|air fryer"),
"moto_geral": lista("capacete|vela|pastilha|lona|kit relacao|corrente|coroa|pinhao|guidao|retrovisor|farol|lanterna"),
}

NICHOS = list(PRODUTOS_NICHO.keys()) + ["Moto"]
NICHOS_FREE_ROTA = ["Moto", "Casa", "Moda feminina", "Moda masculina", "Maternidade", "Eletroeletronicos"]

=========================================================
ALIASES DE MOTO
=========================================================

MOTO_ALIASES = {
"titan 150": ["titan 150", "cg 150", "cg titan 150", "titan"],
"titan 160": ["titan 160", "cg 160", "cg titan 160"],
"titan 125": ["titan 125", "cg 125", "cg titan 125"],
"bros 160": ["bros 160", "n bros 160", "nxr bros 160", "bros"],
"bros 150": ["bros 150", "nxr bros 150"],
"fazer 150": ["fazer 150", "ys fazer 150"],
"fazer 250": ["fazer 250", "ys 250 fazer"],
"factor 150": ["factor 150", "factor 150i", "yamaha factor"],
"cb 300": ["cb 300", "cb300", "cb 300f"],
"xre 300": ["xre 300", "xre300"],
"xre 190": ["xre 190", "xre190"],
"crosser 150": ["crosser 150", "crosser"],
"lander 250": ["lander 250", "xtz 250 lander"],
"tenere 250": ["tenere 250", "tenere 250"],
"twister 250": ["twister 250", "cbx 250", "cbx twister"],
"twister 300": ["twister 300", "cb 300 twister"],
"biz 125": ["biz 125", "honda biz 125"],
"biz 100": ["biz 100", "honda biz 100"],
"pop 110": ["pop 110", "pop 110i"],
"tornado": ["tornado", "xr 250 tornado"],
}

PECA_ALIASES = {
"kit relacao": ["kit relacao", "kit relação", "relacao", "relação", "transmissao", "transmissão"],
"kit embreagem": ["kit embreagem", "embreagem", "disco embreagem"],
"bateria": ["bateria", "bateria moto"],
"estator": ["estator", "bobina estator"],
"pastilha freio": ["pastilha freio", "pastilha de freio", "pastilhas freio"],
"vela iridium": ["vela iridium", "vela de iridium", "vela ignicao"],
"amortecedor": ["amortecedor", "amortecedor traseiro", "amortecedor dianteiro"],
"kit pisca seta": ["kit pisca", "pisca seta", "seta moto"],
"capacete": ["capacete", "capacete moto"],
"pneu": ["pneu", "pneu moto"],
"corrente moto": ["corrente moto", "corrente de moto"],
"coroa moto": ["coroa moto", "coroa"],
"pinhao moto": ["pinhao moto", "pinhão", "pinhao"],
"farol": ["farol", "farol moto"],
"retrovisor": ["retrovisor", "retrovisor moto"],
"manopla": ["manopla", "manopla moto"],
"guidao": ["guidao", "guidão", "guidão moto"],
}

=========================================================
ESTADO / HISTORICO
=========================================================

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

for nicho, produtos in PRODUTOS_NICHO.items():
    estado.setdefault(nicho, {})
    estado[nicho].setdefault("produto_idx", 0)
    estado[nicho].setdefault("produtos_ordem", [])
    if len(estado[nicho]["produtos_ordem"]) != len(produtos):
        estado[nicho]["produtos_ordem"] = list(range(len(produtos)))
        random.shuffle(estado[nicho]["produtos_ordem"])

estado.setdefault("estrategicos_idx", {})
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
valor = carregar_historico().get(chave)
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

=========================================================
TEXTO / IDENTIDADE
=========================================================

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

def chave_identidade_forte(produto, nicho):
titulo = sem_acento(produto.get("productName", ""))
link = str(produto.get("offerLink") or produto.get("productLink") or "")
shop = str(produto.get("shopId") or produto.get("shopName") or "")
base = chave_base_titulo(titulo) if nicho == "Moto" else assinatura_diversidade(titulo)
return hashlib.md5(f"{base}|{shop}|{link}".encode()).hexdigest()

def tem_bloqueio(titulo):
texto = sem_acento(titulo)
bloqueios = [
"teste", "amostra", "nao compre", "produto teste", "exemplo", "dummy",
"vela led", "vela decorativa", "decorativa", "decoracao", "casamento",
"festa", "replica", "generico", "display", "mostruario", "brinde"
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

=========================================================
MOTO - RELEVANCIA
=========================================================

def contem_algum(texto, termos):
texto = sem_acento(texto)
return any(sem_acento(t) in texto for t in termos)

def modelo_moto_encontrado(titulo, modelo):
modelo_n = sem_acento(modelo)
texto = sem_acento(titulo)
aliases = MOTO_ALIASES.get(modelo_n, [modelo_n])
return contem_algum(texto, aliases)

def peca_moto_encontrada(titulo, peca):
peca_n = sem_acento(peca)
aliases = PECA_ALIASES.get(peca_n, [peca_n])
return contem_algum(titulo, aliases)

def validar_moto(titulo, modelo, peca):
texto = sem_acento(titulo)
if any(x in texto for x in ["capacete infantil", "capacete brinquedo", "brinquedo moto"]):
return False

modelo_ok = modelo_moto_encontrado(titulo, modelo)
peca_ok = peca_moto_encontrada(titulo, peca)

# Regra principal: produto deve ser claramente peça para aquele modelo.
if modelo_ok and peca_ok:
    return True

# Alguns anúncios omitem o modelo exato, mas deixam Honda/Yamaha + peça.
fabricantes = {
    "honda": ["titan", "bros", "biz", "xre", "cb", "twister", "pop", "tornado"],
    "yamaha": ["fazer", "factor", "lander", "crosser", "tenere"],
}

fabricante_ok = any(
    fabricante in texto and any(modelo_base in texto for modelo_base in modelos)
    for fabricante, modelos in fabricantes.items()
)

# Permite alguns casos em que a busca encontrou a peça, mas o modelo
# está abreviado no título.
if peca_ok and fabricante_ok:
    return True

return False

=========================================================
RELEVANCIA GERAL
=========================================================

def validar_relevancia_nicho(nicho, titulo, termo=None, modelo=None, peca=None):
texto = sem_acento(titulo)

if nicho == "Moto":
    return validar_moto(titulo, modelo or "", peca or "")

if nicho == "Eletroeletronicos":
    if any(x in texto for x in ["capa", "pelicula", "case"]):
        if not any(x in texto for x in ["celular", "tablet", "smartphone", "iphone"]):
            return False
    if "smart tv" in texto or "televisao" in texto:
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

return True

=========================================================
FAMILIA
=========================================================

def parse_familia_from_title(titulo):
texto = sem_acento(titulo)
for familia, termos in FAMILIAS_EXTRA.items():
if any(sem_acento(x) in texto for x in termos):
return familia
return "outros"

=========================================================
SCORE
=========================================================

PONTOS_MARCAS = {
"apple": 12, "iphone": 12, "samsung": 10, "motorola": 9, "xiaomi": 8,
"poco": 8, "philips": 8, "electrolux": 8, "mondial": 6, "philco": 6,
"britania": 6, "oster": 6, "jbl": 7, "nike": 7, "adidas": 7, "tcl": 8,
"aoc": 7, "lg": 9, "lenovo": 8, "asus": 8, "dell": 9, "acer": 7,
"midea": 7, "wap": 6,
}

TERMOS_ESTRELA = {
"smart tv", "televisao", "celular", "smartphone", "notebook", "iphone",
"tablet", "air fryer", "fritadeira eletrica", "aspirador vertical",
"cafeteira", "smartwatch", "fone bluetooth", "kit relacao",
"kit embreagem", "bateria", "carrinho bebe", "fralda descartavel",
"vestido feminino", "tenis feminino", "tenis masculino",
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

    score = math.log10(vendas + 1) * 8
    score += avaliacao * 3.2
    score += shop_type_score(produto.get("shopType", []))
    score += PONTOS_MARCAS.get(identificar_marca(nome), 0)
    score += penalidade_termo_fraco(nome)

    # Comissão agora é propositalmente fraca.
    score += min(comissao * 20, 3)

    # Comissão em reais ajuda, mas não domina.
    comissao_r = valor_comissao(preco, comissao)
    if comissao_r >= 150:
        score += 3
    elif comissao_r >= 80:
        score += 2
    elif comissao_r >= 30:
        score += 1

    if 40 <= preco <= 3000:
        score += 5
    elif 3000 < preco <= 7000:
        score += 2
    elif preco < 25:
        score -= 2

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

    if termo_n and termo_n in nome:
        score += 8
    elif termo_n and any(x in nome for x in termo_n.split() if len(x) > 2):
        score += 3

    if any(t in nome for t in TERMOS_ESTRELA):
        score += 5

    if avaliacao >= 4.7:
        score += 3
    if vendas >= 1000:
        score += 2
    if vendas >= 10000:
        score += 2

    palavras = len(nome.split())
    if 3 <= palavras <= 14:
        score += 2
    elif palavras > 22:
        score -= 4

    if any(x in nome for x in ["pelicula", "manual", "adesivo", "display", "refil"]):
        score -= 6

    return round(score, 3)

except Exception:
    return 0.0

=========================================================
API SHOPEE
=========================================================

def buscar_produtos_da_categoria_kw(palavra_chave, categoria):
logging.info(f"BUSCA [{categoria}] -> {palavra_chave}")

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

=========================================================
VALIDACAO BASICA
=========================================================

def motivo_rejeicao(produto):
try:
titulo = str(produto.get("productName", "")).strip()
link = str(produto.get("offerLink") or produto.get("productLink") or "").strip()
preco = float(produto.get("priceMin", 0) or 0)
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
    if vendas < VENDAS_MIN:
        return "vendas_baixas"
    if avaliacao and avaliacao < RATING_MIN:
        return "rating_baixo"
    if link in usados_no_ciclo:
        return "link_repetido"

    return None

except Exception as e:
    return f"erro_validacao:{type(e).__name__}"

=========================================================
PREPARAR CANDIDATO
=========================================================

def preparar_produto(produto, nicho, termo_busca, modelo=None, peca=None):
titulo = str(produto.get("productName", "")).strip()

produto = dict(produto)
produto["_termo_busca"] = termo_busca
produto["_modelo_moto"] = modelo
produto["_peca_moto"] = peca
produto["_score_base"] = oferta_score(produto, termo_busca, nicho)
produto["_familia"] = parse_familia_from_title(titulo)
produto["_marca"] = identificar_marca(titulo)
produto["_vendedor"] = identificar_vendedor(produto)
produto["_nicho"] = nicho
return produto

=========================================================
TERMOS
=========================================================

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
historico_idx = estado["estrategicos_idx"].get(nicho, 0)

# Metade estratégico, metade catálogo rotativo.
qtd_estrategica = min(len(estrategicos), max(1, math.ceil(quantidade / 2)))

for i in range(qtd_estrategica):
    termo = estrategicos[(historico_idx + i) % len(estrategicos)]
    if termo not in escolhidos:
        escolhidos.append(termo)

estado["estrategicos_idx"][nicho] = (
    historico_idx + qtd_estrategica
) % max(1, len(estrategicos))

while len(escolhidos) < quantidade:
    termo, estado = get_proximo_termo(nicho, estado)
    if termo not in escolhidos:
        escolhidos.append(termo)

return escolhidos[:quantidade], estado

=========================================================
BUSCAS MOTO
=========================================================

def get_proximas_combinacoes_moto(estado, quantidade=5):
dados = estado["Moto"]
peca_idx = dados["peca_idx"]
moto_idx = dados["moto_idx"]
resultado = []

for i in range(quantidade):
    modelo = MOTOS[moto_idx]
    peca = PECAS_MOTO[peca_idx]

    # Primeiras buscas são combinadas.
    if i < 3:
        termo = f"{peca} {modelo}"
    elif i == 3:
        termo = peca
    else:
        termo = modelo

    resultado.append((termo, modelo, peca))

    moto_idx = (moto_idx + 1) % len(MOTOS)
    if moto_idx == 0:
        peca_idx = (peca_idx + 1) % len(PECAS_MOTO)

dados["peca_idx"] = peca_idx
dados["moto_idx"] = moto_idx
return resultado, estado

=========================================================
COLETA DE POOL
=========================================================

def coletar_pool_nicho(nicho, estado):
resultados = []
motivos = Counter()

if nicho == "Moto":
    buscas, estado = get_proximas_combinacoes_moto(
        estado, BUSCAS_POR_NICHO["Moto"]
    )
else:
    termos, estado = escolher_termos_nicho(
        nicho, estado, BUSCAS_POR_NICHO[nicho]
    )
    buscas = [(termo, None, None) for termo in termos]

for termo_busca, modelo, peca in buscas:
    try:
        brutos = buscar_produtos_da_categoria_kw(termo_busca, nicho)

        logging.info(
            f"{nicho}: {termo_busca} -> {len(brutos)} brutos"
        )

        for bruto in brutos:
            motivo = motivo_rejeicao(bruto)

            if motivo:
                motivos[motivo] += 1
                continue

            titulo = str(bruto.get("productName", "")).strip()

            if not validar_relevancia_nicho(
                nicho,
                titulo,
                termo=termo_busca,
                modelo=modelo,
                peca=peca,
            ):
                motivos["relevancia"] += 1
                continue

            produto = preparar_produto(
                bruto,
                nicho,
                termo_busca,
                modelo,
                peca,
            )

            resultados.append(produto)

    except Exception as e:
        logging.error(
            f"Erro buscando {nicho}/{termo_busca}: {e}",
            exc_info=True,
        )
        motivos["erro_busca"] += 1

unicos = {}

for produto in resultados:
    chave = chave_produto(produto, nicho)
    anterior = unicos.get(chave)

    if anterior is None or produto["_score_base"] > anterior["_score_base"]:
        unicos[chave] = produto

resultados = list(unicos.values())

logging.info(
    f"{nicho}: pool={len(resultados)} | buscas={len(buscas)} | "
    f"rejeicoes={dict(motivos)}"
)

if nicho == "Moto":
    logging.info(
        f"MOTO AUDITORIA | pool={len(resultados)} | "
        f"rejeicoes={dict(motivos)}"
    )

return resultados, estado, motivos

=========================================================
DIVERSIDADE
=========================================================

def penalidade_diversidade(produto, nicho, familia, vendedor, marca, titulo):
penal = 0.0

if marca != "sem_marca":
    penal += max(0, MARCAS_NO_CICLO[marca] - LIMITE_MARCA_PENALIDADE) * 4

penal += max(
    0,
    VENDEDORES_NO_CICLO[vendedor] - LIMITE_VENDEDOR_PENALIDADE
) * 3

penal += max(
    0,
    FAMILIAS_NO_CICLO[familia] - LIMITE_FAMILIA_PENALIDADE
) * 5

titulo_n = sem_acento(titulo)

for anterior in list(ULTIMOS_TITULOS)[-30:]:
    ratio = SequenceMatcher(None, titulo_n, anterior).ratio()

    if ratio >= SIMILARIDADE_MAX:
        penal += 14
        break

    if ratio >= 0.82:
        penal += 4

base = (
    chave_base_titulo(titulo)
    if nicho == "Moto"
    else assinatura_diversidade(titulo)
)

if base in BASES_VISTAS:
    penal += 10

link = str(
    produto.get("offerLink")
    or produto.get("productLink")
    or ""
)

if link in ULTIMAS_BUSCAS_SHOPEE:
    penal += 2

return penal


def oferta_e_estrela(produto, nicho, termo):
vendas = int(produto.get("sales", 0) or 0)
rating = float(produto.get("ratingStar", 0) or 0)
nome = sem_acento(produto.get("productName", ""))
score = oferta_score(produto, termo, nicho)

return (
    score >= 78
    and rating >= 4.6
    and vendas >= 500
) or (
    any(t in nome for t in TERMOS_ESTRELA)
    and score >= 75
    and vendas >= 1000
)

=========================================================
SELECAO LOCAL
=========================================================

def selecionar_do_pool(pool, nicho, quantidade):
if not pool or quantidade <= 0:
return []

selecionados = []
restantes = list(pool)

while restantes and len(selecionados) < quantidade:
    ranking = []

    for produto in restantes:
        titulo = produto.get("productName", "")
        familia = produto["_familia"]
        marca = produto["_marca"]
        vendedor = produto["_vendedor"]

        penal = penalidade_diversidade(
            produto,
            nicho,
            familia,
            vendedor,
            marca,
            titulo,
        )

        for item in selecionados:
            ratio = SequenceMatcher(
                None,
                sem_acento(titulo),
                sem_acento(item.get("productName", "")),
            ).ratio()

            if ratio >= SIMILARIDADE_MAX:
                penal += 20
            elif ratio >= 0.82:
                penal += 7

        score = produto["_score_base"] - penal

        if oferta_e_estrela(
            produto,
            nicho,
            produto.get("_termo_busca", ""),
        ):
            score += 4

        ranking.append((score, produto))

    ranking.sort(key=lambda x: x[0], reverse=True)
    _, escolhido = ranking[0]

    selecionados.append(escolhido)
    restantes.remove(escolhido)

    link = str(
        escolhido.get("offerLink")
        or escolhido.get("productLink")
        or ""
    )

    usados_no_ciclo.add(link)

    titulo = escolhido.get("productName", "")
    base = (
        chave_base_titulo(titulo)
        if nicho == "Moto"
        else assinatura_diversidade(titulo)
    )

    BASES_VISTAS.add(base)
    ULTIMOS_TITULOS.append(sem_acento(titulo))
    ULTIMAS_BUSCAS_SHOPEE.append(link)

    MARCAS_NO_CICLO[escolhido["_marca"]] += 1
    VENDEDORES_NO_CICLO[escolhido["_vendedor"]] += 1
    FAMILIAS_NO_CICLO[escolhido["_familia"]] += 1

return selecionados

=========================================================
SCORE FINAL
=========================================================

def score_selecao(produto, selecionados, usados_familia, usados_marca, usados_vendedor, bases):
nicho = produto["_nicho"]
familia = produto["_familia"]
marca = produto["_marca"]
vendedor = produto["_vendedor"]
titulo = produto.get("productName", "")

base = (
    chave_base_titulo(titulo)
    if nicho == "Moto"
    else assinatura_diversidade(titulo)
)

score = float(produto.get("_score_base", 0))

if usados_marca[marca] >= 1 and marca != "sem_marca":
    score -= 3 * usados_marca[marca]

if usados_familia[familia] >= 1 and familia != "outros":
    score -= 6 * usados_familia[familia]

if usados_vendedor[vendedor] >= 1:
    score -= 3 * usados_vendedor[vendedor]

if base in bases:
    score -= 15

for item in selecionados:
    ratio = SequenceMatcher(
        None,
        sem_acento(titulo),
        sem_acento(item.get("productName", "")),
    ).ratio()

    if ratio >= SIMILARIDADE_MAX:
        score -= 22
    elif ratio >= 0.82:
        score -= 7

if oferta_e_estrela(
    produto,
    nicho,
    produto.get("_termo_busca", ""),
):
    score += 5

if nicho == "Eletroeletronicos":
    nome = sem_acento(titulo)
    if any(
        t in nome
        for t in [
            "smart tv",
            "televisao",
            "tv",
            "celular",
            "smartphone",
            "notebook",
            "iphone",
        ]
    ):
        score += 6

if nicho == "Moto":
    nome = sem_acento(titulo)
    vendas = int(produto.get("sales", 0) or 0)

    if modelo_moto_encontrado(
        titulo,
        produto.get("_modelo_moto", ""),
    ):
        score += 5

    if peca_moto_encontrada(
        titulo,
        produto.get("_peca_moto", ""),
    ):
        score += 6

    if vendas >= 500:
        score += 3

    if vendas >= 1000:
        score += 3

return score, base

=========================================================
SELECAO GLOBAL
=========================================================

def selecionar_final_global(pools, max_ofertas=10):
candidatos_por_nicho = {}

for nicho, pool in pools.items():
    validos = []

    for produto in pool:
        produto = dict(produto)
        produto["_nicho"] = nicho

        pid = chave_produto(produto, nicho)

        if historico_bloqueia(pid):
            continue

        validos.append(produto)

    candidatos_por_nicho[nicho] = validos

selecionados = []
usados_nicho = Counter()
usados_familia = Counter()
usados_marca = Counter()
usados_vendedor = Counter()
bases = set()

def melhor(nicho, candidatos):
    ranking = []

    for produto in candidatos:
        score, base = score_selecao(
            produto,
            selecionados,
            usados_familia,
            usados_marca,
            usados_vendedor,
            bases,
        )
        ranking.append((score, produto, base))

    ranking.sort(key=lambda x: x[0], reverse=True)
    return ranking[0] if ranking else None

# =====================================================
# FASE 1 - VAGAS PROTEGIDAS
# =====================================================

for nicho in NICHOS:
    meta = META_NICHO.get(nicho, 0)
    candidatos = candidatos_por_nicho.get(nicho, [])

    for _ in range(meta):
        if not candidatos or len(selecionados) >= max_ofertas:
            break

        escolha = melhor(nicho, candidatos)

        if not escolha:
            break

        _, produto, base = escolha

        selecionados.append(produto)
        candidatos.remove(produto)

        usados_nicho[nicho] += 1
        usados_marca[produto["_marca"]] += 1
        usados_familia[produto["_familia"]] += 1
        usados_vendedor[produto["_vendedor"]] += 1
        bases.add(base)

# =====================================================
# FASE 2 - COMPLETAR
# =====================================================

restantes = [
    produto
    for candidatos in candidatos_por_nicho.values()
    for produto in candidatos
]

while restantes and len(selecionados) < max_ofertas:
    ranking = []

    for produto in restantes:
        score, base = score_selecao(
            produto,
            selecionados,
            usados_familia,
            usados_marca,
            usados_vendedor,
            bases,
        )
        ranking.append((score, produto, base))

    ranking.sort(key=lambda x: x[0], reverse=True)
    _, escolhido, base = ranking[0]

    restantes.remove(escolhido)
    selecionados.append(escolhido)

    usados_nicho[escolhido["_nicho"]] += 1
    usados_marca[escolhido["_marca"]] += 1
    usados_familia[escolhido["_familia"]] += 1
    usados_vendedor[escolhido["_vendedor"]] += 1
    bases.add(base)

distribuicao = Counter(
    item["_nicho"] for item in selecionados
)

logging.info(f"DISTRIBUICAO FINAL: {dict(distribuicao)}")

logging.info(
    f"MOTO FINAL: {distribuicao.get('Moto', 0)}/"
    f"{META_NICHO.get('Moto', 0)} | "
    f"CANDIDATOS: {len(candidatos_por_nicho.get('Moto', []))}"
)

return selecionados[:max_ofertas]

=========================================================
RECUPERACAO
=========================================================

def recuperar_ofertas(pools, selecionados, estado):
if len(selecionados) >= MAX_OFERTAS:
return selecionados, estado

logging.info(
    f"RECUPERACAO: faltam {MAX_OFERTAS - len(selecionados)}"
)

ids_selecionados = {
    chave_produto(x, x["_nicho"])
    for x in selecionados
}

for nicho in random.sample(NICHOS, len(NICHOS)):
    if len(selecionados) >= MAX_OFERTAS:
        break

    if nicho == "Moto":
        buscas, estado = get_proximas_combinacoes_moto(estado, 2)
    else:
        termos, estado = escolher_termos_nicho(nicho, estado, 2)
        buscas = [(x, None, None) for x in termos]

    for termo_busca, modelo, peca in buscas:
        if len(selecionados) >= MAX_OFERTAS:
            break

        try:
            brutos = buscar_produtos_da_categoria_kw(
                termo_busca,
                nicho,
            )

            novos = []

            for bruto in brutos:
                if motivo_rejeicao(bruto):
                    continue

                titulo = str(
                    bruto.get("productName", "")
                ).strip()

                if not validar_relevancia_nicho(
                    nicho,
                    titulo,
                    termo=termo_busca,
                    modelo=modelo,
                    peca=peca,
                ):
                    continue

                produto = preparar_produto(
                    bruto,
                    nicho,
                    termo_busca,
                    modelo,
                    peca,
                )

                pid = chave_produto(
                    produto,
                    nicho,
                )

                if pid in ids_selecionados:
                    continue

                if historico_bloqueia(pid):
                    continue

                novos.append(produto)

            if not novos:
                continue

            # Reavalia pela qualidade e diversidade.
            escolhidos = selecionar_do_pool(
                novos,
                nicho,
                1,
            )

            if escolhidos:
                escolhido = escolhidos[0]
                selecionados.append(escolhido)
                ids_selecionados.add(
                    chave_produto(escolhido, nicho)
                )

        except Exception as e:
            logging.error(
                f"Erro recuperacao {nicho}/{termo_busca}: {e}",
                exc_info=True,
            )

return selecionados[:MAX_OFERTAS], estado

=========================================================
MOTOR PRINCIPAL
=========================================================

def get_shopee_offers():
global usados_no_ciclo, BASES_VISTAS
global ULTIMAS_BUSCAS_SHOPEE, ULTIMOS_TITULOS
global VENDEDORES_NO_CICLO, MARCAS_NO_CICLO, FAMILIAS_NO_CICLO

usados_no_ciclo = set()
BASES_VISTAS = set()
VENDEDORES_NO_CICLO = Counter()
MARCAS_NO_CICLO = Counter()
FAMILIAS_NO_CICLO = Counter()

ULTIMAS_BUSCAS_SHOPEE = ULTIMAS_BUSCAS_SHOPEE[-300:]
ULTIMOS_TITULOS = ULTIMOS_TITULOS[-150:]

estado = carregar_estado()
estado["ciclos"] = int(estado.get("ciclos", 0)) + 1

pools = {}
ordem_nichos = NICHOS[:]
random.shuffle(ordem_nichos)

logging.info("=" * 60)
logging.info(f"INICIO CICLO V24 #{estado['ciclos']}")
logging.info("=" * 60)

for nicho in ordem_nichos:
    try:
        pool, estado, _ = coletar_pool_nicho(
            nicho,
            estado,
        )
        pools[nicho] = pool

    except Exception as e:
        logging.error(
            f"Erro pool {nicho}: {e}",
            exc_info=True,
        )
        pools[nicho] = []

candidatos_total = sum(
    len(x) for x in pools.values()
)

logging.info(
    f"POOL TOTAL: {candidatos_total}"
)

selecionados = selecionar_final_global(
    pools,
    MAX_OFERTAS,
)

if len(selecionados) < MAX_OFERTAS:
    selecionados, estado = recuperar_ofertas(
        pools,
        selecionados,
        estado,
    )

selecionados = selecionados[:MAX_OFERTAS]

logging.info("=" * 60)
logging.info(
    f"RESULTADO CICLO: "
    f"{len(selecionados)}/{MAX_OFERTAS}"
)

for i, item in enumerate(selecionados, 1):
    logging.info(
        f"{i:02d}. [{item.get('_nicho')}] "
        f"{item.get('productName')} | "
        f"score={item.get('_score_base', 0):.1f} | "
        f"vendas={item.get('sales', 0)} | "
        f"comissao="
        f"{float(item.get('commissionRate', 0) or 0) * 100:.1f}%"
    )

logging.info("=" * 60)

salvar_estado(estado)

return [
    (item.get("_nicho", ""), item)
    for item in selecionados
]

=========================================================
COPY
=========================================================

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

def aplicar_id_afiliado(link):
parsed = urlparse(link)
query = parse_qs(parsed.query)
query["af_siteid"] = AFILIADO_ID
return urlunparse(
parsed._replace(
query=urlencode(query, doseq=True)
)
)

def gerar_link_whatsapp(mensagem):
texto = re.sub(r"<[^>]+>", "", mensagem)
return f"https://wa.me/?text={quote(texto)}"

def gerar_copy(
nome,
preco,
vendas,
avaliacao,
comissao,
link,
whatsapp=False,
):
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

🔥 {nome}

{gatilho}

{acao}

💰 R$ {preco}
⭐ {avaliacao} | 🛒 {vendas} vendas

⚠️ Pode subir de preço

🛒 COMPRAR AGORA: {link}

📢 Grupo:
{LINK_GRUPO_OFERTAS}
"""

return f"""


{abertura}

🔥 {nome}

{gatilho}

{acao}

💰 R$ {preco}
⭐ {avaliacao} | {vendas} vendas
💸 Comissão: {comissao}%

⚠️ Pode subir de preço

🛒 COMPRAR AGORA

📲 Entrar no grupo de ofertas
"""

=========================================================
ENVIO
=========================================================

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
try:
if not dentro_do_horario():
logging.info("Fora do horario permitido")
return

    ofertas = get_shopee_offers()

    if len(ofertas) < MIN_OFERTAS:
        logging.warning(
            f"Apenas {len(ofertas)} ofertas validas. "
            f"Ciclo nao enviado."
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
            link_html = html.escape(
                link,
                quote=True,
            )

            nome = html.escape(
                str(item.get("productName", "")),
                quote=False,
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
                    item.get(
                        "commissionRate",
                        0,
                    ) or 0
                ) * 100,
                2,
            )

            vendas_texto = f"{vendas:,}".replace(",", ".")
            preco_texto = f"{preco:.2f}".replace(".", ",")

            if not imagem:
                logging.warning(
                    f"Produto sem imagem: {nome}"
                )
                continue

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
                quote=True,
            )

            mensagem += (
                f'\n📲 <a href="{link_zap}">'
                "Compartilhar no WhatsApp</a>"
                "\n━━━━━━━━━━━━━━━"
                "\n📢 <b>Ofertas Secretas</b>"
            )

            produto_id = chave_produto(
                item,
                nicho,
            )

            selecionadas.append({
                "msg": mensagem,
                "img": imagem,
                "produto_id": produto_id,
                "nicho": nicho,
            })

        except Exception as e:
            logging.error(
                f"Erro preparando produto: {e}",
                exc_info=True,
            )

    if len(selecionadas) < MIN_OFERTAS:
        logging.warning(
            f"Somente {len(selecionadas)} ofertas "
            f"possuem imagem/dados para envio"
        )
        return

    logging.info(
        f"ENVIANDO {len(selecionadas)} OFERTAS PARA VIP"
    )

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

            registrar_historico(
                item["produto_id"]
            )

            enviadas.append(item)

            await asyncio.sleep(40)

        except Exception as e:
            logging.error(
                f"Erro enviando VIP: {e}",
                exc_info=True,
            )

    # =================================================
    # FREE
    # =================================================

    estado = carregar_estado()

    indice = int(
        estado.get("free_nicho_idx", 0)
    )

    nicho_free = NICHOS_FREE_ROTA[
        indice % len(NICHOS_FREE_ROTA)
    ]

    oferta_free = next(
        (
            x for x in enviadas
            if x["nicho"] == nicho_free
        ),
        None,
    )

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

            registrar_historico(
                oferta_free["produto_id"]
            )

        except Exception as e:
            logging.error(
                f"Erro enviando FREE: {e}",
                exc_info=True,
            )

    estado["free_nicho_idx"] = (
        indice + 1
    ) % len(NICHOS_FREE_ROTA)

    salvar_estado(estado)

    logging.info(
        f"CICLO FINALIZADO: "
        f"VIP={len(enviadas)} | "
        f"FREE={'1' if oferta_free else '0'}"
    )

except Exception as e:
    logging.error(
        f"ERRO CRITICO: {e}",
        exc_info=True,
    )

=========================================================
RUNTIME
=========================================================

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

asyncio.create_task(
    keep_alive()
)

logging.info(
    "🤖 BOT RODANDO ESTAVEL - V24"
)

logging.info(
    f"Intervalo: {CHECK_INTERVAL}s | "
    f"Janela: {HORARIO_INICIO} - {HORARIO_FIM}"
)


async def error_handler(update, context):
logging.error(
f"ERRO TELEGRAM: {context.error}",
exc_info=True,
)

=========================================================
MAIN
=========================================================

if name == "main":
if not TELEGRAM_TOKEN:
raise RuntimeError(
"TELEGRAM_TOKEN ausente"
)

if not SHOPEE_PASSWORD:
    raise RuntimeError(
        "SHOPEE_PASSWORD ausente"
    )

while True:
    try:
        app = (
            ApplicationBuilder()
            .token(TELEGRAM_TOKEN)
            .post_init(post_init)
            .build()
        )

        app.add_error_handler(
            error_handler
        )

        app.run_polling(
            allowed_updates=None
        )

    except Exception as erro:
        logging.error(
            f"BOT REINICIANDO: {erro}",
            exc_info=True,
        )
        time.sleep(15)
