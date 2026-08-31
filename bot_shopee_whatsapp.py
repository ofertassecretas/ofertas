import asyncio, requests, logging, random, hashlib, time, json, os, html, re, tempfile
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder

print("VERSAO V37-ERROS-CORRIGIDOS")
# =========================
# CONFIG
# =========================
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "").strip()
SHOPEE_APP_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
FREE_CHAT_ID = -1003886228244
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"

CHECK_INTERVAL = 5400
MAX_OFERTAS = 10
MIN_OFERTAS = 4
HISTORICO_DIAS = 3
SIMILARIDADE_MAX = .88
VENDAS_MIN = 2
RATING_MIN = 4.0
PRECO_MIN = 15
PRECO_MAX = 10000
COMISSAO_MIN = .03
VERSAO_RODIZIO = 37
LIMITE_POR_FAMILIA = 2
MAX_PAGINA_BUSCA = 4
TIPOS_ORDEM = [1, 2, 3, 4, 5]

FUSO_BR = ZoneInfo("America/Sao_Paulo")
ARQUIVO_ESTADO = "estado_buscas.json"
ARQUIVO_HISTORICO = "historico_envios.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ✅ DECLAREI AS VARIÁVEIS QUE ESTAVAM FALTANDO!
ULTIMOS_LINKS = []
ULTIMOS_TITULOS = []
ABERTURAS_USADAS = set()
GATILHOS_USADAS = set()  # ✅ FALTAVA ESSA!
LINKS_CICLO_ATUAL = set()
TERMOS_USADOS_CICLO = set()
BASES_VISTAS = set()

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
    variacoes = [base, f"{base} promocao", f"{base} oferta"]
    return random.choice(variacoes)

GRUPO_SINONIMOS = {
    "smartwatch": {"smartwatch", "relogio inteligente"},
    "airfryer": {"air fryer", "fritadeira sem oleo", "fritadeira eletrica"},
    "fone": {"fone bluetooth", "fone ouvido", "fone sem fio"},
    "caixa_som": {"caixa de som", "alto falante"},
    "tv": {"smart tv", "televisao", "tv led"},
    "notebook": {"notebook", "laptop"},
    "tablet": {"tablet"},
    "celular": {"celular", "smartphone"}
}
MAPA_SINONIMOS = {normalizar(t): g for g, ts in GRUPO_SINONIMOS.items() for t in ts}

def termo_ja_usado(termo):
    g = MAPA_SINONIMOS.get(normalizar(termo))
    return bool(g and any(MAPA_SINONIMOS.get(normalizar(t)) == g for t in TERMOS_USADOS_CICLO))

# =========================
# LISTAS DE PRODUTOS E MOTO — ✅ USANDO LISTA DO CÓDIGO ANTIGO
# =========================
PECAS_MOTO = [
    "kit relacao","kit embreagem","bateria","refil bomba combustivel",
    "chicote fiação principal","bucha balança","burrinho de freio",
    "estribo","pedal de marcha","pedal de freio","rolamento virabrequim",
    "estator","chave ignição","punho chave luz","kit pisca seta",
    "par pneu","bloco optico","retentor de bengala","bucha amortecedor",
    "carburador corpo de injeção","kit cilindro","jogo de juntas","biela",
    "valvulas escape admissão","kit freio a disco","disco de freio",
    "tubo interno","vela iridium","pastilha freio","guidao","manopla",
    "amortecedor","retrovisor","farol","lona de freio","cabo embreagem",
    "cabo acelerador","coroa moto","pinhao moto","corrente moto",
    "pedaleira","carenagem","lanterna traseira","capacete"
]
MOTOS = [
    "titan 150","cb 300","factor 150","titan 160","tornado 250","fazer 150",
    "titan 125","bros 160","twister 250","biz 125","pop 110","xre 300",
    "crosser 150","xre 190","fazer 250","lander 250","bros 150",
    "tenere 250","biz 100","twister 300"
]

PRODUTOS_POR_NICHO = {
    "Casa":["air fryer","aspirador","liquidificador","cafeteira","panela eletrica","panela de pressão","ventilador","batedeira","filtro de barro","jogo de panelas"],
    "Maternidade":["carrinho bebe","berco bebe","fralda descartavel","naninha","kit toalha umedecida","banheira","kit bolsa maternidade","kit mamadeira","ninho bebe","kit enxoval bebe"],
    "Eletroeletrônicos":["smartwatch","fone bluetooth","caixa de som bluetooth","bastão pau de selfie","celular","smart tv","video game","capinha celular","pelicula celular","balança digital","pen drive","impressora termica","computador","notebook","drone","camera de segurança","tablet","ssd","mouse gamer","teclado mecanico","power bank","carregador turbo"],
    "Moda feminina":["vestido feminino","conjunto feminino","biquines","saida de praia","maquiagens","roupa academia","calça jean","calça leggin","saia longa","sandalias","pijamas","blusa regata","oculos de sol","tenis feminino","bolsa feminina","jaqueta feminina","short feminino"],
    "Moda masculina":["camiseta masculina","bermudas jeans","camisetas regatas","camisa polo","camisa de linho","terno","blazer","barbeador","oculos de sol","calção de futebol","tenis futebol","chuteiras","camisa termica","bermuda masculina","jaqueta masculina","tenis masculino","carteira masculina","calça jeans masculina","camisa social masculina","moletom masculino","sapatenis masculino"]
}

NICHOS_FREE_ROTA = ["Moto", "Casa", "Moda feminina", "Moda masculina", "Maternidade", "Eletroeletrônicos"]

FAMILIAS_PRODUTOS = {
    "air_fryer": ["air fryer", "fritadeira"],
    "fone_bluetooth": ["fone bluetooth", "fone ouvido", "fone sem fio"],
    "smartwatch": ["smartwatch", "relogio inteligente"],
    "caixa_som": ["caixa de som", "alto falante"],
    "tv": ["smart tv", "televisao", "tv"],
    "notebook": ["notebook", "laptop"],
    "tablet": ["tablet"],
    "celular": ["celular", "smartphone"],
    "bebe": ["bebe", "infantil", "carrinho", "berco", "mamadeira", "ninho"],
    "moda_fem": ["vestido", "conjunto", "saia", "bolsa", "sandalia", "tenis feminino", "body"],
    "moda_masc": ["camisa", "camiseta", "calca", "tenis masculino", "jaqueta", "bermuda"],
    "casa_lar": ["panela", "aspirador", "liquidificador", "cafeteira", "ventilador", "batedeira"],
    "moto_geral": ["kit relacao", "embreagem", "pneu", "disco freio", "pastilha freio", "bateria", "vela"]
}

# =========================
# ROTAÇÃO DE MOTO — ✅ CORRIGIDA PARA USAR NOMES CORRETOS
# =========================
def gerar_par_moto(indice_ciclo):
    peca = PECAS_MOTO[indice_ciclo % len(PECAS_MOTO)]
    deslocamento = (indice_ciclo // len(PECAS_MOTO)) % len(MOTOS)
    m1_idx = deslocamento % len(MOTOS)
    m2_idx = (m1_idx + 1 + random.randint(1, len(MOTOS)-2)) % len(MOTOS)
    moto1 = MOTOS[m1_idx]
    moto2 = MOTOS[m2_idx]
    logging.info("🏍️ Peça: [%s] | Moto 1: [%s] | Moto 2: [%s]", peca, moto1, moto2)
    return peca, moto1, moto2

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
        logging.error("Erro salvar %s: %s", caminho, e)

def carregar_json(caminho, padrao):
    try:
        if not os.path.exists(caminho): return padrao
        with open(caminho, "r", encoding="utf-8") as arq:
            return json.load(arq)
    except Exception as e:
        logging.error("Erro ler %s: %s", caminho, e)
        return padrao

def carregar_estado():
    estado = carregar_json(ARQUIVO_ESTADO, {})
    if estado.get("versao_rodizio") != VERSAO_RODIZIO:
        hoje = datetime.now(FUSO_BR).strftime("%Y%m%d")
        estado = {
            "versao_rodizio": VERSAO_RODIZIO,
            "ciclo_moto": 0,
            "pares_moto_usados": [],
            "free_nicho_idx": 0,
            "Moto": {"data_rodizio": hoje, "idx": 0}
        }
        for nicho in PRODUTOS_POR_NICHO:
            estado[nicho] = {"pos": 0, "data_rodizio": hoje}
    return estado

def salvar_estado(estado): salvar_json(ARQUIVO_ESTADO, estado)
def carregar_historico(): return carregar_json(ARQUIVO_HISTORICO, {})
def salvar_historico(dados): salvar_json(ARQUIVO_HISTORICO, dados)

# =========================
# ROTAÇÃO DE BUSCAS
# =========================
def proxima_busca_moto(estado):
    estado["ciclo_moto"] = estado.get("ciclo_moto", 0) + 1
    peca, moto1, moto2 = gerar_par_moto(estado["ciclo_moto"])
    
    par_atual = f"{peca}-{moto1}-{moto2}"
    tentativas = 0
    while par_atual in estado.get("pares_moto_usados", []) and tentativas < 20:
        estado["ciclo_moto"] += 1
        peca, moto1, moto2 = gerar_par_moto(estado["ciclo_moto"])
        par_atual = f"{peca}-{moto1}-{moto2}"
        tentativas += 1
    
    if "pares_moto_usados" not in estado: estado["pares_moto_usados"] = []
    estado["pares_moto_usados"].append(par_atual)
    estado["pares_moto_usados"] = estado["pares_moto_usados"][-50:]
    
    return peca, moto1, moto2, estado

def proximo_termo(nicho, estado):
    itens = PRODUTOS_POR_NICHO[nicho]
    c = estado[nicho]
    for _ in range(len(itens)):
        t = itens[c["pos"] % len(itens)]
        c["pos"] += 1
        if termo_ja_usado(t):
            logging.info("🛑 Pulado: %s", t)
            continue
        TERMOS_USADOS_CICLO.add(t)
        return t, estado
    return itens[c["pos"] % len(itens)], estado

# =========================
# FILTROS — ✅ IGUAIS AO CÓDIGO ANTIGO
# =========================
def chave_titulo(titulo):
    stop = {"premium","novo","promocao","promoção","super","original","profissional","casual","masculino","feminino","infantil","adulto","unissex","kit","com","de","para","o","a","promo","oferta","modelo","versao","versão","linha","envio","usado","branco","preto","azul","vermelho","rosa","verde","amarelo","tamanho","gamer","led","usb"}
    p = [x for x in normalizar(titulo).split() if x not in stop and len(x) > 2]
    return " ".join(sorted(p)[:8])

def tem_bloqueio(t):
    t = normalizar(t)
    return any(x in t for x in ["teste","amostra","não compre","nao compre","produto teste","exemplo","dummy","vela led","vela decorativa","decorativa","decoração","casamento","festa"])

def duplicata_forte(titulo):
    n, b = normalizar(titulo), chave_titulo(titulo)
    return any(n == normalizar(p) or SequenceMatcher(None, n, normalizar(p)).ratio() >= SIMILARIDADE_MAX or (b and b == chave_titulo(p)) for p in ULTIMOS_TITULOS)

def enviado_anteriormente(chave):
    h = carregar_historico()
    if chave not in h: return False
    try:
        d = datetime.fromisoformat(h[chave])
        if d.tzinfo is None: d = d.replace(tzinfo=FUSO_BR)
        return datetime.now(FUSO_BR) - d < timedelta(days=HISTORICO_DIAS)
    except: return False

def registrar_envio(chave):
    h = carregar_historico(); h[chave] = datetime.now(FUSO_BR).isoformat()
    limite = datetime.now(FUSO_BR) - timedelta(days=HISTORICO_DIAS*3)
    salvar_historico({k:v for k,v in h.items() if datetime.fromisoformat(v).replace(tzinfo=FUSO_BR) >= limite})

def identificar_familia(titulo):
    nt = normalizar(titulo)
    for f, ps in FAMILIAS_PRODUTOS.items():
        if any(normalizar(p) in nt for p in ps): return f
    return "outros"

def pontuar_produto(p, termo=""):
    try:
        v = int(p.get("sales", 0) or 0)
        r = float(p.get("ratingStar", 0) or 0)
        c = float(p.get("commissionRate", 0) or 0)
        pr = float(p.get("priceMin", 0) or 0)
        n = normalizar(p.get("productName",""))
        tn = normalizar(termo)
        s = min(v/8, 25) + r*3 + c*100
        if 50 <= pr <= 5000: s += 6
        if tn: s += 8 if tn in n else sum(2 for x in tn.split() if x in n)
        return s
    except: return 0

def avaliar_rejeicao(p):
    titulo = str(p.get("productName","")).strip()
    link = str(p.get("offerLink") or p.get("productLink","")).strip()
    try:
        preco_str = p.get("priceMin", "0") or "0"
        preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
    except: preco = 0
    try: comissao = float(p.get("commissionRate", "0") or 0)
    except: comissao = 0
    vendas = int(p.get("sales", 0) or 0)
    nota = float(p.get("ratingStar", 0) or 0)
    if not titulo: return "sem_titulo"
    if not link: return "sem_link"
    if tem_bloqueio(titulo): return "bloqueado"
    if preco < PRECO_MIN: return "preco_baixo"
    if preco > PRECO_MAX: return "preco_alto"
    if comissao < COMISSAO_MIN: return "comissao_baixa"
    if vendas > 0 and vendas < VENDAS_MIN: return "vendas_baixas"
    if nota > 0 and nota < RATING_MIN: return "nota_baixa"
    if link in LINKS_CICLO_ATUAL or link in ULTIMOS_LINKS: return "link_repetido"
    return None

# =========================
# BUSCA API
# =========================
def buscar_produtos(termo, nicho):
    logging.info("🔍 Buscando em %s: %s", nicho, termo)
    ts = int(time.time())
    ordem = random.choice(TIPOS_ORDEM)
    pagina = random.randint(1, MAX_PAGINA_BUSCA)
    termo_busca = variar_termo(termo)
    logging.info("   ↳ Ordem=%s | Página=%s | Buscando: %s", ordem, pagina, termo_busca)
    q = f'query {{productOfferV2(sortType:{ordem},page:{pagina},limit:50,keyword:{json.dumps(termo_busca,ensure_ascii=False)},isAMSOffer:true){{nodes{{productName,priceMin,priceMax,commissionRate,sales,ratingStar,productLink,offerLink,imageUrl,shopType}}}}}}'
    payload = json.dumps({"query":q}, ensure_ascii=False)
    assinatura = hashlib.sha256(f"{SHOPEE_APP_ID}{ts}{payload}{SHOPEE_PASSWORD}".encode()).hexdigest()
    cab = {"Content-Type":"application/json","Authorization":f"SHA256 Credential={SHOPEE_APP_ID},Timestamp={ts},Signature={assinatura}","User-Agent":"Mozilla/5.0"}
    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload.encode("utf-8"), headers=cab, timeout=25)
        r.raise_for_status()
        d = r.json()
        if d.get("errors"): logging.error("API Erro: %s", d["errors"]); return []
        p = (d.get("data",{}).get("productOfferV2",{}).get("nodes") or [])
        logging.info("✅ %s produtos encontrados", len(p))
        return p
    except Exception as e:
        logging.error("❌ Falha busca: %s", e); return []

# =========================
# SELECIONAR
# =========================
def selecionar(nicho, termo, qtd, estado, moto=False, peca=None):
    tcompleto = f"{peca} {termo}" if moto else termo
    res = buscar_produtos(tcompleto, nicho)
    val = []; motivos = Counter()
    for p in res:
        m = avaliar_rejeicao(p)
        if m: motivos[m] += 1
        else: val.append(p)
    logging.info("📊 %s: %s brutos / %s válidos", nicho, len(res), len(val))
    
    if val:
        val.sort(key=lambda x: pontuar_produto(x, termo), reverse=True)
    
    esc = []; familias = Counter()
    for p in val:
        if len(esc) >= qtd: break
        titulo = str(p.get("productName","")).strip()
        link = str(p.get("offerLink") or p.get("productLink","")).strip()
        ch = chave_titulo(titulo)
        fam = identificar_familia(titulo)
        hid = hashlib.md5(f"{ch}|{link}".encode()).hexdigest()
        if duplicata_forte(titulo): continue
        if familias[fam] >= LIMITE_POR_FAMILIA: continue
        if enviado_anteriormente(hid): continue
        esc.append(p); familias[fam] += 1
        LINKS_CICLO_ATUAL.add(link); ULTIMOS_LINKS.append(link); ULTIMOS_TITULOS.append(titulo)
        BASES_VISTAS.add(ch)
        registrar_envio(hid)
        logging.info("🏆 Selecionado: %s | %s", titulo[:50], fam)
    del ULTIMOS_LINKS[:-300]; del ULTIMOS_TITULOS[:-150]
    if motivos: logging.info("📋 Excluídos: %s", dict(motivos))
    return esc, estado

# =========================
# COLETAR OFERTAS
# =========================
def obter_ofertas_shopee():
    global LINKS_CICLO_ATUAL, TERMOS_USADOS_CICLO, BASES_VISTAS
    LINKS_CICLO_ATUAL.clear(); TERMOS_USADOS_CICLO.clear(); BASES_VISTAS.clear()
    sel = []
    estado = carregar_estado()
    
    # 🏍️ MOTO — 2 modelos
    peca, moto1, moto2, estado = proxima_busca_moto(estado)
    its1, estado = selecionar("Moto", moto1, 1, estado, True, peca)
    sel.extend([("Moto", x) for x in its1])
    its2, estado = selecionar("Moto", moto2, 1, estado, True, peca)
    sel.extend([("Moto", x) for x in its2])
    
    # DEMAIS NICHOS
    cotas = {"Casa":2,"Maternidade":2,"Eletroeletrônicos":2,"Moda feminina":1,"Moda masculina":1}
    for nicho, qtd in cotas.items():
        for _ in range(qtd):
            t, estado = proximo_termo(nicho, estado)
            its, estado = selecionar(nicho, t, 1, estado)
            sel.extend([(nicho, x) for x in its])
    
    salvar_estado(estado)
    sel.sort(key=lambda x: pontuar_produto(x[1], x[0]), reverse=True)
    logging.info("✅ Total: %s | Enviando: %s/%s", len(sel), min(len(sel),MAX_OFERTAS), MAX_OFERTAS)
    return sel[:MAX_OFERTAS], estado

# =========================
# FORMATAR EXIBIÇÃO
# =========================
def formatar_vendas(vendas):
    if vendas == 0: return "0"
    return f"{vendas:,}".replace(",",".")

def formatar_nota(nota):
    if nota == 0: return "Sem nota"
    return f"{nota:.1f}".replace(".",",")

# =========================
# MENSAGENS — SEM COMISSÃO, SEM AFILIADO
# =========================
ABERTURAS = [
    "🚨 Isso não aparece todo dia!","👀 Olha o que encontrei…","🔥 Aproveita enquanto dá!",
    "🛑 Para e olha!","🤯 Difícil achar barato assim!","⚠️ Pode sumir a qualquer hora…",
    "📉 Caiu de preço!","🚀 Tá bombando!"
]
GATILHOS = [
    "Bem abaixo do preço normal","Avaliações excelentes","Muita gente comprando",
    "Custo-benefício ótimo","Quem compra recomenda","Produto confiável","Saindo rápido"
]
CHAMADAS = [
    "👇 Corre antes que acabe!","⚡ Clique antes de aumentar!","🚀 Estoque limitado!",
    "💥 Oportunidade!","🎯 Compre antes dos outros!","⏰ Acaba hoje!","💰 Economia real!","🛒 Não perca!"
]

def anexar_afiliado(link):
    try: u=urlparse(link); p=parse_qs(u.query); p["af_siteid"]=AFILIADO_ID; return urlunparse(u._replace(query=urlencode(p,doseq=True)))
    except: return link

def link_whatsai_completo(nome, preco, vendas, nota, link):
    texto = (
        f"🔥 Produto: {nome}\n"
        f"💰 Preço: R$ {preco}\n"
        f"📊 Vendas: {vendas}\n"
        f"⭐ Avaliação: {nota}\n\n"
        f"🛒 Comprar: {link}\n\n"
        f"👥 Grupo de ofertas: {LINK_GRUPO_OFERTAS}"
    )
    return f"https://wa.me/?text={quote(re.sub(r'<[^>]+>','',texto))}"

def montar_mensagem_telegram(nome, preco, vendas, nota, link, lk_whats, free=False):
    # ✅ GATILHOS_USADAS AGORA EXISTE!
    ab = random.choice([x for x in ABERTURAS if x not in ABERTURAS_USADAS] or ABERTURAS)
    gt = random.choice([x for x in GATILHOS if x not in GATILHOS_USADAS] or GATILHOS)
    ch = random.choice(CHAMADAS)
    ABERTURAS_USADAS.add(ab); GATILHOS_USADAS.add(gt)
    etiqueta = "🎁 OFERTA DESTAQUE" if free else ""
    
    # ✅ SEM COMISSÃO + ESPAÇO ENTRE BOTÕES
    return (
        f"{etiqueta}\n\n" if etiqueta else ""
        f"{html.escape(ab)}\n\n"
        f"🔥 <b>Produto:</b> {html.escape(nome)}\n\n"
        f"💰 <b>Preço:</b> R$ {preco}\n"
        f"📊 <b>Vendas:</b> {vendas}\n"
        f"⭐ <b>Avaliação:</b> {nota}\n\n"
        f"{html.escape(gt)}\n\n"
        f"{html.escape(ch)}\n\n"
        f'<a href="{html.escape(link)}">🛒 COMPRAR AGORA</a>\n\n'
        f'<a href="{lk_whats}">📲 Compartilhar WhatsApp</a>\n\n'
        f'<a href="{LINK_GRUPO_OFERTAS}">👥 Grupo de ofertas</a>'
    )

# =========================
# ENVIO
# =========================
async def enviar_msg(ctx, txt, img, cid):
    try: await ctx.bot.send_photo(cid, photo=img, caption=txt, parse_mode="HTML"); return True
    except Exception as e: logging.warning("⚠️ Foto: %s", e)
    try: await ctx.bot.send_message(cid, text=txt, parse_mode="HTML"); return True
    except Exception as e: logging.error("❌ Erro envio: %s", e); return False

async def ciclo(ctx):
    try:
        logging.info("========== 🔄 INÍCIO ==========")
        if not horario_valido(): logging.info("⏹️ Fora do horário"); return
        ABERTURAS_USADAS.clear(); GATILHOS_USADAS.clear()
        
        ofertas, estado = obter_ofertas_shopee()
        
        if len(ofertas) < MIN_OFERTAS:
            logging.warning("⚠️ Apenas %s ofertas. Mínimo %s exigido. Ciclo pulado.", len(ofertas), MIN_OFERTAS)
            return
        
        # ENVIAR VIP
        await ctx.bot.send_message(CHAT_ID_DESTINO, text="🚨 <b>OFERTAS NOVAS CHEGARAM!</b>", parse_mode="HTML")
        await asyncio.sleep(5)
        
        enviados = []
        for nicho, p in ofertas:
            try:
                titulo = str(p.get("productName","")).strip()
                lb = str(p.get("offerLink") or p.get("productLink","")).strip()
                if not titulo or not lb: continue
                link = anexar_afiliado(lb)
                try:
                    preco_str = p.get("priceMin", "0") or "0"
                    preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
                except: preco = 0
                vendas = formatar_vendas(int(p.get("sales", 0) or 0))
                nota = formatar_nota(float(p.get("ratingStar", 0) or 0))
                img = str(p.get("imageUrl","")).strip()
                prc = f"{preco:.2f}".replace(".",",")
                lk_whats = link_whatsai_completo(titulo, prc, vendas, nota, link)
                msg = montar_mensagem_telegram(titulo, prc, vendas, nota, link, lk_whats)
                hid = hashlib.md5(f"{chave_titulo(titulo)}|{lb}".encode()).hexdigest()
                enviados.append({"msg":msg,"img":img,"hid":hid,"nicho":nicho})
            except Exception as e: logging.error("❌ Montagem: %s", e)
        
        for item in enviados:
            logging.info("📤 Enviando VIP: %s", item["nicho"])
            ok = await enviar_msg(ctx, item["msg"], item["img"], CHAT_ID_DESTINO)
            if ok: registrar_envio(item["hid"])
            await asyncio.sleep(40)
        
        # 🆓 ENVIAR FREE — ESCOLHE NICHO POR ROTAÇÃO
        logging.info("========== 🆓 BLOCO GRATUITO ==========")
        idx_free = estado.get("free_nicho_idx", 0)
        nicho_free = NICHOS_FREE_ROTA[idx_free % len(NICHOS_FREE_ROTA)]
        estado["free_nicho_idx"] = (idx_free + 1) % len(NICHOS_FREE_ROTA)
        salvar_estado(estado)
        
        oferta_free = next((x for x in enviados if x["nicho"] == nicho_free), None)
        
        if oferta_free:
            logging.info("🎁 Enviando oferta FREE do nicho: %s", nicho_free)
            await ctx.bot.send_message(FREE_CHAT_ID, text="🎁 <b>OFERTA DESTAQUE DA SEMANA!</b>", parse_mode="HTML")
            await asyncio.sleep(3)
            ok = await enviar_msg(ctx, oferta_free["msg"], oferta_free["img"], FREE_CHAT_ID)
            if ok: registrar_envio(oferta_free["hid"]); logging.info("✅ Oferta FREE enviada!")
            else: logging.warning("⚠️ Falha ao enviar FREE")
        else:
            logging.warning("⚠️ Sem oferta disponível para o nicho FREE: %s", nicho_free)
        
        logging.info("========== ✅ CICLO FINALIZADO ==========")
    except Exception as e: logging.error("❌ ERRO CICLO: %s", e, exc_info=True)

async def loop(app):
    ult = 0
    while True:
        agora = time.time()
        if agora - ult >= CHECK_INTERVAL:
            await ciclo(type("Ctx",(),{"bot":app.bot})())
            ult = agora
        await asyncio.sleep(60)

async def manter_vivo():
    while True: logging.info("💓 Ativo | %s", datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M")); await asyncio.sleep(300)

async def principal():
    if not TELEGRAM_TOKEN or not SHOPEE_PASSWORD or not SHOPEE_APP_ID:
        raise RuntimeError("Defina TELEGRAM_TOKEN, SHOPEE_PASSWORD e SHOPEE_APP_ID")
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    logging.info("🤖 Bot pronto!")
    asyncio.create_task(manter_vivo())
    await loop(app)

def iniciar():
    try: asyncio.run(principal())
    except Exception as e: logging.error("🔄 Reiniciando em 15s: %s", e); time.sleep(15); iniciar()

if __name__ == "__main__": iniciar()
