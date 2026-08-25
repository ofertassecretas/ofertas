import asyncio,requests,logging,random,hashlib,time,json,os,html,re,tempfile
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime,time as dt_time,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse,parse_qs,urlencode,urlunparse,quote
from telegram.ext import ApplicationBuilder

print("VERSAO V29-ROTACAO-ALTERNADA")

# =========================
# CONFIG
# =========================
TELEGRAM_TOKEN=(os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD=os.getenv("SHOPEE_PASSWORD","").strip()
CHAT_ID_DESTINO=-1003848415150
FREE_CHAT_ID=-1003886228244
SHOPEE_APP_ID="18349740277"
AFILIADO_ID="18349740277"
LINK_GRUPO_OFERTAS="https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL="https://open-api.affiliate.shopee.com.br/graphql"
CHECK_INTERVAL=5400
MAX_OFERTAS=10
MIN_OFERTAS=4
HISTORICO_DIAS=3
SIMILARIDADE_MAX=.88
VENDAS_MIN=2
RATING_MIN=4.0
PRECO_MIN=15
PRECO_MAX=10000
COMISSAO_MIN=.03
RODIZIO_BUSCAS_VERSAO=9
FUSO_BR=ZoneInfo("America/Sao_Paulo")
ESTADO_FILE="estado_buscas.json"
HISTORICO_FILE="historico_envios.json"

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s")
ULTIMAS_BUSCAS_SHOPEE=[];ULTIMOS_TITULOS=[]
usadas_abertura,set_gatilho,set_ciclo,BASES_VISTAS,TERMOS_USADOS_CICLO=set(),set(),set(),set(),set()
REJEICOES=Counter()

# =========================
# BÁSICAS
# =========================
def normalizar_texto(txt):
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9à-ÿ\s]"," ",str(txt or "").lower().strip()))

def dentro_do_horario():
    a=datetime.now(FUSO_BR).time()
    return dt_time(5,30)<=a<=dt_time(21,30)

SINONIMOS_GRUPO={
    "smartwatch":{"smartwatch","relogio inteligente"},
    "airfryer":{"air fryer","airfryer","fritadeira eletrica"},
    "fone":{"fone bluetooth","fones de ouvido","headset"},
    "caixa_som":{"caixa de som","speaker","soundbar"},
    "tv":{"smart tv","televisao","tv"},
    "notebook":{"notebook","laptop"},
    "tablet":{"tablet","ipad"},
    "celular":{"celular","smartphone","iphone"}
}
MAPA_SINONIMO={normalizar_texto(t):g for g,ts in SINONIMOS_GRUPO.items() for t in ts}

def termo_ja_foi_buscado(t):
    g=MAPA_SINONIMO.get(normalizar_texto(t))
    return bool(g and any(MAPA_SINONIMO.get(normalizar_texto(x))==g for x in TERMOS_USADOS_CICLO))

# =========================
# CATÁLOGOS
# =========================
MOTOS=["titan 150","cb 300","factor 150","titan 160","tornado 250","fazer 150","titan 125","bros 160","twister 250","biz 125","pop 110","xre 300","crosser 150","xre 190","fazer 250","lander 250","bros 150","tenere 250","biz 100","twister 300"]

PECAS_MOTO=[
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

PRODUTOS_NICHO={
"Casa":["air fryer","aspirador","liquidificador","cafeteira","panela eletrica","panela de pressão","capa para colchão","jogo de pratos","jogo de copos","copo stanley","talher","panos de prato","toalhas de banho","coberta manta","lençol","mangueira de jardim","tapete","torneira de cozinha","filtro de barro","guarda roupas casal","cama casal","forma de silicone","sapateira","umidificador","ar condicionado","jogo de panelas","cortinas","tinta spray","frigideiras","rede de dormir","pipoqueira","mop","ventilador","batedeira","escorredor de louça","caixa organizadora","papel de parede","luminaria"],
"Maternidade":["carrinho bebe","berco bebe","fralda descartavel","fralda de pano","naninha","sapatinho","kit toalha umedecida","banheira","kit bolsa maternidade","canguru","kit mamadeira","baba eletronica","ninho bebe","kit enxoval bebe","babador bebe","mordedor bebe","tapete infantil","cadeirinha bebe","almofada amamentacao","termometro infantil"],
"Eletroeletrônicos":["smartwatch","fone bluetooth","caixa de som bluetooth","bastão pau de selfie","celular","smart tv","video game","capinha celular","pelicula celular","balança digital","aparelho medidor de pressão","webcam camera","pen drive","impressora termica","computador","notebook","drone","camera de segurança","tablet","ssd","mouse gamer","teclado mecanico","power bank","carregador turbo","suporte celular carro"],
"Moda feminina":["vestido feminino","conjunto feminino","kit calcinhas","biquines","saida de praia","maquiagens","roupa academia","calça jean","calça leggin","saia longa","sandalias","pijamas","blusa regata","kit sutian","bermuda modeladora","oculos de sol","calça social","vestido midi","jaqueta feminina","casaco feminino","conjunto alfaiataria","short feminino","tenis feminino","bolsa feminina","blazer feminino","saia jeans","top feminino","body feminino"],
"Moda masculina":["camiseta masculina","bermudas jeans","camisetas regatas","camisa polo","camisa de linho","terno","blazer","kit meias","barbeador","meias esportivas","oculos de sol","calção de futebol","tenis futebol","chuteiras","camisa termica","bermuda masculina","jaqueta masculina","tenis masculino","carteira masculina","kit cueca","calça jeans masculina","camisa social masculina","moletom masculino","sapatenis masculino"]
}

FAMILIAS_EXTRA={
"air_fryer":["air fryer","airfryer","fritadeira"],
"fone_bluetooth":["fone bluetooth","fones de ouvido","headset"],
"smartwatch":["smartwatch","relogio inteligente"],
"caixa_som":["caixa de som","speaker"],
"smart_tv":["smart tv","televisao","tv"],
"notebook":["notebook","laptop"],
"tablet":["tablet","ipad"],
"celular":["celular","smartphone","iphone"],
"maternidade_bebe":["bebe","fralda","carrinho","berco","mamadeira","ninho"],
"moda_fem":["vestido","conjunto","saia","bolsa","sandalia","tenis feminino","body"],
"moda_masc":["camisa","camiseta","calca","tenis masculino","jaqueta","bermuda"],
"casa_lar":["tapete","lençol","cortina","organizador","luminaria"],
"moto_geral":["capacete","vela","pastilha","lona","corrente","coroa","pinhao","guidao","retrovisor","farol"]
}

NICHOS_FREE_ROTA=["Moto","Casa","Moda feminina","Moda masculina","Maternidade","Eletroeletrônicos"]

# =========================
# JSON / ESTADO
# =========================
def salvar_json_seguro(arq,dados):
    try:
        pasta=os.path.dirname(os.path.abspath(arq)) or "."
        fd,tmp=tempfile.mkstemp(prefix=".tmp_",dir=pasta,text=True)
        with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(dados,f,ensure_ascii=False,indent=2)
        os.replace(tmp,arq)
    except Exception as e:logging.error("Erro salvando %s: %s",arq,e)

def carregar_json(arq,padrao):
    try:
        if not os.path.exists(arq):return padrao
        with open(arq,"r",encoding="utf-8") as f:return json.load(f)
    except Exception as e:logging.error("Erro lendo %s: %s",arq,e);return padrao

def carregar_estado():
    e=carregar_json(ESTADO_FILE,{})
    if e.get("rodizio_buscas_versao")!=RODIZIO_BUSCAS_VERSAO:
        hoje=datetime.now(FUSO_BR).strftime("%Y%m%d")
        e={"rodizio_buscas_versao":RODIZIO_BUSCAS_VERSAO,
           "Moto":{"data_rodizio":hoje,"idx":0}}
        for n,l in PRODUTOS_NICHO.items():e[n]={"pos":0,"data_rodizio":hoje}
    e.setdefault("Moto",{"data_rodizio":"","idx":0})
    e["Moto"].setdefault("idx",0);e["Moto"].setdefault("data_rodizio","")
    for n in PRODUTOS_NICHO:
        e.setdefault(n,{"pos":0,"data_rodizio":""})
        e[n].setdefault("pos",0);e[n].setdefault("data_rodizio","")
    e.setdefault("free_nicho_idx",0)
    return e

def salvar_estado(e):salvar_json_seguro(ESTADO_FILE,e)
def carregar_historico():return carregar_json(HISTORICO_FILE,{})
def salvar_historico(h):salvar_json_seguro(HISTORICO_FILE,h)

# =========================
# 🏍️ ROTAÇÃO MOTO CORRIGIDA
# =========================
def proxima_busca_moto(e):
    idx=e["Moto"]["idx"]
    peca=PECAS_MOTO[idx%len(PECAS_MOTO)]
    moto=MOTOS[idx%len(MOTOS)]
    e["Moto"]["idx"]=(idx+1)%(len(PECAS_MOTO)*len(MOTOS))
    logging.info("🏍️ Peça: [%s] | Moto: [%s]",peca,moto)
    return peca,moto,e

# =========================
# RODÍZIO NORMAL
# =========================
def get_proximo_termo(nicho,e):
    l=PRODUTOS_NICHO[nicho];st=e[nicho]
    for _ in range(len(l)):
        termo=l[st["pos"]%len(l)];st["pos"]+=1
        if termo_ja_foi_buscado(termo):
            logging.info("🛑 PULADO sinônimo: %s",termo);continue
        TERMOS_USADOS_CICLO.add(termo);return termo,e
    return l[st["pos"]%len(l)],e

# =========================
# FILTROS
# =========================
def chave_base_titulo(titulo):
    stop={"premium","novo","promocao","promoção","super","original","profissional","casual","masculino","feminino","infantil","adulto","unissex","kit","com","de","para","o","a","promo","oferta","modelo","versao","versão","linha","envio","usado","branco","preto","azul","vermelho","rosa","verde","amarelo","tamanho","gamer","led","usb"}
    p=[x for x in normalizar_texto(titulo).split() if x not in stop and len(x)>2]
    return " ".join(sorted(p)[:8])

def tem_bloqueio(t):
    t=normalizar_texto(t)
    return any(x in t for x in ["teste","amostra","não compre","nao compre","produto teste","exemplo","dummy","vela led","vela decorativa","decorativa","decoração","casamento","festa"])

def titulo_duplicado_forte(t):
    n,b=normalizar_texto(t),chave_base_titulo(t)
    return any(n==p or SequenceMatcher(None,n,p).ratio()>=SIMILARIDADE_MAX or (b and b==chave_base_titulo(p)) for p in ULTIMOS_TITULOS)

def produto_parecido(t,titulos):
    n,b=normalizar_texto(t),chave_base_titulo(t)
    return any(SequenceMatcher(None,n,normalizar_texto(x)).ratio()>=.84 or (b and b==chave_base_titulo(x)) for x in titulos)

def shop_score(s):
    try:return 3 if 1 in s else 2 if 4 in s else 1 if 2 in s else 0
    except:return 0

def oferta_score(p,termo=""):
    try:
        v=int(p.get("sales",0)or 0);r=float(p.get("ratingStar",0)or 0)
        c=float(p.get("commissionRate",0)or 0);pr=float(p.get("priceMin",0)or 0)
        n=normalizar_texto(p.get("productName",""));tn=normalizar_texto(termo)
        s=min(v/8,25)+r*2+c*100+shop_score(p.get("shopType",[]))
        if 50<=pr<=5000:s+=6
        if tn:s+=8 if tn in n else sum(2 for x in tn.split() if x in n)
        return s
    except:return 0

def motivo_rejeicao(p):
    t=str(p.get("productName","")).strip();l=str(p.get("offerLink")or p.get("productLink")or "").strip()
    pr=float(p.get("priceMin",0)or 0);c=float(p.get("commissionRate",0)or 0)
    v=int(p.get("sales",0)or 0);r=float(p.get("ratingStar",0)or 0)
    if not t:return "sem_titulo"
    if not l:return "sem_link"
    if tem_bloqueio(t):return "bloqueio_texto"
    if pr<PRECO_MIN:return "preco_baixo"
    if pr>PRECO_MAX:return "preco_alto"
    if c<COMISSAO_MIN:return "comissao_baixa"
    if v<VENDAS_MIN:return "vendas_baixas"
    if r and r<RATING_MIN:return "rating_baixo"
    if l in ULTIMAS_BUSCAS_SHOPEE or l in set_ciclo:return "link_repetido"
    return None

def historico_bloqueia(chave):
    h=carregar_historico()
    if chave not in h:return False
    try:
        d=datetime.fromisoformat(h[chave])
        if d.tzinfo is None:d=d.replace(tzinfo=FUSO_BR)
        return datetime.now(FUSO_BR)-d<timedelta(days=HISTORICO_DIAS)
    except:return False

def registrar_historico(chave):
    h=carregar_historico();h[chave]=datetime.now(FUSO_BR).isoformat()
    limite=datetime.now(FUSO_BR)-timedelta(days=HISTORICO_DIAS*3)
    salvar_historico({k:v for k,v in h.items() if datetime.fromisoformat(v).replace(tzinfo=FUSO_BR)>=limite})

def familia(t):
    t=normalizar_texto(t)
    return next((f for f,ts in FAMILIAS_EXTRA.items() if any(normalizar_texto(x) in t for x in ts)),"outros")

# =========================
# VALIDAÇÃO
# =========================
def validar_modelo(titulo,modelo):
    t=normalizar_texto(titulo);m=normalizar_texto(modelo)
    return all(x in t for x in m.split() if len(x)>2)

def validar_peca(titulo,peca):
    t,p=normalizar_texto(titulo),normalizar_texto(peca)
    aliases={"kit relacao":["kit relacao","relação completa","kit transmissão"],
             "jogo de juntas":["jogo de juntas","juntas"],
             "burrinho de freio":["burrinho de freio","cilindro mestre"],
             "par pneu":["par pneu","kit pneu","pneus"]}
    return any(x in t for x in aliases.get(p,[p]))

def validar_relevancia(nicho,titulo,termo=None,modelo=None,peca=None):
    t=normalizar_texto(titulo)
    if nicho=="Eletroeletrônicos" and any(x in t for x in ["capa","pelicula"]) and not any(x in t for x in ["celular","tablet","iphone"]):return False
    if nicho=="Casa" and "tinta" in t and not any(x in t for x in ["parede","spray"]):return False
    if nicho=="Moda feminina" and any(x in t for x in ["masculino","homem"]):return False
    if nicho=="Moda masculina" and any(x in t for x in ["feminino","mulher"]):return False
    if nicho=="Maternidade" and any(x in t for x in ["organizador","cozinha"]) and not any(x in t for x in ["bebe","infantil"]):return False
    if nicho=="Moto" and ((modelo and not validar_modelo(titulo,modelo)) or (peca and not validar_peca(titulo,peca))):return False
    return True

# =========================
# SHOPEE
# =========================
def buscar_produtos(kw,nicho):
    logging.info("🔍 Buscando em %s: %s",nicho,kw)
    ts=int(time.time())
    query=f'query {{productOfferV2(sortType:2,limit:50,keyword:{json.dumps(kw,ensure_ascii=False)},isAMSOffer:true){{nodes{{productName,priceMin,priceMax,commissionRate,sales,ratingStar,productLink,offerLink,imageUrl,shopType}}}}}}'
    payload=json.dumps({"query":query},ensure_ascii=False)
    sig=hashlib.sha256((SHOPEE_APP_ID+str(ts)+payload+SHOPEE_PASSWORD).encode()).hexdigest()
    headers={"Content-Type":"application/json","Authorization":f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={ts}, Signature={sig}","User-Agent":"Mozilla/5.0"}
    try:
        r=requests.post(SHOPEE_GRAPHQL_URL,data=payload.encode(),headers=headers,timeout=25);r.raise_for_status()
        d=r.json()
        if d.get("errors"):logging.error("GraphQL: %s",d["errors"]);return []
        p=d.get("data",{}).get("productOfferV2",{}).get("nodes",[])or[]
        logging.info("✅ Retornou %s produtos",len(p));return p
    except Exception as e:logging.error("❌ Shopee: %s",e);return []

def selecionar(nicho,termo,cota,e,moto=False,peca=None):
    kw=f"{peca} {termo}" if moto else termo
    resultados=buscar_produtos(kw,nicho);validos=[];motivos=Counter()
    for p in resultados:
        m=motivo_rejeicao(p)
        if m:motivos[m]+=1;REJEICOES[m]+=1
        else:validos.append(p)
    logging.info("📊 %s [%s]: %s brutos / %s válidos",nicho,kw,len(resultados),len(validos))
    validos.sort(key=lambda x:oferta_score(x,termo),reverse=True)
    escolhidos=[];titulos=[];familias=Counter()
    for p in validos:
        if len(escolhidos)>=cota:break
        t=str(p.get("productName","")).strip();l=str(p.get("offerLink")or p.get("productLink")or "").strip()
        b=chave_base_titulo(t);f=familia(t);pid=hashlib.md5(f"{b}|{l}".encode()).hexdigest()
        if not l or b in BASES_VISTAS or l in set_ciclo or historico_bloqueia(pid):continue
        if titulo_duplicado_forte(t) or produto_parecido(t,titulos):continue
        if not validar_relevancia(nicho,t,termo=termo,modelo=termo if moto else None,peca=peca):motivos["relevancia"]+=1;continue
        if f!="outros" and familias[f]>=2:continue
        escolhidos.append(p);titulos.append(t);familias[f]+=1
        BASES_VISTAS.add(b);set_ciclo.add(l);ULTIMAS_BUSCAS_SHOPEE.append(l);ULTIMOS_TITULOS.append(normalizar_texto(t))
        logging.info("🏆 ESCOLHIDO | %s | família=%s | score=%.1f",t,f,oferta_score(p,termo))
    del ULTIMAS_BUSCAS_SHOPEE[:-300];del ULTIMOS_TITULOS[:-150]
    if motivos:logging.info("📋 Motivos %s: %s",nicho,dict(motivos))
    return escolhidos,e

# =========================
# COLETA
# =========================
def get_shopee_offers():
    global set_ciclo,BASES_VISTAS,TERMOS_USADOS_CICLO
    set_ciclo=BASES_VISTAS=TERMOS_USADOS_CICLO=set()
    candidatos=[];e=carregar_estado()

    # 🏍️ IMPORTANTE:
    # cada busca de moto avança PEÇA + MODELO.
    # não fica mais vários ciclos na mesma peça.
    for _ in range(2):
        peca,moto,e=proxima_busca_moto(e)
        escolhidos,e=selecionar("Moto",moto,1,e,True,peca)
        candidatos.extend(("Moto",p) for p in escolhidos)

    cotas={"Casa":2,"Maternidade":2,"Eletroeletrônicos":2,"Moda feminina":1,"Moda masculina":1}
    for nicho,cota in cotas.items():
        for _ in range(cota):
            termo,e=get_proximo_termo(nicho,e)
            escolhidos,e=selecionar(nicho,termo,1,e)
            candidatos.extend((nicho,p) for p in escolhidos)

    salvar_estado(e);candidatos.sort(key=lambda x:oferta_score(x[1]),reverse=True)
    logging.info("✅ POOL TOTAL: %s | RESULTADO CICLO: %s/%s",len(candidatos),min(len(candidatos),MAX_OFERTAS),MAX_OFERTAS)
    return candidatos[:MAX_OFERTAS]

# =========================
# COPY
# =========================
CHAMADAS=["👇 CORRE QUE TÁ ACABANDO!","⚡ CLIQUE ANTES QUE AUMENTE!","🚀 ESTOQUE LIMITADO - AGORA!","💥 MELHOR PREÇO DO ANO!","🎯 COMPRE ANTES DOS OUTROS!","🔥 VOOU DAS PRATELEIRAS!","⏰ PROMOÇÃO ACABA HOJE!","💰 ECONOMIA REAL - CORRE!","⭐ OFERTA QUENTE AGORA!","🛒 NÃO DEIXA ESCAPAR!"]
ABERTURAS=["🚨 Isso aqui não é comum aparecer assim","👀 Achei isso aqui e fui conferir…","🔥 Isso aqui tá com cara de oportunidade","💥 Esse aqui tá chamando atenção de quem compra","🛑 Para tudo e olha isso aqui","🤯 Sério… olha esse achado","⚠️ Isso aqui pode desaparecer rápido","👁️ Pouca gente viu isso ainda","📉 Esse preço aqui não costuma durar","🚀 Esse aqui tá começando a rodar forte"]
GATILHOS=["Preço muito abaixo do que costuma aparecer","Avaliações acima da média","Volume de vendas alto","Simples e funcional","Custo-benefício forte","Quem compra recomenda","Produto direto ao ponto","Tá vendendo bem","Boa margem pra afiliado","Resolve de verdade"]

def aplicar_id(link):
    try:
        p=urlparse(link);q=parse_qs(p.query);q["af_siteid"]=AFILIADO_ID
        return urlunparse(p._replace(query=urlencode(q,doseq=True)))
    except:return link

def gerar_link_whatsapp(msg):
    return f"https://wa.me/?text={quote(re.sub(r'<[^>]+>','',msg))}"

def gerar_copy(nome,preco,vendas,rating,comissao,link):
    abertura=random.choice([x for x in ABERTURAS if x not in usadas_abertura] or ABERTURAS)
    gatilho=random.choice([x for x in GATILHOS if x not in set_gatilho] or GATILHOS)
    acao=random.choice(CHAMADAS);usadas_abertura.add(abertura);set_gatilho.add(gatilho)

    return (
        f"{html.escape(abertura)}\n\n"
        f"🔥 <b>{html.escape(nome)}</b>\n\n"
        f"{html.escape(gatilho)}\n\n"
        f"{html.escape(acao)}\n\n"
        f"💰 <b>R$ {preco}</b>\n"
        f"⭐ <b>{rating} | 🛒 {vendas} vendas</b>\n"
        f"💸 Comissão: <b>{comissao}%</b>\n\n"
        f"⚠️ Pode subir de preço\n\n"
        f'<a href="{html.escape(link,quote=True)}">🛒 COMPRAR AGORA</a>\n\n'
        f'<a href="{html.escape(LINK_GRUPO_OFERTAS,quote=True)}">📲 Entrar no grupo de ofertas</a>'
    )

def gerar_zap(nome,preco,vendas,rating,link,abertura,gatilho,acao):
    return (
        f"{abertura}\n\n🔥 {nome}\n\n{gatilho}\n\n{acao}\n\n"
        f"💰 R$ {preco}\n⭐ {rating} | 🛒 {vendas} vendas\n\n"
        f"⚠️ Pode subir de preço\n\n"
        f"🛒 COMPRAR AGORA: {link}\n\n"
        f"📢 Quer mais ofertas assim? Entre no nosso grupo: {LINK_GRUPO_OFERTAS}"
    )

# =========================
# TELEGRAM
# =========================
async def enviar_produto(ctx,item,chat):
    try:
        await ctx.bot.send_photo(chat_id=chat,photo=item["img"],caption=item["msg"],parse_mode="HTML")
        return True
    except Exception as e:logging.warning("⚠️ Foto falhou: %s",e)
    try:
        await ctx.bot.send_message(chat_id=chat,text=item["msg"],parse_mode="HTML")
        return True
    except Exception as e:logging.error("❌ Falha envio: %s",e)
    return False

async def enviar_lote(ctx,lista):
    await ctx.bot.send_message(chat_id=CHAT_ID_DESTINO,text="🚨 <b>OFERTAS NOVAS CHEGANDO...</b>",parse_mode="HTML")
    await asyncio.sleep(5)
    for item in lista:
        logging.info("📤 Enviando VIP | nicho=%s",item["nicho_origem"])
        if await enviar_produto(ctx,item,CHAT_ID_DESTINO):registrar_historico(item["produto_id"])
        await asyncio.sleep(40)

# =========================
# CICLO
# =========================
async def send_ofertas(ctx):
    try:
        logging.info("========== 🔄 INÍCIO DO CICLO ==========")
        if not dentro_do_horario():
            logging.info("⏹️ Fora do horário 05:30–21:30");return

        usadas_abertura.clear();set_gatilho.clear()
        ofertas=get_shopee_offers()
        if len(ofertas)<MIN_OFERTAS:
            logging.warning("⚠️ Só %s ofertas. Mínimo %s.",len(ofertas),MIN_OFERTAS);return

        selecionadas=[]
        for nicho,p in ofertas:
            try:
                nome=str(p.get("productName","")).strip()
                lb=str(p.get("offerLink")or p.get("productLink")or "").strip()
                if not nome or not lb:continue

                link=aplicar_id(lb)
                preco=float(p.get("priceMin",0)or 0)
                vendas=int(p.get("sales",0)or 0)
                rating=float(p.get("ratingStar",4.5)or 4.5)
                comissao=round(float(p.get("commissionRate",0)or 0)*100,2)
                img=str(p.get("imageUrl")or "").strip()

                pf=f"{preco:.2f}".replace(".",",")
                vf=f"{vendas:,}".replace(",",".")
                rf=f"{rating:.1f}"

                abertura=random.choice([x for x in ABERTURAS if x not in usadas_abertura] or ABERTURAS)
                gatilho=random.choice([x for x in GATILHOS if x not in set_gatilho] or GATILHOS)
                acao=random.choice(CHAMADAS)
                usadas_abertura.add(abertura);set_gatilho.add(gatilho)

                msg=gerar_copy(nome,pf,vf,rf,comissao,link)
                zap=gerar_link_whatsapp(gerar_zap(nome,pf,vf,rf,link,abertura,gatilho,acao))

                msg+=(
                    f'\n\n<a href="{html.escape(zap,quote=True)}">'
                    f'📲 Compartilhar no WhatsApp</a>'
                    f'\n\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                )

                pid=hashlib.md5(f"{nome}|{lb}".encode()).hexdigest()
                selecionadas.append({"msg":msg,"img":img,"produto_id":pid,"item_raw":p,"nicho_origem":nicho})
            except Exception as e:logging.error("❌ Erro produto: %s",e)

        if len(selecionadas)<MIN_OFERTAS:
            logging.warning("⚠️ Só %s ofertas válidas.",len(selecionadas));return

        await enviar_lote(ctx,selecionadas)

        logging.info("========== 🆓 BLOCO FREE ==========")
        e=carregar_estado();idx=int(e.get("free_nicho_idx",0))
        nicho=NICHOS_FREE_ROTA[idx%len(NICHOS_FREE_ROTA)]
        oferta=next((x for x in selecionadas if x["nicho_origem"]==nicho),None)
        if oferta and await enviar_produto(ctx,oferta,FREE_CHAT_ID):registrar_historico(oferta["produto_id"])
        else:logging.warning("⚠️ Sem oferta FREE para %s",nicho)
        e["free_nicho_idx"]=(idx+1)%len(NICHOS_FREE_ROTA);salvar_estado(e)
        logging.info("========== ✅ CICLO FINALIZADO ==========")
    except Exception as e:logging.error("❌ ERRO CICLO: %s",e,exc_info=True)

# =========================
# LOOP
# =========================
async def ofertas_loop(app):
    logging.info("🔄 Loop automático iniciado.");await asyncio.sleep(10)
    while True:
        try:await send_ofertas(type("Contexto",(),{"bot":app.bot})())
        except Exception as e:logging.error("❌ Erro loop: %s",e,exc_info=True)
        logging.info("⏳ Próximo ciclo em %ss",CHECK_INTERVAL)
        await asyncio.sleep(CHECK_INTERVAL)

async def keep_alive():
    while True:
        logging.info("💚 BOT VIVO | %s",datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M"))
        await asyncio.sleep(300)

# =========================
# TELEGRAM START
# =========================
async def post_init(app):
    app.bot_data["ofertas_task"]=asyncio.create_task(ofertas_loop(app))
    app.bot_data["keepalive_task"]=asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTÁVEL")

async def post_shutdown(app):
    tasks=[app.bot_data.get(x) for x in ["ofertas_task","keepalive_task"]]
    for t in tasks:
        if t:t.cancel()
    await asyncio.gather(*[t for t in tasks if t],return_exceptions=True)

async def error_handler(update,context):
    logging.error("❌ ERRO: %s",context.error,exc_info=True)

def validar_config():
    faltam=[x for x in ["TELEGRAM_TOKEN","SHOPEE_PASSWORD","SHOPEE_APP_ID"] if not globals().get(x,"")]
    if faltam:raise RuntimeError("Variáveis ausentes: "+", ".join(faltam))

def iniciar():
    validar_config()
    logging.info("="*45)
    logging.info("🚀 SHOPEE BOT V29 - ROTAÇÃO ALTERNADA")
    logging.info("🏍️ Moto: PEÇA + MODELO avançam juntos")
    logging.info("🔗 Botões separados e clicáveis")
    logging.info("="*45)
    while True:
        try:
            app=(ApplicationBuilder().token(TELEGRAM_TOKEN)
                 .post_init(post_init).post_shutdown(post_shutdown).build())
            app.add_error_handler(error_handler)
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            logging.error("🔄 Reiniciando em 15s: %s",e)
            time.sleep(15)

if __name__=="__main__":iniciar()


