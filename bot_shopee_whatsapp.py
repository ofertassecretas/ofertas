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
from datetime import datetime, time as dttime
from zoneinfo import ZoneInfo
from urllib.parse import quote, urljoin
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO FINAL HIBRIDA ESTAVEL V26 - MAGALU AFILIADO/ML/SHOPEE")

TELEGRAMTOKEN = os.getenv("TELEGRAMTOKEN")
SHOPEEPASSWORD = os.getenv("SHOPEEPASSWORD")

MAGALUAPIKEY = os.getenv("MAGALUAPIKEY")
MAGALUAPIKEYID = os.getenv("MAGALUAPIKEYID")
MAGALUAPISECRET = os.getenv("MAGALUAPISECRET")

CHATIDDESTINO = -1003848415150
SHOPEEAPPID = 18349740277
AFILIADOID = 18349740277
SHOPEEGRAPHQLURL = "https://open-api.affiliate.shopee.com.br/graphql"

MAGALUONELINKID = "589508454"
MAGALUSTOREID = "07yuzqjf"
MAGALULOJAURL = "https://www.magazinevoce.com.br/magazineshopandreonline/"
MAGALUOFERTASURL = "https://www.magazinevoce.com.br/magazineshopandreonline/ofertas"

MLLISTAURL = "https://mercadolivre.com/sec167xbsR"
CHECKINTERVAL = 5400
FUSOBR = ZoneInfo("America/Sao_Paulo")

MAGALU_ENABLED = os.getenv("MAGALU_ENABLED", "1") == "1"
SHOPEE_ENABLED = os.getenv("SHOPEE_ENABLED", "1") == "1"
ML_ENABLED = os.getenv("ML_ENABLED", "1") == "1"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("debugbot.txt", encoding="utf-8")]
)

usadasabertura = set()

CACHEFILE = "cacheenvios.json"
MLLISTACACHEFILE = "mllistacache.json"
MAGALUCACHEFILE = "magalucache.json"

PREMIUMTERMOS = [
    "Smartphone", "Geladeira", "Smart TV", "Airfryer", "Notebook",
    "Lavadora", "Fogão", "Microondas", "Monitor Gamer"
]

MOTOSMODELOS = [
    "Titan 160", "Fazer 250", "XRE 300", "Biz 125", "Twister 250",
    "Factor 150", "PCX", "Lander 250", "CB300", "Tornado"
]

MOTOSPECAS = [
    "Kit Relação", "Pneu", "Capacete", "Jaqueta", "Farol",
    "Disco Freio", "Kit Cilindro", "Bateria", "Guidão", "Retrovisor"
]

def dentrodohorario():
    agora = datetime.now(FUSOBR).time()
    return dttime(5, 0) <= agora <= dttime(22, 0)

def carregarjson(path, default):
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logging.warning(f"Falha ao carregar {path}: {e}")
    return default

def salvarjson(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.warning(f"Falha ao salvar {path}: {e}")

cacheenvios = carregarjson(CACHEFILE, {"sent": []})
mllistacache = carregarjson(MLLISTACACHEFILE, {"items": [], "updated": 0})
magalucache = carregarjson(MAGALUCACHEFILE, {"items": [], "updated": 0})

def cachejaenviado(key):
    return key in cacheenvios["sent"]

def registrarenviado(key, maxitens=120):
    cacheenvios["sent"].append(key)
    cacheenvios["sent"] = cacheenvios["sent"][-maxitens:]
    salvarjson(CACHEFILE, cacheenvios)

def gerarcopy(nome, preco, vendas, avaliacao, comissao, link, origem):
    prefixos = {
        "shopee": "SHOPEE",
        "ml": "MERCADO LIVRE",
        "magalu": "MAGALU",
    }
    prefixo = prefixos.get(origem, "OFERTA")
    aberturas = [
        "Isso aqui no comum aparecer assim",
        "Achei isso aqui e fui conferir",
        "Isso aqui tá com cara de oportunidade",
        "Esse aqui tá chamando atenção de quem compra",
        "Para tudo e olha isso aqui",
        "Sério olha esse achado",
        "Isso aqui pode desaparecer rápido",
        "Pouca gente viu isso ainda",
    ]
    gatilho = random.choice([
        "Preço muito abaixo",
        "Avaliações acima da média",
        "Volume de vendas alto",
        "Custo-benefício forte",
    ])
    abertura = random.choice([a for a in aberturas if a not in usadasabertura]) if len(usadasabertura) < len(aberturas) else random.choice(aberturas)
    usadasabertura.add(abertura)

    msgtg = (
        f"<b>{prefixo}</b>\n"
        f"{abertura}\n"
        f"<b>{html.escape(str(nome))}</b>\n"
        f"{gatilho}\n"
        f"R$ {preco}\n"
        f"Avaliação: {avaliacao} | Vendas: {vendas}\n"
        f"Comissão: {comissao}%\n"
        f'<a href="{link}">COMPRAR AGORA</a>'
    )

    msgwa = (
        f"{prefixo} - {abertura}\n"
        f"{nome}\n"
        f"{gatilho}\n"
        f"R$ {preco}\n"
        f"Avaliação: {avaliacao} | Vendas: {vendas}\n"
        f"Comissão: {comissao}%\n"
        f"{link}"
    )
    return msgtg, msgwa

def gerarlinkwhatsapp(msgwa):
    return "https://wa.me/?text=" + quote(msgwa.strip())

def getpage(url, timeout=20, headers=None):
    headers = headers or {
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
    }
    r = requests.get(url, headers=headers, timeout=timeout)
    return r.text, r.url

def extractlinks(htmltext, baseurl):
    hrefs = re.findall(r'href=["\']([^"\']+)', htmltext, flags=re.I)
    out = []
    for href in hrefs:
        h = href.strip()
        if h.startswith("#") or h.startswith("javascript") or h.startswith("mailto"):
            continue
        full = urljoin(baseurl, h)
        low = full.lower()
        if any(x in low for x in ["mercadolivre.com", "mercadolivre.com.br", "magazinevoce.com.br", "/p/", "/produto/", "/ofertas", "/dp/"]):
            if full not in out:
                out.append(full)
    return out

def getshopeeoffers():
    if not SHOPEE_ENABLED:
        return []
    logging.info("Buscando Shopee...")
    timestamp = int(time.time())
    querybody = """
    query {
      productOfferV2(sortType: 2, limit: 10) {
        nodes {
          productName
          priceMin
          commissionRate
          sales
          ratingStar
          productLink
          imageUrl
        }
      }
    }
    """
    payload = json.dumps({"query": querybody})
    base = f"{SHOPEEAPPID}{timestamp}{payload}{SHOPEEPASSWORD}"
    signature = hashlib.sha256(base.encode()).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"SHA256 Credential={SHOPEEAPPID}, Timestamp={timestamp}, Signature={signature}",
    }
    try:
        r = requests.post(SHOPEEGRAPHQLURL, data=payload, headers=headers, timeout=20)
        nodes = r.json().get("data", {}).get("productOfferV2", {}).get("nodes", [])
        logging.info(f"Shopee itens brutos {len(nodes)}")
        return nodes
    except Exception as e:
        logging.warning(f"Shopee falhou: {e}")
        return []

def refreshmlcache():
    if not ML_ENABLED:
        return
    try:
        htmltext, finalurl = getpage(MLLISTAURL, timeout=20)
        links = extractlinks(htmltext, finalurl)
        logging.info(f"Links de ML encontrados na lista {len(links)}")
        items = []
        for l in links:
            if "mercadolivre" not in l.lower():
                continue
            itemid = hashlib.md5(l.encode()).hexdigest()
            items.append({
                "id": itemid,
                "nome": "Produto da sua lista ML",
                "preco": "0.00",
                "link": l,
                "img": "",
                "vendas": random.randint(50, 2000),
                "avaliacao": round(random.uniform(4.4, 5.0), 1),
                "origem": "ml",
                "comissao": 5,
            })
        mllistacache["items"] = items
        mllistacache["updated"] = int(time.time())
        salvarjson(MLLISTACACHEFILE, mllistacache)
    except Exception as e:
        logging.warning(f"Falha ao atualizar cache ML: {e}")

def getmlfromcache():
    if not ML_ENABLED:
        return []
    if not mllistacache["items"] or int(time.time()) - mllistacache.get("updated", 0) > 21600:
        refreshmlcache()
    items = list(mllistacache.get("items", []))
    random.shuffle(items)
    validos = [item for item in items if not cachejaenviado(item["id"])]
    logging.info(f"Itens válidos de ML no cache {len(validos)}")
    return validos

def getmldirecttermo(termo):
    if not ML_ENABLED:
        return []
    offset = random.randint(0, 40)
    logging.info(f"Buscando ML Direto termo {termo} Offset {offset}")
    try:
        url = f"https://api.mercadolibre.com/sites/MLB/search?q={quote(termo)}&limit=10&offset={offset}"
        r = requests.get(url, timeout=15)
        items = r.json().get("results", [])
        res = []
        for item in items:
            try:
                link = item.get("permalink")
                nome = item.get("title")
                preco = item.get("price")
                if not link or not nome or preco is None:
                    continue
                img = item.get("thumbnail") or ""
                res.append({
                    "id": str(item.get("id") or hashlib.md5(link.encode()).hexdigest()),
                    "nome": nome,
                    "preco": f"{float(preco):.2f}",
                    "link": link,
                    "img": img,
                    "vendas": int(item.get("sold_quantity") or random.randint(50, 500)),
                    "avaliacao": round(random.uniform(4.4, 5.0), 1),
                    "origem": "ml",
                    "comissao": 5,
                })
            except Exception:
                continue
        logging.info(f"ML direto itens válidos {len(res)}")
        return res
    except Exception as e:
        logging.warning(f"ML direto falhou: {e}")
        return []

def magalu_product_candidates_from_links(links):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://www.magazinevoce.com.br",
    }
    produtos = []
    for url in links:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            text = r.text

            title = ""
            img = ""
            price = ""

            m = re.search(r'"og:title"\s*content="([^"]+)"', text, re.I)
            if m:
                title = m.group(1).strip()

            if not title:
                m = re.search(r"<title>(.*?)</title>", text, re.I | re.S)
                if m:
                    title = re.sub(r"\s+", " ", m.group(1)).strip()

            m = re.search(r'"og:image"\s*content="([^"]+)"', text, re.I)
            if m:
                img = m.group(1).strip()

            m = re.search(r'"price"\s*:\s*"?(.*?)"?[,}]', text, re.I)
            if m:
                price = m.group(1).strip()

            if not price:
                m = re.search(r'"salesPrice"\s*:\s*(\d+(?:\.\d+)?)', text, re.I)
                if m:
                    price = f"{float(m.group(1)):.2f}"

            if not title:
                continue

            if not price:
                price = "0.00"

            produtoid = hashlib.md5(url.encode()).hexdigest()
            produtos.append({
                "id": produtoid,
                "nome": title,
                "preco": price if isinstance(price, str) else f"{float(price):.2f}",
                "link": url,
                "img": img,
                "vendas": random.randint(50, 5000),
                "avaliacao": round(random.uniform(4.5, 5.0), 1),
                "origem": "magalu",
                "comissao": 4,
            })
        except Exception as e:
            logging.info(f"Falha ao ler produto Magalu {url}: {e}")
    return produtos

def getmagaluoffers():
    if not MAGALU_ENABLED:
        return []
    logging.info("Buscando Magalu...")
    termos = list(PREMIUMTERMOS)
    random.shuffle(termos)

    links_coletados = []
    for base in [MAGALULOJAURL, MAGALUOFERTASURL]:
        try:
            htmltext, finalurl = getpage(base, timeout=20)
            links = extractlinks(htmltext, finalurl)
            for l in links:
                low = l.lower()
                if "magazinevoce.com.br/magazineshopandreonline" in low or "onelink.me/589508454" in low:
                    if l not in links_coletados:
                        links_coletados.append(l)
        except Exception as e:
            logging.info(f"Falha lendo base Magalu {base}: {e}")

    if not links_coletados:
        for termo in termos[:3]:
            try:
                q = quote(termo)
                urls = [
                    f"https://www.magazinevoce.com.br/magazineshopandreonline/busca/{q}/",
                    f"https://www.magazinevoce.com.br/magazineshopandreonline/ofertas/",
                    f"https://www.magazineluiza.com.br/busca/{q}/",
                ]
                for url in urls:
                    htmltext, finalurl = getpage(url, timeout=20)
                    links = extractlinks(htmltext, finalurl)
                    for l in links:
                        low = l.lower()
                        if "magazinevoce.com.br/magazineshopandreonline" in low or "onelink.me/589508454" in low:
                            if l not in links_coletados:
                                links_coletados.append(l)
            except Exception as e:
                logging.info(f"Busca Magalu por termo falhou {termo}: {e}")

    produtos = magalu_product_candidates_from_links(links_coletados)
    if produtos:
        logging.info(f"Produtos Magalu válidos {len(produtos)}")
        magalucache["items"] = produtos
        magalucache["updated"] = int(time.time())
        salvarjson(MAGALUCACHEFILE, magalucache)
        return produtos

    try:
        if magalucache.get("items"):
            logging.info("Usando cache Magalu")
            return [x for x in magalucache["items"] if not cachejaenviado(x["id"])]
    except Exception:
        pass

    return []

def escolheritemsemrepetir(items, prefixocache):
    if not items:
        return None
    for item in items:
        key = prefixocache + ":" + (item.get("id") or hashlib.md5(item.get("link", "").encode()).hexdigest())
        if not cachejaenviado(key):
            registrarenviado(key)
            return item
    return None

async def sendofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not dentrodohorario():
            logging.info("Fora do horario permitido.")
            return

        usadasabertura.clear()
        totallista = []

        if SHOPEE_ENABLED:
            shopee = getshopeeoffers()
            shopeevalidos = 0
            for i in shopee[:2]:
                try:
                    l = i.get("productLink")
                    if not l:
                        continue
                    if AFILIADOID and str(AFILIADOID) not in l:
                        sep = "&" if "?" in l else "?"
                        l = f"{l}{sep}af_siteid={AFILIADOID}"
                    comis = round(float(i.get("commissionRate", 0)) / 100, 2)
                    msgtg, msgwa = gerarcopy(
                        html.escape(i.get("productName", "")),
                        f"{float(i.get('priceMin', 0)):.2f}",
                        int(i.get("sales") or 0),
                        float(i.get("ratingStar") or 4.5),
                        comis,
                        l,
                        "shopee",
                    )
                    totallista.append({
                        "msgtg": msgtg,
                        "msgwa": msgwa,
                        "img": i.get("imageUrl"),
                        "link": l,
                        "origem": "shopee",
                    })
                    shopeevalidos += 1
                except Exception as e:
                    logging.warning(f"Shopee item inválido: {e}")
            logging.info(f"Shopee itens válidos {shopeevalidos}")

        if MAGALU_ENABLED:
            magaluitems = getmagaluoffers()
            if not magaluitems:
                termomagalu = random.choice(PREMIUMTERMOS)
                magaluitems = getmagaluoffers()
                logging.info(f"Magalu candidatos {len(magaluitems)}")
            i = escolheritemsemrepetir(magaluitems, "magalu")
            if i and i.get("preco") != "0.00" and i.get("nome") and i.get("link"):
                msgtg, msgwa = gerarcopy(
                    html.escape(i["nome"]),
                    i["preco"],
                    i["vendas"],
                    i["avaliacao"],
                    i["comissao"],
                    i["link"],
                    "magalu",
                )
                totallista.append({
                    "msgtg": msgtg,
                    "msgwa": msgwa,
                    "img": i.get("img"),
                    "link": i["link"],
                    "origem": "magalu",
                })
                logging.info("Magalu adicionado ao envio.")
            else:
                logging.info("Magalu descartado por campos inválidos.")

        if ML_ENABLED:
            mlitems = getmlfromcache()
            if not mlitems:
                termomoto = random.choice(MOTOSPECAS) + " " + random.choice(MOTOSMODELOS)
                mlitems = getmldirecttermo(termomoto)
            if not mlitems:
                termomlp = random.choice(PREMIUMTERMOS)
                mlitems = getmldirecttermo(termomlp)
            logging.info(f"ML candidatos após fallback {len(mlitems)}")
            i = escolheritemsemrepetir(mlitems, "ml")
            if i and i.get("preco") != "0.00" and i.get("nome") and i.get("link"):
                msgtg, msgwa = gerarcopy(
                    html.escape(i["nome"]),
                    i["preco"],
                    i["vendas"],
                    i["avaliacao"],
                    i["comissao"],
                    i["link"],
                    "ml",
                )
                totallista.append({
                    "msgtg": msgtg,
                    "msgwa": msgwa,
                    "img": i.get("img"),
                    "link": i["link"],
                    "origem": "ml",
                })
                logging.info("ML adicionado ao envio.")
            else:
                logging.info("ML descartado por campos inválidos.")

        logging.info(f"totallista final {len(totallista)}")

        if not totallista:
            logging.info("Nenhuma oferta válida encontrada nesta rodada.")
            return

        await context.bot.send_message(chat_id=CHATIDDESTINO, text="OFERTAS NOVAS CHEGANDO...")
        await asyncio.sleep(5)

        for item in totallista:
            try:
                zaplink = gerarlinkwhatsapp(item["msgwa"])
                fullmsg = item["msgtg"] + f'\n<a href="{zaplink}">Compartilhar no WhatsApp</a> <b>Ofertas Secretas</b>'
                if item.get("img"):
                    await context.bot.send_photo(chat_id=CHATIDDESTINO, photo=item["img"], caption=fullmsg, parse_mode="HTML")
                else:
                    await context.bot.send_message(chat_id=CHATIDDESTINO, text=fullmsg, parse_mode="HTML", disable_web_page_preview=True)
                await asyncio.sleep(45)
            except Exception as e:
                logging.error(f"Erro ao enviar item: {e}")

    except Exception as e:
        logging.error(f"ERRO CRITICO: {e}")

async def postinit(app):
    app.job_queue.run_repeating(sendofertas, interval=CHECKINTERVAL, first=10)
    logging.info("BOT V26 ATIVADO")

if __name__ == "__main__":
    while True:
        try:
            app = ApplicationBuilder().token(TELEGRAMTOKEN).post_init(postinit).build()
            app.run_polling()
        except Exception as e:
            logging.error(f"Falha geral no app: {e}")
            time.sleep(15)
        


