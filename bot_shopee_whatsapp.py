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
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO SHOPEE V18 - CATÁLOGO SEQUENCIAL INTELIGENTE")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")

CHAT_ID_DESTINO = -1003848415150
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"
CHECK_INTERVAL = 5400

MAX_OFERTAS = 10
MIN_OFERTAS = 4
HISTORICO_DIAS = 3
SIMILARIDADE_MAX = 0.88
VENDAS_MIN = 2
RATING_MIN = 4.0
PRECO_MIN = 15.0
PRECO_MAX = 10000.0
COMISSAO_MIN = 0.03

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")

ESTADO_FILE = "estado_buscas.json"
HISTORICO_FILE = "historico_envios.json"

ULTIMAS_BUSCAS_SHOPEE = []
ULTIMOS_TITULOS = []
usadas_abertura = set()
usadas_gatilho = set()
usados_no_ciclo = set()
BASES_VISTAS = set()
REJEICOES = Counter()

MOTOS = [
    "titan 150",
    "cb 300",
    "factor 150",
    "titan 160",
    "tornado",
    "fazer 150",
    "titan 125",
    "bros 160",
    "twister 250",
    "biz 125",
    "pop 110",
    "xre 300",
    "croosser 150",
    "xre 190",
    "fazer 250",
    "lander 250",
    "bros 150",
    "tenere 250",
    "biz 100",
    "twister 300",
]

PECAS_MOTO = [
    "kit relacao",
    "kit embreagem",
    "bateria",
    "refil bomba combustivel",
    "chicote fiação principal",
    "bucha balança",
    "burrinho de freio",
    "estribo",
    "pedal de marcha",
    "pedal de freio",
    "rolamento virabrequim",
    "estator",
    "chave ignição",
    "punho chave luz",
    "kit pisca seta",
    "par pneu",
    "bloco optico",
    "retentor de bengala",
    "bucha amortecedor",
    "carburador corpo de injeção",
    "kit cilindro",
    "jogo de juntas",
    "biela",
    "valvulas escape admissão",
    "disco de freio",
    "tubo interno",
    "vela iridium",
    "pastilha freio",
    "guidao",
    "manopla",
    "amortecedor",
    "retrovisor",
    "farol",
]

PRODUTOS_NICHO = {
    "Casa": [
        "air fryer",
        "aspirador",
        "liquidificador",
        "capa para colchão",
        "jogo de pratos",
        "jogo de copos",
        "talher",
        "panos de prato",
        "toalhas de banho",
        "coberta manta",
        "lençol",
        "cobre leito",
        "mangueira de jardim",
        "tapete",
        "torneira de cozinha",
        "filtro de barro",
        "guarda roupas casal",
        "guarda roupas portatil",
        "cama casal",
        "forma de silicone",
        "sapateira",
        "umidificador",
        "ar condicionado",
        "jogo de panelas",
        "cortinas",
        "tintas",
        "frigideiras",
        "rede de dormir",
        "pipoqueria",
        "cafeteira",
        "mop",
        "ventilador",
        "batedeira",
        "panela eletrica",
    ],
    "Maternidade": [
        "carrinho bebe",
        "berco bebe",
        "fralda descartavel",
        "fralda de pano",
        "naninha",
        "sapatinho",
        "pagãozinho",
        "coberdrom dupla face",
        "kit toalha umedecida",
        "toalha infantil banho",
        "banheira",
        "mictorio infantil",
        "patinete",
        "bebê riborn",
        "carrinhos",
        "piscina de bolinhas",
        "kit bolsa maternidade",
        "canguru",
        "mosqueteiro",
        "kit mamadeira",
        "kit bicos",
        "baba eletronica",
        "ninho bebe",
        "kit enxoval bebe",
        "babador bebe",
        "mordedor bebe",
        "tapete infantil",
    ],
    "Eletroeletrônicos": [
        "smartwatch",
        "fone bluetooth",
        "caixa de som bluetooth",
        "bastão pau de selfie",
        "celular",
        "smartphone",
        "televisão",
        "video game",
        "fones de ouvido",
        "capinha celular",
        "pelicula celular",
        "massageador",
        "balança digital",
        "aparelho medidor de pressão",
        "massageador portatil",
        "webcam camera",
        "pen drive",
        "impressora termica",
        "maquina de impressão 3d",
        "computador",
        "cpu gamer",
        "cpu",
        "notbook",
        "drone",
        "camera de segurança",
        "golpro",
        "tablet",
        "ssd",
        "mouse gamer",
        "teclado mecanico",
        "headset gamer",
        "power bank",
    ],
    "Moda feminina": [
        "vestido feminino",
        "conjunto feminino",
        "kit calcinhas",
        "biquines",
        "saida de praia",
        "maquiagens",
        "roupa academia",
        "calça jean",
        "calça leggin",
        "saia longa",
        "vestido lovito",
        "sandalias",
        "pijamas",
        "pijamas mãe e filha",
        "blusa regata",
        "kit sutian",
        "bermuda modeladora",
        "oculos de sol",
        "calça social",
        "vestido midi",
        "jaqueta feminina",
        "casaco feminino",
        "conjunto alfaiataria",
        "short feminino",
        "macacao feminino",
        "tenis feminino",
        "bolsa feminina",
    ],
    "Moda masculina": [
        "camiseta masculina",
        "relogios esportivos",
        "bermudas jeans",
        "relogio de quartzo",
        "camisetas regatas",
        "camisa polo",
        "camisa de linho",
        "terno",
        "blazer",
        "camisa tshort",
        "kit meias",
        "barbeador",
        "meias esportivas",
        "oculos de sol",
        "toucas",
        "calção de futebol",
        "tenis futebol",
        "chuteiras",
        "camisa termica",
        "bermuda masculina",
        "jaqueta masculina",
        "tenis masculino",
        "carteira masculina",
        "kit cueca",
    ],
}

VARIACOES_NICHO = {
    "Casa": ["inoxidavel", "inverter", "digital", "sem fio", "2 em 1", "gourmet"],
    "Maternidade": ["recem nascido", "anti refluxo", "multifuncional"],
    "Eletroeletrônicos": ["gamer", "pro", "bluetooth 5.0"],
    "Moda feminina": ["plus size", "casual", "social"],
    "Moda masculina": ["casual", "social", "slim"],
}

FAMILIAS_EXTRA = {
    "air_fryer": ["air fryer", "airfryer", "fritadeira"],
    "fone_bluetooth": ["fone bluetooth", "fones de ouvido", "headset", "earbud"],
    "smartwatch": ["smartwatch", "relogio inteligente", "relógio inteligente"],
    "caixa_som": ["caixa de som", "speaker", "soundbar"],
}

def carregar_estado():
    try:
        if os.path.exists(ESTADO_FILE):
            with open(ESTADO_FILE, "r", encoding="utf-8") as f:
                estado = json.load(f)
        else:
            estado = {}
    except:
        estado = {}

    estado.setdefault("Moto", {})
    for nicho in ["Casa", "Maternidade", "Eletroeletrônicos", "Moda feminina", "Moda masculina"]:
        estado.setdefault(nicho, {})

    estado["Moto"].setdefault("moto_idx", 0)
    estado["Moto"].setdefault("peca_idx", 0)
    estado["Moto"].setdefault("resultado_idx", {})

    for nicho in ["Casa", "Maternidade", "Eletroeletrônicos", "Moda feminina", "Moda masculina"]:
        estado[nicho].setdefault("produto_idx", 0)
        estado[nicho].setdefault("resultado_idx", {})

    return estado

def salvar_estado(estado):
    try:
        with open(ESTADO_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Erro salvando estado: {e}")

def carregar_historico():
    try:
        if os.path.exists(HISTORICO_FILE):
            with open(HISTORICO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {}

def salvar_historico(hist):
    try:
        with open(HISTORICO_FILE, "w", encoding="utf-8") as f:
            json.dump(hist, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"Erro salvando historico: {e}")

def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 30) <= agora <= dt_time(21, 30)

def normalizar_texto(txt):
    if not txt:
        return ""
    txt = txt.lower().strip()
    txt = re.sub(r"[^a-z0-9à-ÿ\s]", " ", txt)
    txt = re.sub(r"\s+", " ", txt)
    return txt

def chave_base_titulo(titulo):
    t = normalizar_texto(titulo)
    stop = {
        "premium", "novo", "promocao", "promoção", "super", "original", "profissional",
        "casual", "masculino", "feminino", "infantil", "adulto", "unissex",
        "estica", "kit", "com", "de", "para", "o", "a", "promo", "oferta",
        "modelo", "versao", "versão", "linha", "envio"
    }
    tokens = [x for x in t.split() if x not in stop and len(x) > 2]
    return " ".join(tokens[:6])

def tem_bloqueio(titulo):
    t = normalizar_texto(titulo)
    palavras = [
        "teste", "amostra", "não compre", "nao compre", "produto teste", "exemplo",
        "dummy", "vela led", "vela decorativa", "decorativa", "decoração", "casamento", "festa"
    ]
    return any(p in t for p in palavras)

def titulo_duplicado_forte(titulo):
    t = normalizar_texto(titulo)
    base = chave_base_titulo(titulo)
    for prev in ULTIMOS_TITULOS:
        if t == prev:
            return True
        if SequenceMatcher(None, t, prev).ratio() >= SIMILARIDADE_MAX:
            return True
        if base and base == chave_base_titulo(prev):
            return True
    return False

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
        return 0
    except:
        return 0

def oferta_score(p):
    try:
        vendas = int(p.get("sales", 0) or 0)
        rating = float(p.get("ratingStar", 0) or 0)
        comissao = float(p.get("commissionRate", 0) or 0)
        preco = float(p.get("priceMin", 0) or 0)
        st = p.get("shopType", [])
        nome = str(p.get("productName", "")).lower()
        score = 0
        score += min(vendas / 8, 25)
        score += rating * 2
        score += comissao * 100
        score += shop_type_score(st)
        if 50 <= preco <= 5000:
            score += 6
        if any(x in nome for x in ["moto", "bebê", "bebe", "smartwatch", "ssd", "fone", "tablet"]):
            score += 2
        return score
    except:
        return 0

def motivo_rejeicao(p):
    try:
        titulo = str(p.get("productName", "")).strip()
        link = str(p.get("offerLink") or p.get("productLink") or "").strip()
        preco_min = float(p.get("priceMin", 0) or 0)
        comissao = float(p.get("commissionRate", 0) or 0)
        vendas = int(p.get("sales", 0) or 0)
        rating = float(p.get("ratingStar", 0) or 0)
        if not titulo:
            return "sem_titulo"
        if not link:
            return "sem_link"
        if tem_bloqueio(titulo):
            return "bloqueio_texto"
        if preco_min < PRECO_MIN:
            return "preco_baixo"
        if preco_min > PRECO_MAX:
            return "preco_alto"
        if comissao < COMISSAO_MIN:
            return "comissao_baixa"
        if vendas < VENDAS_MIN:
            return "vendas_baixas"
        if rating and rating < RATING_MIN:
            return "rating_baixo"
        if link in ULTIMAS_BUSCAS_SHOPEE or link in usados_no_ciclo:
            return "link_repetido"
        return None
    except Exception as e:
        return f"erro_validacao:{type(e).__name__}"

def gerar_link_whatsapp_from_html(msg_html):
    texto = re.sub(r"<[^>]+>", "", msg_html)
    return f"https://wa.me/?text={quote(texto)}"

def aplicar_id_afiliado(link):
    parsed = urlparse(link)
    query = parse_qs(parsed.query)
    query["af_siteid"] = AFILIADO_ID
    return urlunparse(parsed._replace(query=urlencode(query, doseq=True)))

def buscar_produtos_da_categoria_kw(palavra_chave, categoria_selecionada):
    logging.info(f"Buscando em {categoria_selecionada}: {palavra_chave}")
    timestamp = int(time.time())
    query_body = f'''
    query {{
        productOfferV2(sortType: 2, limit: 50, keyword: "{palavra_chave}", isAMSOffer: true) {{
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
            }}
        }}
    }}
    '''
    payload = json.dumps({"query": query_body}, ensure_ascii=False)
    base = SHOPEE_APP_ID + str(timestamp) + payload + SHOPEE_PASSWORD
    signature = hashlib.sha256(base.encode()).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}"
    }
    r = requests.post(SHOPEE_GRAPHQL_URL, data=payload.encode("utf-8"), headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()
    return data.get("data", {}).get("productOfferV2", {}).get("nodes", []) or []

def historico_bloqueia(chave):
    hist = carregar_historico()
    if chave not in hist:
        return False
    try:
        data = datetime.fromisoformat(hist[chave])
        return datetime.now(FUSO_BR) - data < timedelta(days=HISTORICO_DIAS)
    except:
        return False

def registrar_historico(chave):
    hist = carregar_historico()
    hist[chave] = datetime.now(FUSO_BR).isoformat()
    salvar_historico(hist)

def parse_familia_from_title(titulo):
    t = normalizar_texto(titulo)
    for fam in sorted(MOTOS, key=len, reverse=True):
        if normalizar_texto(fam) in t:
            return normalizar_texto(fam).replace(" ", "_")
    for familia, termos in FAMILIAS_EXTRA.items():
        if any(normalizar_texto(term) in t for term in termos):
            return familia
    return "outros"

def chave_resultado(nicho, chave):
    return f"{nicho}__{chave}"

def carregar_indice_resultado(estado, nicho, chave):
    return estado.setdefault(nicho, {}).setdefault("resultado_idx", {}).get(chave, 0)

def salvar_indice_resultado(estado, nicho, chave, valor):
    estado.setdefault(nicho, {}).setdefault("resultado_idx", {})[chave] = valor

def montar_catalogo():
    catalogos = {
        "Moto": [],
        "Casa": [],
        "Maternidade": [],
        "Eletroeletrônicos": [],
        "Moda feminina": [],
        "Moda masculina": [],
    }
    for p in PRODUTOS_NICHO["Casa"]:
        catalogos["Casa"].append((p, "", ""))
    for p in PRODUTOS_NICHO["Maternidade"]:
        catalogos["Maternidade"].append((p, "", ""))
    for p in PRODUTOS_NICHO["Eletroeletrônicos"]:
        catalogos["Eletroeletrônicos"].append((p, "", ""))
    for p in PRODUTOS_NICHO["Moda feminina"]:
        catalogos["Moda feminina"].append((p, "", ""))
    for p in PRODUTOS_NICHO["Moda masculina"]:
        catalogos["Moda masculina"].append((p, "", ""))
    return catalogos

CATALOGOS = montar_catalogo()

def get_proximo_bloco(nicho, estado, tamanho=2):
    catalogo = CATALOGOS[nicho]
    if not catalogo:
        return [], estado
    idx = estado.setdefault(nicho, {}).get("produto_idx", 0)
    bloco = catalogo[idx:idx + tamanho]
    if len(bloco) < tamanho:
        bloco = bloco + catalogo[:tamanho - len(bloco)]
    estado[nicho]["produto_idx"] = (idx + tamanho) % len(catalogo)
    return bloco, estado

def get_proxima_combinacao_moto(estado, tamanho_motos=2):
    moto_state = estado.setdefault("Moto", {})
    moto_idx = moto_state.get("moto_idx", 0)
    peca_idx = moto_state.get("peca_idx", 0)

    total_motos = len(MOTOS)
    total_pecas = len(PECAS_MOTO)
    if total_motos == 0 or total_pecas == 0:
        return [], estado

    peca_atual = PECAS_MOTO[peca_idx % total_pecas]
    bloco_motos = []
    for i in range(tamanho_motos):
        bloco_motos.append(MOTOS[(moto_idx + i) % total_motos])

    novo_moto_idx = moto_idx + tamanho_motos
    if novo_moto_idx >= total_motos:
        novo_moto_idx = novo_moto_idx % total_motos
        peca_idx = (peca_idx + 1) % total_pecas

    moto_state["moto_idx"] = novo_moto_idx
    moto_state["peca_idx"] = peca_idx

    return [(m, peca_atual) for m in bloco_motos], estado

def validar_modelo_titulo(titulo, modelo):
    if not modelo:
        return True
    t = normalizar_texto(titulo)
    m = normalizar_texto(modelo)
    return m in t or any(x in t for x in m.split())

def selecionar_ofertas_nicho(nicho, cota, estado):
    global BASES_VISTAS, REJEICOES
    produtos_brutos = []
    blocos, estado = get_proximo_bloco(nicho, estado, tamanho=2)

    for tpl in blocos:
        produto, modelo, marca = tpl
        kw = " ".join([x for x in [produto, modelo, marca] if x])
        resultados = buscar_produtos_da_categoria_kw(kw, nicho)
        produtos_brutos.extend([(r, tpl) for r in resultados])

    logging.info(f"{nicho}: {len(produtos_brutos)} produtos brutos")

    filtrados = []
    rejeitados_local = Counter()

    for p, tpl in produtos_brutos:
        motivo = motivo_rejeicao(p)
        if motivo is None:
            filtrados.append((p, tpl))
        else:
            rejeitados_local[motivo] += 1
            REJEICOES[motivo] += 1

    logging.info(f"{nicho}: {len(filtrados)} passaram no filtro")
    if rejeitados_local:
        logging.info(f"{nicho}: rejeições {dict(rejeitados_local)}")

    filtrados.sort(key=lambda x: oferta_score(x[0]), reverse=True)

    if filtrados:
        idx_resultado = carregar_indice_resultado(estado, nicho, filtrados[0][1][0])
        filtrados = filtrados[idx_resultado:] + filtrados[:idx_resultado]
    else:
        idx_resultado = 0

    escolhidos = []
    chaves_ciclo = set()
    titulos_ciclo = []
    familias_ciclo = Counter()
    motivos = Counter()

    for p, tpl in filtrados:
        if len(escolhidos) >= cota:
            break

        titulo = str(p.get("productName", "")).strip()
        link = p.get("offerLink") or p.get("productLink")
        familia = parse_familia_from_title(titulo)
        modelo = normalizar_texto(tpl[1]).replace(" ", "")
        base = chave_base_titulo(titulo)
        produto_id = hashlib.md5((link or "").encode()).hexdigest()

        if base and base in BASES_VISTAS:
            motivos["base_repetida"] += 1
            continue
        if not link or link in usados_no_ciclo or link in ULTIMAS_BUSCAS_SHOPEE:
            motivos["link_repetido"] += 1
            continue
        if historico_bloqueia(produto_id):
            motivos["historico"] += 1
            continue
        if titulo_duplicado_forte(titulo):
            motivos["titulo"] += 1
            continue
        if any(SequenceMatcher(None, normalizar_texto(titulo), t).ratio() >= SIMILARIDADE_MAX for t in titulos_ciclo):
            motivos["similaridade"] += 1
            continue
        if nicho == "Moto" and not validar_modelo_titulo(titulo, tpl[0]) and not validar_modelo_titulo(titulo, tpl[1]):
            motivos["modelo"] += 1
            continue

        chave = chave_resultado(nicho, f"{familia}__{modelo}")
        idx_resultado_atual = carregar_indice_resultado(estado, nicho, chave)

        if familia != "outros":
            limite = 2 if nicho == "Moto" else 3
            if familias_ciclo[familia] >= limite:
                motivos["familia_limite"] += 1
                continue

        escolhidos.append(p)
        chaves_ciclo.add(chave)
        titulos_ciclo.append(normalizar_texto(titulo))
        familias_ciclo[familia] += 1
        BASES_VISTAS.add(base)
        usados_no_ciclo.add(link)
        ULTIMAS_BUSCAS_SHOPEE.append(link)
        ULTIMOS_TITULOS.append(normalizar_texto(titulo))
        salvar_indice_resultado(estado, nicho, tpl[0], idx_resultado_atual + 1)

        logging.info(f"{nicho}: escolhido {titulo} | chave={chave}")

        if len(ULTIMAS_BUSCAS_SHOPEE) > 300:
            ULTIMAS_BUSCAS_SHOPEE.pop(0)
        if len(ULTIMOS_TITULOS) > 150:
            ULTIMOS_TITULOS.pop(0)

    if motivos:
        logging.info(f"{nicho}: rejeições seleção {dict(motivos)}")

    if len(escolhidos) < cota:
        logging.warning(f"{nicho}: só conseguiu {len(escolhidos)}/{cota}")

    return escolhidos, estado

def selecionar_ofertas_moto(cota, estado):
    global BASES_VISTAS, REJEICOES
    combinacoes, estado = get_proxima_combinacao_moto(estado, tamanho_motos=2)
    escolhidos = []
    chaves_ciclo = set()
    titulos_ciclo = []

    for moto, peca in combinacoes:
        if len(escolhidos) >= cota:
            break

        kw = f"{peca} {moto}"
        resultados = buscar_produtos_da_categoria_kw(kw, "Moto")
        chave = chave_resultado("Moto", f"{normalizar_texto(moto).replace(' ', '_')}__{normalizar_texto(peca).replace(' ', '_')}")
        idx_resultado = carregar_indice_resultado(estado, "Moto", chave)

        if not resultados:
            continue

        total = len(resultados)
        tentativas = 0

        while tentativas < total:
            p = resultados[(idx_resultado + tentativas) % total]
            tentativas += 1

            motivo = motivo_rejeicao(p)
            if motivo is not None:
                REJEICOES[motivo] += 1
                continue

            titulo = str(p.get("productName", "")).strip()
            link = p.get("offerLink") or p.get("productLink")
            base = chave_base_titulo(titulo)
            produto_id = hashlib.md5((link or "").encode()).hexdigest()

            if base and base in BASES_VISTAS:
                continue
            if not link or link in usados_no_ciclo or link in ULTIMAS_BUSCAS_SHOPEE:
                continue
            if historico_bloqueia(produto_id):
                continue
            if not validar_modelo_titulo(titulo, moto):
                continue
            if titulo_duplicado_forte(titulo):
                continue
            if any(SequenceMatcher(None, normalizar_texto(titulo), t).ratio() >= SIMILARIDADE_MAX for t in titulos_ciclo):
                continue

            escolhidos.append(p)
            chaves_ciclo.add(chave)
            titulos_ciclo.append(normalizar_texto(titulo))
            BASES_VISTAS.add(base)
            usados_no_ciclo.add(link)
            ULTIMAS_BUSCAS_SHOPEE.append(link)
            ULTIMOS_TITULOS.append(normalizar_texto(titulo))
            salvar_indice_resultado(estado, "Moto", chave, (idx_resultado + tentativas) % total)

            logging.info(f"Moto: escolhido {titulo} | chave={chave}")
            break

    if len(ULTIMAS_BUSCAS_SHOPEE) > 300:
        ULTIMAS_BUSCAS_SHOPEE.pop(0)
    if len(ULTIMOS_TITULOS) > 150:
        ULTIMOS_TITULOS.pop(0)

    if len(escolhidos) < cota:
        logging.warning(f"Moto: só conseguiu {len(escolhidos)}/{cota}")

    return escolhidos, estado

def get_shopee_offers():
    global usados_no_ciclo, BASES_VISTAS
    usados_no_ciclo = set()
    BASES_VISTAS = set()
    candidatos = []
    estado = carregar_estado()

    nichos_ordem = list(CATALOGOS.keys())
    random.shuffle(nichos_ordem)

    COTAS_POR_NICHO = {
        "Moda feminina": 1,
        "Moda masculina": 1,
        "Moto": 2,
        "Maternidade": 2,
        "Casa": 2,
        "Eletroeletrônicos": 2,
    }

    for nicho in nichos_ordem:
        try:
            if nicho == "Moto":
                escolhidos, estado = selecionar_ofertas_moto(COTAS_POR_NICHO[nicho], estado)
            else:
                escolhidos, estado = selecionar_ofertas_nicho(nicho, COTAS_POR_NICHO[nicho], estado)
            candidatos.extend(escolhidos)
        except Exception as e:
            logging.error(f"Erro no nicho {nicho}: {e}", exc_info=True)

    salvar_estado(estado)
    candidatos.sort(key=oferta_score, reverse=True)
    logging.info(f"Shopee OK: {len(candidatos[:MAX_OFERTAS])} produtos exclusivos para envio")
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
    "🛒 NÃO DEIXA ESCAPAR!"
]

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link, for_whatsapp=False):
    aberturas = [
        "🚨 Isso aqui não é comum aparecer assim",
        "👀 Achei isso aqui e fui conferir…",
        "🔥 Isso aqui tá com cara de oportunidade",
        "💥 Esse aqui tá chamando atenção de quem compra",
        "🛑 Para tudo e olha isso aqui",
        "🤯 Sério… olha esse achado",
        "⚠️ Isso aqui pode desaparecer rápido",
        "👁️ Pouca gente viu isso ainda",
        "📉 Esse preço aqui não costuma durar",
        "🚀 Esse aqui tá começando a rodar forte"
    ]
    gatilhos = [
        "Preço muito abaixo do que costuma aparecer",
        "Avaliações acima da média",
        "Volume de vendas alto",
        "Simples e funcional",
        "Custo-benefício forte",
        "Quem compra recomenda",
        "Produto direto ao ponto",
        "Tá vendendo bem",
        "Boa margem pra afiliado",
        "Resolve de verdade"
    ]
    chamada_grupo = f"📢 Quer mais ofertas assim? Entre no nosso grupo: {LINK_GRUPO_OFERTAS}"
    chamada_acao = random.choice(CHAMADAS_ACAO)
    abertura = random.choice([a for a in aberturas if a not in usadas_abertura] or aberturas)
    usadas_abertura.add(abertura)
    gatilho = random.choice([g for g in gatilhos if g not in usadas_gatilho] or gatilhos)
    usadas_gatilho.add(gatilho)

    if for_whatsapp:
        return f"""{abertura}

*🔥 {nome}*

{gatilho}

{chamada_acao}

*💰 R$ {preco}*
*⭐ {avaliacao} | 🛒 {vendas} vendas*

⚠️ Pode subir de preço

🛒 COMPRAR AGORA: {link}
{chamada_grupo}
"""
    return f"""{abertura}

🔥 <b>{nome}</b>

{gatilho}

{chamada_acao}

💰 <b>R$ {preco}</b>
⭐ <b>{avaliacao} | {vendas} vendas</b>
💸 Comissão: <b>{comissao}%</b>

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>
<a href="{LINK_GRUPO_OFERTAS}">📲 Entrar no grupo de ofertas</a>
"""

async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        logging.info("Loop de ofertas iniciado")
        if not dentro_do_horario():
            logging.info("Fora do horário (05:30–21:30)")
            return

        usadas_abertura.clear()
        usadas_gatilho.clear()
        shopee_ofertas = get_shopee_offers()
        selecionadas = []

        if len(shopee_ofertas) < MIN_OFERTAS:
            logging.warning(f"Apenas {len(shopee_ofertas)} ofertas válidas. Pulando envio.")
            return

        for item in shopee_ofertas[:MAX_OFERTAS]:
            try:
                link_base = item.get("offerLink") or item.get("productLink")
                link = aplicar_id_afiliado(link_base)
                nome = html.escape(item["productName"])
                preco = float(item["priceMin"])
                img = item["imageUrl"]
                rating = float(item.get("ratingStar", 4.5))
                vendas = int(item.get("sales", 100))
                comissao = round(float(item.get("commissionRate", 0)) * 100, 2)

                produto_id = hashlib.md5((link_base or "").encode()).hexdigest()

                vendas_f = f"{vendas:,}".replace(",", ".")
                preco_f = f"{preco:.2f}".replace(".", ",")

                msg = gerar_copy(nome, preco_f, vendas_f, rating, comissao, link, for_whatsapp=False)
                zap_msg = gerar_copy(nome, preco_f, vendas_f, rating, 0, link, for_whatsapp=True)
                zap = gerar_link_whatsapp_from_html(zap_msg)
                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"
                selecionadas.append({"msg": msg, "img": img, "produto_id": produto_id})
            except Exception as e:
                logging.error(f"Erro Shopee item: {e}", exc_info=True)

        logging.info(f"Selecionadas: {len(selecionadas)}")

        if not selecionadas:
            logging.warning("Nenhuma oferta encontrada")
            return

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 <b>OFERTAS NOVAS CHEGANDO...</b>",
            parse_mode="HTML"
        )

        await asyncio.sleep(5)

        for item in selecionadas:
            try:
                logging.info("Enviando produto")
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=item["msg"],
                    parse_mode="HTML"
                )
                registrar_historico(item["produto_id"])
                await asyncio.sleep(40)
            except Exception as e:
                logging.error(f"Erro Telegram: {e}", exc_info=True)

        logging.info("Loop finalizado")

    except Exception as e:
        logging.error(f"ERRO CRITICO: {e}", exc_info=True)

async def keep_alive():
    while True:
        logging.info("BOT VIVO")
        await asyncio.sleep(300)

async def post_init(app):
    app.job_queue.run_repeating(send_ofertas, interval=CHECK_INTERVAL, first=10)
    asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTAVEL")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logging.error(f"ERRO TELEGRAM: {context.error}", exc_info=True)

if __name__ == "__main__":
    if not TELEGRAM_TOKEN:
        raise RuntimeError("TELEGRAM_TOKEN ausente")

    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).build()
            app.add_error_handler(error_handler)
            app.run_polling(allowed_updates=None)
        except Exception as e:
            logging.error(f"BOT REINICIANDO: {e}", exc_info=True)
            time.sleep(15)

