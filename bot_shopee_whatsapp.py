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
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO SHOPEE V13.2 - COTAS + SUBCATEGORIA + MOTO ROTATIVO")

TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "")

CHAT_ID_DESTINO = -1003848415150
SHOPEE_APP_ID = "18349740277"
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"
CHECK_INTERVAL = 5400

MAX_OFERTAS = 10
MIN_OFERTAS = 6

COTAS_POR_NICHO = {
    "Moda feminina": 1,
    "Moda masculina": 1,
    "Moto": 2,
    "Maternidade": 2,
    "Casa": 2,
    "Eletroeletrônicos": 2
}

PRECO_MIN = 15.0
PRECO_MAX = 10000.0
COMISSAO_MIN = 0.03
VENDAS_MIN = 5
RATING_MIN = 4.0

MOTO_BUSCAS = [
    "kit relacao titan 160 riffel",
    "kit relacao fazer 250 riffel",
    "kit relacao xre 300 riffel",
    "kit relacao cb300 riffel",
    "kit relacao lander 250 scud",
    "kit relacao bros 160 scud",
    "kit embreagem titan 160 hamp",
    "kit embreagem fazer 250 cobreq",
    "kit embreagem xre 300 cobreq",
    "kit embreagem cb300 cobreq",
    "kit cabos titan 160 scud",
    "kit cabos fazer 250 scud",
    "kit cabos xre 300 scud",
    "kit cabos lander 250 scud",
    "bateria titan 160 heliar",
    "bateria fazer 250 heliar",
    "bateria xre 300 yuasa",
    "bateria cb300 yuasa",
    "pastilha freio titan 160 cobreq",
    "pastilha freio fazer 250 cobreq",
    "pastilha freio xre 300 diafrag",
    "pastilha freio cb300 diafrag",
    "guidao titan 160 protork",
    "guidao fazer 250 protork",
    "guidao xre 300 protork",
    "guidao bros 160 protork",
    "vela iridium titan 160 ngk",
    "vela iridium fazer 250 ngk",
    "vela iridium xre 300 ngk",
    "vela iridium cb300 ngk",
    "capacete norisk",
    "capacete asx",
    "capacete san marino",
    "estator titan 160 magnetron",
    "estator fazer 250 magnetron",
    "estator xre 300 magnetron",
    "chicote principal titan 160 magnetron",
    "chicote principal fazer 250 magnetron",
    "chicote principal xre 300 magnetron",
    "amortecedor titan 160 cofap",
    "amortecedor fazer 250 cofap",
    "amortecedor xre 300 cofap",
    "manopla titan 160 circuit",
    "manopla fazer 250 circuit",
    "manopla xre 300 circuit"
]

KEYWORDS = {
    "Moda feminina": [
        "vestido feminino", "blusa feminina", "saia feminina", "tenis feminino",
        "sandalia feminina", "bolsa feminina", "shorts feminino", "conjunto feminino",
        "macacao feminino", "calca feminina"
    ],
    "Moda masculina": [
        "bermuda masculina", "camisa masculina", "tenis masculino", "sapato masculino",
        "calca masculina", "kit cueca", "blaser masculino", "jaqueta masculina",
        "camisa polo masculina", "carteira masculina"
    ],
    "Moto": [
        "escapamento moto", "pneu moto", "retrovisor moto", "capacete moto",
        "bateria moto", "kit relacao moto", "freio moto", "pastilha freio moto",
        "farol moto", "carenagem moto"
    ],
    "Maternidade": [
        "kit enxoval bebe", "carrinho bebe", "berco bebe", "chocalho bebe",
        "mordedor bebe", "babador bebe", "cadeirinha bebe", "tapete infantil",
        "brinquedo educativo bebe", "ninho bebe"
    ],
    "Casa": [
        "air fryer", "aspirador", "mop", "organizador cozinha", "cafeteira",
        "liquidificador", "batedeira", "panela eletrica", "tapete infantil", "ventilador"
    ],
    "Eletroeletrônicos": [
        "smartwatch", "fone bluetooth", "ssd", "carregador turbo", "power bank",
        "caixa de som bluetooth", "tablet", "mouse gamer", "teclado mecanico", "headset gamer"
    ]
}

SUBCATEGORIAS = {
    "caixa_som": [
        "caixa de som", "caixa som", "soundbar", "speaker", "bluetooth karaok", "karaokê", "karaoke"
    ],
    "fone": [
        "fone", "earbuds", "headset", "fone de ouvido", "auricular"
    ],
    "smartwatch": [
        "smartwatch", "relogio inteligente", "relógio inteligente"
    ],
    "ssd": ["ssd"],
    "mouse": ["mouse"],
    "teclado": ["teclado"],
    "airfryer": ["air fryer", "airfryer"],
    "aspirador": [
        "aspirador", "aspira po", "aspira pó", "aspirador robo", "aspirador robô", "robot vacuum", "robo aspirador"
    ],
    "mop": ["mop"],
    "liquidificador": ["liquidificador"],
    "cafeteira": ["cafeteira"],
    "ventilador": ["ventilador"],
    "babador": ["babador"],
    "berco": ["berço", "berco"],
    "carrinho": ["carrinho bebe", "carrinho bebê", "carrinho infantil", "carrinho"],
    "mordedor": ["mordedor"],
    "tapete_infantil": ["tapete infantil", "tapete de atividades", "tapete de atividades térmico"],
    "capacete": ["capacete"],
    "retrovisor": ["retrovisor"],
    "kit_relacao": ["kit relação", "kit relacao"],
    "escapamento": ["escapamento"],
    "pneu": ["pneu"],
    "pastilha": ["pastilha freio", "pastilha de freio"],
    "roupa_feminina": ["vestido", "saia", "blusa", "cropped", "shorts", "macacao", "macacão", "calça feminina"],
    "tenis_feminino": ["tenis feminino", "tênis feminino"],
    "tenis_masculino": ["tenis masculino", "tênis masculino"],
    "cueca": ["cueca"],
    "bolsa": ["bolsa"],
    "carteira": ["carteira"],
    "roupa_masculina": ["camisa masculina", "camiseta masculina", "bermuda masculina", "jaqueta masculina"],
}

ULTIMAS_BUSCAS_SHOPEE = []
ULTIMOS_TITULOS = []
usadas_abertura = set()
usadas_gatilho = set()
usados_no_ciclo = set()
BASES_VISTAS = set()
SUBCATEGORIAS_USADAS = set()
REJEICOES = Counter()

ESTADO_FILE = "estado_buscas.json"


def carregar_estado():
    try:
        if os.path.exists(ESTADO_FILE):
            with open(ESTADO_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return {"Moto": 0}


def salvar_estado(estado):
    try:
        with open(ESTADO_FILE, "w", encoding="utf-8") as f:
            json.dump(estado, f)
    except Exception as e:
        logging.error(f"Erro salvando estado: {e}")


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
FUSO_BR = ZoneInfo("America/Sao_Paulo")


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
    return " ".join(tokens[:5])


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
        if SequenceMatcher(None, t, prev).ratio() >= 0.86:
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
    except Exception:
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
    except Exception:
        return 0


def categoria_produto(titulo):
    t = normalizar_texto(titulo)

    for categoria, palavras in SUBCATEGORIAS.items():
        for palavra in palavras:
            if palavra in t:
                return categoria

    if "caixa" in t and "som" in t:
        return "caixa_som"
    if "aspirador" in t or "aspira" in t:
        return "aspirador"
    if "babador" in t:
        return "babador"

    return "outros"


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
        if titulo_duplicado_forte(titulo):
            return "duplicado_forte"
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


def produto_valido(p):
    return motivo_rejeicao(p) is None


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


def get_shopee_offers():
    global ULTIMAS_BUSCAS_SHOPEE, ULTIMOS_TITULOS, usados_no_ciclo, BASES_VISTAS, REJEICOES, SUBCATEGORIAS_USADAS

    logging.info("Buscando ofertas Shopee")
    usados_no_ciclo = set()
    BASES_VISTAS = set()
    SUBCATEGORIAS_USADAS = set()
    candidatos = []

    for nicho, cota in COTAS_POR_NICHO.items():
        try:
            produtos_brutos = []

            if nicho == "Moto":
                estado = carregar_estado()
                indice = estado.get("Moto", 0)
                kws_selecionadas = []
                for _ in range(4):
                    kws_selecionadas.append(MOTO_BUSCAS[indice % len(MOTO_BUSCAS)])
                    indice += 1
                estado["Moto"] = indice
                salvar_estado(estado)
            else:
                kws = KEYWORDS.get(nicho, [])
                kws = kws[:]
                random.shuffle(kws)
                kws_selecionadas = kws[:4] if len(kws) > 4 else kws

            for kw in kws_selecionadas:
                if len(produtos_brutos) >= 80:
                    break
                resultados = buscar_produtos_da_categoria_kw(kw, nicho)
                produtos_brutos.extend(resultados)

            logging.info(f"{nicho}: {len(produtos_brutos)} produtos brutos")

            filtrados = []
            rejeitados_local = Counter()

            for p in produtos_brutos:
                motivo = motivo_rejeicao(p)
                if motivo is None:
                    filtrados.append(p)
                else:
                    rejeitados_local[motivo] += 1
                    REJEICOES[motivo] += 1

            logging.info(f"{nicho}: {len(filtrados)} passaram no filtro")
            if rejeitados_local:
                logging.info(f"{nicho}: rejeições {dict(rejeitados_local)}")

            random.shuffle(filtrados)
            filtrados.sort(key=oferta_score, reverse=True)

            escolhidos = 0
            for escolhido in filtrados:
                if escolhidos >= cota:
                    break

                titulo = str(escolhido.get("productName", "")).strip()
                base = chave_base_titulo(titulo)
                link = escolhido.get("offerLink") or escolhido.get("productLink")
                cat = categoria_produto(titulo)

                if nicho != "Moto" and cat in SUBCATEGORIAS_USADAS:
                    logging.info(f"{nicho}: pulou categoria repetida -> {cat} ({titulo})")
                    continue

                if base and base in BASES_VISTAS:
                    logging.info(f"{nicho}: pulou por base repetida -> {titulo}")
                    continue

                if link and link not in usados_no_ciclo and link not in ULTIMAS_BUSCAS_SHOPEE:
                    candidatos.append(escolhido)
                    BASES_VISTAS.add(base)
                    SUBCATEGORIAS_USADAS.add(cat)
                    usados_no_ciclo.add(link)
                    ULTIMAS_BUSCAS_SHOPEE.append(link)
                    ULTIMOS_TITULOS.append(normalizar_texto(titulo))
                    escolhidos += 1

                    logging.info(f"{nicho}: escolhido {titulo} | categoria={cat}")

                    if len(ULTIMAS_BUSCAS_SHOPEE) > 300:
                        ULTIMAS_BUSCAS_SHOPEE.pop(0)
                    if len(ULTIMOS_TITULOS) > 150:
                        ULTIMOS_TITULOS.pop(0)

            if escolhidos < cota:
                logging.warning(f"{nicho}: só conseguiu {escolhidos}/{cota}")

        except Exception as e:
            logging.error(f"Erro no nicho {nicho}: {e}", exc_info=True)

    candidatos.sort(key=oferta_score, reverse=True)
    logging.info(f"Shopee OK: {len(candidatos[:MAX_OFERTAS])} produtos únicos para envio")
    return candidatos[:MAX_OFERTAS]


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

                vendas_f = f"{vendas:,}".replace(",", ".")
                preco_f = f"{preco:.2f}".replace(".", ",")

                msg = gerar_copy(nome, preco_f, vendas_f, rating, comissao, link, for_whatsapp=False)
                zap_msg = gerar_copy(nome, preco_f, vendas_f, rating, 0, link, for_whatsapp=True)
                zap = gerar_link_whatsapp_from_html(zap_msg)
                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

                selecionadas.append({"msg": msg, "img": img})

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
            app = (
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .build()
            )
            app.add_error_handler(error_handler)
            app.run_polling(allowed_updates=None)
        except Exception as e:
            logging.error(f"BOT REINICIANDO: {e}", exc_info=True)
            time.sleep(15)









        


