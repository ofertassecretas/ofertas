import asyncio,requests,logging,random,hashlib,time,json,os,html,re,tempfile
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime,time as dt_time,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse,parse_qs,urlencode,urlunparse,quote
from telegram.ext import ApplicationBuilder,ContextTypes

print("VERSAO V29-DIVERSIDADE-INTELIGENTE")

# =========================
# CONFIGURAÇÃO
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
PRECO_MIN=15.0
PRECO_MAX=10000.0
COMISSAO_MIN=0
RODIZIO_BUSCAS_VERSAO=8
FUSO_BR=ZoneInfo("America/Sao_Paulo")

ESTADO_FILE="estado_buscas.json"
HISTORICO_FILE="historico_envios.json"

logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s")

ULTIMAS_BUSCAS_SHOPEE=[]
ULTIMOS_TITULOS=[]
usadas_abertura,set_gatilho=set(),set()
usadas_gatilho=set()
usados_no_ciclo=set()
BASES_VISTAS=set()
FAMILIAS_VISTAS=set()
TERMOS_USADOS_CICLO=set()
REJEICOES=Counter()

# =========================
# FUNÇÕES BÁSICAS
# =========================
def normalizar_texto(txt):
    if not txt:return ""
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9à-ÿ\s]"," ",str(txt).lower().strip()))

def dentro_do_horario():
    agora=datetime.now(FUSO_BR).time()
    return dt_time(5,30)<=agora<=dt_time(21,30)

# =========================
# SINÔNIMOS
# =========================
SINONIMOS_GRUPO={
    "smartwatch":{"smartwatch","relogio inteligente","relógio inteligente"},
    "airfryer":{"air fryer","airfryer","fritadeira eletrica","fritadeira elétrica","fritadeira de ar"},
    "fone":{"fone bluetooth","fones de ouvido","headset"},
    "caixa_som":{"caixa de som","caixa de som bluetooth","speaker","soundbar"},
    "tv":{"smart tv","televisão","tv"},
    "notebook":{"notebook","laptop"},
    "tablet":{"tablet","ipad"},
    "celular":{"celular","smartphone","iphone"}
}

MAPA_SINONIMO={}
for grupo,termos in SINONIMOS_GRUPO.items():
    for t in termos:MAPA_SINONIMO[normalizar_texto(t)]=grupo

def termo_ja_foi_buscado(termo):
    t_norm=normalizar_texto(termo)
    grupo=MAPA_SINONIMO.get(t_norm)
    if not grupo:return False
    return any(MAPA_SINONIMO.get(normalizar_texto(t))==grupo for t in TERMOS_USADOS_CICLO)

def marcar_termo_usado(termo):
    TERMOS_USADOS_CICLO.add(termo)

# =========================
# CATÁLOGOS
# =========================
MOTOS=[
    "titan 150","cb 300","factor 150","titan 160","tornado 250","fazer 150",
    "titan 125","bros 160","twister 250","biz 125","pop 110","xre 300",
    "crosser 150","xre 190","fazer 250","lander 250","bros 150","tenere 250",
    "biz 100","twister 300"
]

PECAS_MOTO=[
    "kit relacao","kit embreagem","bateria","refil bomba combustivel",
    "chicote fiação principal","bucha balança","burrinho de freio","estribo",
    "pedal de marcha","pedal de freio","rolamento virabrequim","estator",
    "chave ignição","punho chave luz","kit pisca seta","par pneu","bloco optico",
    "retentor de bengala","bucha amortecedor","carburador corpo de injeção",
    "kit cilindro","jogo de juntas","biela","valvulas escape admissão",
    "kit freio a disco","disco de freio","tubo interno","vela iridium",
    "pastilha freio","guidao","manopla","amortecedor","retrovisor","farol",
    "lona de freio","cabo embreagem","cabo acelerador","coroa moto",
    "pinhao moto","corrente moto","pedaleira","carenagem","lanterna traseira",
    "capacete"
]

PRODUTOS_NICHO={
"Casa":[
    "air fryer","aspirador","liquidificador","cafeteira","panela eletrica",
    "panela de pressão","capa para colchão","jogo de pratos","jogo de copos",
    "copo stanley","talher","panos de prato","toalhas de banho","coberta manta",
    "lençol","mangueira de jardim","tapete","torneira de cozinha","filtro de barro",
    "guarda roupas casal","cama casal","forma de silicone","sapateira","umidificador",
    "ar condicionado","jogo de panelas","cortinas","tinta spray","frigideiras",
    "rede de dormir","pipoqueira","mop","ventilador","batedeira","escorredor de louça",
    "caixa organizadora","papel de parede","luminaria"
],
"Maternidade":[
    "carrinho bebe","berco bebe","fralda descartavel","fralda de pano","naninha",
    "sapatinho","kit toalha umedecida","banheira","kit bolsa maternidade","canguru",
    "kit mamadeira","baba eletronica","ninho bebe","kit enxoval bebe","babador bebe",
    "mordedor bebe","tapete infantil","cadeirinha bebe","almofada amamentacao",
    "termometro infantil"
],
"Eletroeletrônicos":[
    "smartwatch","fone bluetooth","caixa de som bluetooth","bastão pau de selfie",
    "celular","smart tv","video game","capinha celular","pelicula celular",
    "balança digital","aparelho medidor de pressão","webcam camera","pen drive",
    "impressora termica","computador","notebook","drone","camera de segurança",
    "tablet","ssd","mouse gamer","teclado mecanico","power bank","carregador turbo",
    "suporte celular carro"
],
"Moda feminina":[
    "vestido feminino","conjunto feminino","kit calcinhas","biquines","saida de praia",
    "maquiagens","roupa academia","calça jean","calça leggin","saia longa","sandalias",
    "pijamas","blusa regata","kit sutian","bermuda modeladora","oculos de sol",
    "calça social","vestido midi","jaqueta feminina","casaco feminino",
    "conjunto alfaiataria","short feminino","tenis feminino","bolsa feminina",
    "blazer feminino","saia jeans","top feminino","body feminino"
],
"Moda masculina":[
    "camiseta masculina","bermudas jeans","camisetas regatas","camisa polo",
    "camisa de linho","terno","blazer","kit meias","barbeador","meias esportivas",
    "oculos de sol","calção de futebol","tenis futebol","chuteiras","camisa termica",
    "bermuda masculina","jaqueta masculina","tenis masculino","carteira masculina",
    "kit cueca","calça jeans masculina","camisa social masculina","moletom masculino",
    "sapatenis masculino"
]}

FAMILIAS_EXTRA={
    "air_fryer":["air fryer","airfryer","fritadeira"],
    "aspirador":["aspirador robô","aspirador robo","aspirador"],
    "liquidificador":["liquidificador"],
    "cafeteira":["cafeteira"],
    "panela":["panela eletrica","panela elétrica","jogo de panelas","frigideira","panela"],
    "celular":["celular","smartphone","iphone","galaxy","redmi","poco","moto g"],
    "smartwatch":["smartwatch","relogio inteligente"],
    "fone_bluetooth":["fone bluetooth","fone de ouvido","fones de ouvido","headset"],
    "caixa_som":["caixa de som","speaker","soundbar"],
    "smart_tv":["smart tv","televisão","televisor","tv"],
    "notebook":["notebook","laptop"],
    "tablet":["tablet","ipad"],
    "maternidade_bebe":["carrinho bebe","carrinho de bebe","berco","berço","fralda","mamadeira","ninho bebe"],
    "moda_fem":["vestido feminino","conjunto feminino","saia","bolsa feminina","sandalia","tenis feminino","body feminino"],
    "moda_masc":["camisa masculina","camiseta masculina","calça masculina","tenis masculino","jaqueta masculina","bermuda masculina"],
    "tapete":["tapete"],
    "lençol":["lençol","jogo de cama"],
    "toalha":["toalha","toalhas"],
    "mangueira":["mangueira"],
    "organizador":["organizador","caixa organizadora"],
    "luminaria":["luminaria","luminária"],
    "capacete":["capacete"],
    "moto_peca":["pastilha","lona de freio","kit relação","kit relacao","corrente","coroa","pinhão","pinhao","vela","retrovisor","farol","amortecedor"]
}

NICHOS_FREE_ROTA=["Moto","Casa","Moda feminina","Moda masculina","Maternidade","Eletroeletrônicos"]

# =========================
# ARQUIVOS / ESTADO
# =========================
def salvar_json_seguro(arquivo,dados):
    try:
        pasta=os.path.dirname(os.path.abspath(arquivo)) or "."
        fd,tmp=tempfile.mkstemp(prefix=".tmp_",dir=pasta,text=True)
        with os.fdopen(fd,"w",encoding="utf-8") as f:
            json.dump(dados,f,ensure_ascii=False,indent=2)
        os.replace(tmp,arquivo)
    except Exception as e:
        logging.error("Erro salvando %s: %s",arquivo,e)

def carregar_json(arquivo,padrao):
    try:
        if not os.path.exists(arquivo):return padrao
        with open(arquivo,"r",encoding="utf-8") as f:return json.load(f)
    except Exception as e:
        logging.error("Erro lendo %s: %s",arquivo,e)
        return padrao

def carregar_estado():
    estado=carregar_json(ESTADO_FILE,{})
    if estado.get("rodizio_buscas_versao")!=RODIZIO_BUSCAS_VERSAO:
        logging.info("🔄 REINICIANDO RODÍZIO - versão %s",RODIZIO_BUSCAS_VERSAO)
        hoje=datetime.now(FUSO_BR).strftime("%Y%m%d")
        estado={
            "rodizio_buscas_versao":RODIZIO_BUSCAS_VERSAO,
            "Moto":{"data_rodizio":hoje,"peca_idx":0,"moto_par_idx":0}
        }
        for n in PRODUTOS_NICHO:
            estado[n]={
                "ordem":list(range(len(PRODUTOS_NICHO[n]))),
                "pos":0,
                "data_rodizio":hoje
            }

    for n in PRODUTOS_NICHO:
        estado.setdefault(n,{})
        estado[n].setdefault("ordem",list(range(len(PRODUTOS_NICHO[n]))))
        estado[n].setdefault("pos",0)
        estado[n].setdefault("data_rodizio","")

    estado.setdefault("free_nicho_idx",0)
    estado.setdefault("Moto",{})
    estado["Moto"].setdefault("data_rodizio","")
    estado["Moto"].setdefault("peca_idx",0)
    estado["Moto"].setdefault("moto_par_idx",0)
    return estado

def salvar_estado(estado):
    salvar_json_seguro(ESTADO_FILE,estado)

def carregar_historico():
    return carregar_json(HISTORICO_FILE,{})

def salvar_historico(hist):
    salvar_json_seguro(HISTORICO_FILE,hist)

# =========================
# 🏍️ ROTAÇÃO MOTO
# =========================
def gerar_pares_motos():
    pares=[MOTOS[i:i+2] for i in range(0,len(MOTOS),2)]
    if len(MOTOS)%2:pares[-1].append(MOTOS[0])
    return pares

def get_combinacao_moto_dia(estado):
    hoje=datetime.now(FUSO_BR).strftime("%Y%m%d")
    pares=gerar_pares_motos()

    if estado["Moto"]["data_rodizio"]!=hoje:
        logging.info("🗓️ NOVO DIA → reiniciando sequência de peças e motos")
        estado["Moto"]["data_rodizio"]=hoje
        estado["Moto"]["peca_idx"]=0
        estado["Moto"]["moto_par_idx"]=0

    pi=estado["Moto"]["peca_idx"]%len(PECAS_MOTO)
    mi=estado["Moto"]["moto_par_idx"]%len(pares)

    peca_atual=PECAS_MOTO[pi]
    motos_atuais=pares[mi]

    estado["Moto"]["moto_par_idx"]+=1

    if estado["Moto"]["moto_par_idx"]>=len(pares):
        estado["Moto"]["moto_par_idx"]=0
        estado["Moto"]["peca_idx"]+=1
        logging.info("✅ Fim dos pares de moto → próxima peça")

    logging.info("🏍️ Peça: [%s] | Motos: [%s]",peca_atual," + ".join(motos_atuais))
    return peca_atual,motos_atuais,estado

# =========================
# RODÍZIO DEMAIS NICHOS
# =========================
def get_proximo_termo(nicho,estado):
    st=estado[nicho]
    lista=PRODUTOS_NICHO[nicho]

    for _ in range(len(lista)):
        idx=st["pos"]%len(lista)
        termo=lista[idx]
        st["pos"]+=1

        if termo_ja_foi_buscado(termo):
            logging.info("🛑 PULADO (sinônimo já usado): %s",termo)
            continue

        marcar_termo_usado(termo)
        return termo,estado

    termo=lista[st["pos"]%len(lista)]
    st["pos"]+=1
    logging.warning("⚠️ Termos esgotados em %s → usando %s",nicho,termo)
    return termo,estado

# =========================
# TEXTO / FAMÍLIA / PRODUTO
# =========================
def chave_base_titulo(titulo):
    stop={
        "premium","novo","promocao","promoção","super","original","profissional",
        "casual","masculino","feminino","infantil","adulto","unissex","estica",
        "kit","com","de","para","o","a","promo","oferta","modelo","versao",
        "versão","linha","envio","usado","branco","preto","azul","vermelho",
        "rosa","verde","amarelo","tamanho","tamanhos","unico","único","gamer",
        "led","usb"
    }
    palavras=[x for x in normalizar_texto(titulo).split() if x not in stop and len(x)>2]
    return " ".join(sorted(palavras)[:8])

def gerar_produto_id(titulo,link):
    return hashlib.md5(f"{normalizar_texto(titulo)}|{link}".encode()).hexdigest()

def tem_bloqueio(titulo):
    t=normalizar_texto(titulo)
    return any(x in t for x in [
        "teste","amostra","nao compre","não compre","produto teste","exemplo",
        "dummy","vela led","vela decorativa","decorativa","decoracao","decoração",
        "casamento","festa"
    ])

def titulo_duplicado_forte(titulo):
    t=normalizar_texto(titulo)
    base=chave_base_titulo(titulo)
    return any(
        t==prev or
        SequenceMatcher(None,t,prev).ratio()>=SIMILARIDADE_MAX or
        (base and base==chave_base_titulo(prev))
        for prev in ULTIMOS_TITULOS
    )

def produto_muito_parecido(titulo,titulos):
    t=normalizar_texto(titulo)
    base=chave_base_titulo(titulo)
    return any(
        SequenceMatcher(None,t,normalizar_texto(p)).ratio()>=.84 or
        (base and base==chave_base_titulo(p))
        for p in titulos
    )

def shop_type_score(shop_type):
    try:
        return 3 if 1 in shop_type else 2 if 4 in shop_type else 1 if 2 in shop_type else 0
    except:
        return 0

def identificar_familia(titulo):
    t=normalizar_texto(titulo)
    encontrados=[]

    for familia,termos in FAMILIAS_EXTRA.items():
        for termo in termos:
            termo_n=normalizar_texto(termo)
            if termo_n and termo_n in t:
                encontrados.append((len(termo_n),familia))

    if encontrados:
        return max(encontrados,key=lambda x:x[0])[1]

    palavras=[x for x in t.split() if len(x)>3]
    return "generico_"+("_".join(palavras[:2]) if palavras else "outros")

def oferta_score(p,termo="",familia_nova=True):
    try:
        vendas=int(p.get("sales",0)or 0)
        rating=float(p.get("ratingStar",0)or 0)
        comissao=float(p.get("commissionRate",0)or 0)
        preco=float(p.get("priceMin",0)or 0)
        nome=normalizar_texto(p.get("productName",""))
        termo_n=normalizar_texto(termo)

        score=min(vendas/8,25)+rating*2+comissao*100+shop_type_score(p.get("shopType",[]))

        if 50<=preco<=5000:score+=6
        if termo_n:
            score+=8 if termo_n in nome else sum(2 for x in termo_n.split() if x in nome)

        if vendas>=1000:score+=5
        elif vendas>=500:score+=3
        elif vendas>=100:score+=2

        if familia_nova:score+=12

        return score
    except:
        return 0

# =========================
# HISTÓRICO INTELIGENTE
# =========================
def historico_info(produto_id):
    hist=carregar_historico()
    valor=hist.get(produto_id)

    if not valor:return None

    try:
        d=datetime.fromisoformat(valor)
        if d.tzinfo is None:d=d.replace(tzinfo=FUSO_BR)
        return datetime.now(FUSO_BR)-d
    except:
        return None

def penalidade_historico(produto_id):
    idade=historico_info(produto_id)
    if idade is None:return 0

    dias=idade.total_seconds()/86400

    if dias<1:return 100
    if dias<2:return 60
    if dias<3:return 30
    if dias<5:return 12
    return 0

def historico_bloqueia(chave):
    return penalidade_historico(chave)>=100

def registrar_historico(chave):
    hist=carregar_historico()
    hist[chave]=datetime.now(FUSO_BR).isoformat()

    limite=datetime.now(FUSO_BR)-timedelta(days=HISTORICO_DIAS*4)
    novo={}

    for k,v in hist.items():
        try:
            d=datetime.fromisoformat(v)
            if d.tzinfo is None:d=d.replace(tzinfo=FUSO_BR)
            if d>=limite:novo[k]=v
        except:
            pass

    salvar_historico(novo)

# =========================
# VALIDAÇÃO
# =========================
def validar_modelo_titulo(titulo,termo):
    t=normalizar_texto(titulo)
    ps=[x for x in normalizar_texto(termo).split() if len(x)>2]
    return not ps or all(x in t for x in ps)

def validar_peca_moto(titulo,peca):
    t=normalizar_texto(titulo)
    p=normalizar_texto(peca)

    aliases={
        "kit relacao":["kit relacao","kit relação","relação completa","relacao completa"],
        "jogo de juntas":["jogo de juntas","juntas"],
        "burrinho de freio":["burrinho de freio","cilindro mestre"],
        "par pneu":["par pneu","kit pneu","pneus"]
    }

    return any(x in t for x in aliases.get(p,[p]))

def validar_relevancia_nicho(nicho,titulo,termo=None,modelo=None,peca=None):
    t=normalizar_texto(titulo)

    if nicho=="Eletroeletrônicos" and any(x in t for x in ["capa","pelicula"]) and not any(x in t for x in ["celular","tablet","iphone"]):
        return False

    if nicho=="Casa" and any(x in t for x in ["tinta"]) and not any(x in t for x in ["parede","spray"]):
        return False

    if nicho=="Moda feminina" and any(x in t for x in ["masculino","homem"]):
        return False

    if nicho=="Moda masculina" and any(x in t for x in ["feminino","mulher"]):
        return False

    if nicho=="Maternidade" and any(x in t for x in ["organizador","cozinha"]) and not any(x in t for x in ["bebe","infantil"]):
        return False

    if nicho=="Moto":
        if modelo and not validar_modelo_titulo(titulo,modelo):
            return False
        if peca and not validar_peca_moto(titulo,peca):
            return False

    return True

# =========================
# SHOPEE API
# =========================
def buscar_produtos_da_categoria_kw(palavra_chave,categoria):
    logging.info("🔍 Buscando em %s: %s",categoria,palavra_chave)

    timestamp=int(time.time())
    keyword=json.dumps(palavra_chave,ensure_ascii=False)

    query=f'query {{productOfferV2(sortType:2,limit:50,keyword:{keyword},isAMSOffer:true){{nodes{{productName,priceMin,priceMax,commissionRate,sales,ratingStar,productLink,offerLink,imageUrl,shopType}}}}}}'
    payload=json.dumps({"query":query},ensure_ascii=False)

    assinatura=SHOPEE_APP_ID+str(timestamp)+payload+SHOPEE_PASSWORD
    signature=hashlib.sha256(assinatura.encode()).hexdigest()

    headers={
        "Content-Type":"application/json",
        "Authorization":f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}",
        "User-Agent":"Mozilla/5.0"
    }

    try:
        r=requests.post(
            SHOPEE_GRAPHQL_URL,
            data=payload.encode("utf-8"),
            headers=headers,
            timeout=25
        )
        r.raise_for_status()
        data=r.json()

        if data.get("errors"):
            logging.error("Erro GraphQL: %s",data["errors"])
            return []

        prods=data.get("data",{}).get("productOfferV2",{}).get("nodes",[]) or []

        logging.info("✅ Retornou %s produtos",len(prods))
        return prods

    except Exception as e:
        logging.error("❌ Erro Shopee: %s",e)
        return []

# =========================
# SELEÇÃO INTELIGENTE
# =========================
def selecionar_ofertas_termo(nicho,termo,cota,estado,e_moto=False,peca=None):
    kw=termo if not e_moto else f"{peca} {termo}"

    resultados=buscar_produtos_da_categoria_kw(kw,nicho)
    filtrados=[]
    motivos=Counter()

    for p in resultados:
        m=motivo_rejeicao(p)

        if m is None:
            filtrados.append(p)
        else:
            motivos[m]+=1
            REJEICOES[m]+=1

    logging.info(
        "📊 %s [%s]: %s brutos / %s válidos",
        nicho,kw,len(resultados),len(filtrados)
    )

    avaliados=[]

    for p in filtrados:
        titulo=str(p.get("productName","")).strip()
        link=str(p.get("offerLink")or p.get("productLink")or "").strip()

        if not titulo or not link:
            continue

        produto_id=gerar_produto_id(titulo,link)
        base=chave_base_titulo(titulo)
        familia=identificar_familia(titulo)

        penal=penalidade_historico(produto_id)

        if penal>=100:
            motivos["historico_recente"]+=1
            continue

        if base and base in BASES_VISTAS:
            motivos["base_repetida"]+=1
            continue

        if link in usados_no_ciclo:
            motivos["link_repetido"]+=1
            continue

        if titulo_duplicado_forte(titulo):
            motivos["titulo_repetido"]+=1
            continue

        if not validar_relevancia_nicho(
            nicho,titulo,
            termo=termo,
            modelo=termo if e_moto else None,
            peca=peca
        ):
            motivos["relevancia"]+=1
            continue

        if produto_muito_parecido(titulo,ULTIMOS_TITULOS):
            motivos["parecido_historico"]+=1
            continue

        score=oferta_score(
            p,
            termo,
            familia_nova=familia not in FAMILIAS_VISTAS
        )-penal

        avaliados.append((score,p,base,familia,produto_id))

    avaliados.sort(key=lambda x:x[0],reverse=True)

    escolhidos=[]
    titulos_ciclo=[]

    for score,p,base,familia,produto_id in avaliados:
        if len(escolhidos)>=cota:
            break

        titulo=str(p.get("productName","")).strip()
        link=str(p.get("offerLink")or p.get("productLink")or "").strip()

        repetida_familia=familia in FAMILIAS_VISTAS

        # Não bloqueia família repetida.
        # Apenas prioriza diversidade.
        if repetida_familia and len(escolhidos)==0 and avaliados:
            score-=8

        if produto_muito_parecido(titulo,titulos_ciclo):
            motivos["similaridade_ciclo"]+=1
            continue

        escolhidos.append(p)
        titulos_ciclo.append(normalizar_texto(titulo))

        if base:
            BASES_VISTAS.add(base)

        FAMILIAS_VISTAS.add(familia)
        usados_no_ciclo.add(link)

        ULTIMAS_BUSCAS_SHOPEE.append(link)
        ULTIMOS_TITULOS.append(normalizar_texto(titulo))

        logging.info(
            "🏆 ESCOLHIDO | %s | família=%s | score=%.1f",
            titulo[:80],familia,score
        )

    del ULTIMAS_BUSCAS_SHOPEE[:-300]
    del ULTIMOS_TITULOS[:-150]

    if motivos:
        logging.info("📋 Motivos %s: %s",nicho,dict(motivos))

    return escolhidos,estado

# =========================
# FILTROS
# =========================
def motivo_rejeicao(p):
    titulo=str(p.get("productName","")).strip()
    link=str(p.get("offerLink")or p.get("productLink")or "").strip()

    preco=float(p.get("priceMin",0)or 0)
    comissao=float(p.get("commissionRate",0)or 0)
    vendas=int(p.get("sales",0)or 0)
    rating=float(p.get("ratingStar",0)or 0)

    if not titulo:return "sem_titulo"
    if not link:return "sem_link"
    if tem_bloqueio(titulo):return "bloqueio_texto"
    if preco<PRECO_MIN:return "preco_baixo"
    if preco>PRECO_MAX:return "preco_alto"

    # Comissão deixou de ser bloqueio.
    # Continua sendo considerada na pontuação.
    if comissao<COMISSAO_MIN:return "comissao_baixa"

    if vendas<VENDAS_MIN:return "vendas_baixas"
    if rating and rating<RATING_MIN:return "rating_baixo"
    if link in usados_no_ciclo:return "link_repetido"

    return None

# =========================
# COLETA PRINCIPAL
# =========================
def get_shopee_offers():
    global usados_no_ciclo,BASES_VISTAS,TERMOS_USADOS_CICLO,FAMILIAS_VISTAS

    usados_no_ciclo=set()
    BASES_VISTAS=set()
    FAMILIAS_VISTAS=set()
    TERMOS_USADOS_CICLO=set()

    candidatos=[]
    estado=carregar_estado()

    ordem=[
        "Moto",
        "Casa",
        "Maternidade",
        "Eletroeletrônicos",
        "Moda feminina",
        "Moda masculina"
    ]

    cotas={
        "Moto":2,
        "Casa":2,
        "Maternidade":2,
        "Eletroeletrônicos":2,
        "Moda feminina":1,
        "Moda masculina":1
    }

    for nicho in ordem:
        try:
            for _ in range(cotas[nicho]):

                if nicho=="Moto":
                    peca,motos,estado=get_combinacao_moto_dia(estado)

                    # Tenta os dois modelos, mas escolhe somente
                    # os melhores candidatos sem destruir a diversidade.
                    pool=[]

                    for moto in motos:
                        escolhidos,estado=selecionar_ofertas_termo(
                            nicho,moto,1,estado,True,peca
                        )
                        pool.extend((nicho,p) for p in escolhidos)

                    candidatos.extend(pool)

                else:
                    termo,estado=get_proximo_termo(nicho,estado)

                    escolhidos,estado=selecionar_ofertas_termo(
                        nicho,termo,1,estado
                    )

                    candidatos.extend((nicho,p) for p in escolhidos)

        except Exception as e:
            logging.error(
                "❌ Erro nicho %s: %s",
                nicho,e,
                exc_info=True
            )

    salvar_estado(estado)

    # Seleção final com diversidade de famílias.
    finais=[]
    familias_finais=set()
    restantes=[]

    candidatos.sort(
        key=lambda x:oferta_score(
            x[1],
            familia_nova=identificar_familia(x[1].get("productName","")) not in familias_finais
        ),
        reverse=True
    )

    for nicho,p in candidatos:
        familia=identificar_familia(p.get("productName",""))

        if familia not in familias_finais:
            finais.append((nicho,p))
            familias_finais.add(familia)
        else:
            restantes.append((nicho,p))

        if len(finais)>=MAX_OFERTAS:
            break

    # Completa a quantidade se ainda faltarem ofertas.
    if len(finais)<MAX_OFERTAS:
        for item in restantes:
            if item not in finais:
                finais.append(item)
            if len(finais)>=MAX_OFERTAS:
                break

    logging.info(
        "✅ POOL TOTAL: %s | RESULTADO CICLO: %s/%s | FAMÍLIAS: %s",
        len(candidatos),len(finais),MAX_OFERTAS,len(familias_finais)
    )

    return finais[:MAX_OFERTAS]

# =========================
# COPY / MENSAGENS
# =========================
CHAMADAS=[
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

ABERTURAS=[
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

GATILHOS=[
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

def aplicar_id_afiliado(link):
    try:
        p=urlparse(link)
        q=parse_qs(p.query)
        q["af_siteid"]=AFILIADO_ID
        return urlunparse(p._replace(query=urlencode(q,doseq=True)))
    except:
        return link

def gerar_link_whatsapp(msg):
    return f"https://wa.me/?text={quote(re.sub(r'<[^>]+>','',msg))}"

def gerar_copy(nome,preco,vendas,avaliacao,comissao,link,for_whatsapp=False):
    abertura=random.choice(
        [x for x in ABERTURAS if x not in usadas_abertura] or ABERTURAS
    )

    gatilho=random.choice(
        [x for x in GATILHOS if x not in usadas_gatilho] or GATILHOS
    )

    acao=random.choice(CHAMADAS)

    usadas_abertura.add(abertura)
    usadas_gatilho.add(gatilho)

    grupo=f"📢 Quer mais ofertas assim? Entre no nosso grupo: {LINK_GRUPO_OFERTAS}"

    if for_whatsapp:
        return (
            f"{abertura}\n\n"
            f"🔥 {nome}\n\n"
            f"{gatilho}\n\n"
            f"{acao}\n\n"
            f"💰 R$ {preco}\n"
            f"⭐ {avaliacao} | 🛒 {vendas} vendas\n\n"
            f"⚠️ Pode subir de preço\n\n"
            f"🛒 COMPRAR AGORA: {link}\n{grupo}"
        )

    return (
        f"{html.escape(abertura)}\n\n"
        f"🔥 <b>{html.escape(nome)}</b>\n\n"
        f"{html.escape(gatilho)}\n\n"
        f"{html.escape(acao)}\n\n"
        f"💰 <b>R$ {html.escape(str(preco))}</b>\n"
        f"⭐ <b>{html.escape(str(avaliacao))} | {html.escape(str(vendas))} vendas</b>\n"
        f"💸 Comissão: <b>{html.escape(str(comissao))}%</b>\n\n"
        f"⚠️ Pode subir de preço\n\n"
        
        f'<a href="{html.escape(link,quote=True)}">🛒 COMPRAR AGORA</a>\n'
        
        f'<a href="{html.escape(LINK_GRUPO_OFERTAS,quote=True)}">📲 Entrar no grupo de ofertas</a>'
    )

# =========================
# ENVIO TELEGRAM
# =========================
async def enviar_produto(context,item,chat_id):
    try:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=item["img"],
            caption=item["msg"],
            parse_mode="HTML"
        )
        return True

    except Exception as e:
        logging.warning("⚠️ Foto falhou: %s",e)

    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=item["msg"],
            parse_mode="HTML",
            disable_web_page_preview=False
        )
        return True

    except Exception as e2:
        logging.error("❌ Falha envio: %s",e2)
        return False

async def enviar_lote(context,selecionadas):
    await context.bot.send_message(
        chat_id=CHAT_ID_DESTINO,
        text="🚨 <b>OFERTAS NOVAS CHEGANDO...</b>",
        parse_mode="HTML"
    )

    await asyncio.sleep(5)

    for item in selecionadas:
        logging.info(
            "📤 Enviando VIP | nicho=%s | produto=%s",
            item["nicho_origem"],
            item["produto_id"]
        )

        if await enviar_produto(context,item,CHAT_ID_DESTINO):
            registrar_historico(item["produto_id"])

        await asyncio.sleep(40)

# =========================
# CICLO PRINCIPAL
# =========================
async def send_ofertas(context):
    try:
        logging.info("========== 🔄 INÍCIO DO CICLO ==========")

        if not dentro_do_horario():
            logging.info("⏹️ Fora do horário 05:30–21:30")
            return

        usadas_abertura.clear()
        usadas_gatilho.clear()

        shopee_ofertas=get_shopee_offers()

        if len(shopee_ofertas)<MIN_OFERTAS:
            logging.warning(
                "⚠️ Só %s ofertas. Mínimo %s. Não enviando.",
                len(shopee_ofertas),
                MIN_OFERTAS
            )
            return

        selecionadas=[]

        for nicho,item in shopee_ofertas[:MAX_OFERTAS]:
            try:
                nome=str(item.get("productName","")).strip()
                link_base=str(
                    item.get("offerLink")or
                    item.get("productLink")or
                    ""
                ).strip()

                if not nome or not link_base:
                    continue

                link=aplicar_id_afiliado(link_base)

                preco=float(item.get("priceMin",0)or 0)
                vendas=int(item.get("sales",0)or 0)
                rating=float(item.get("ratingStar",4.5)or 4.5)
                comissao=round(
                    float(item.get("commissionRate",0)or 0)*100,
                    2
                )

                imagem=str(item.get("imageUrl")or "").strip()

                preco_f=f"{preco:.2f}".replace(".",",")
                vendas_f=f"{vendas:,}".replace(",",".")
                rating_f=f"{rating:.1f}"

                msg=gerar_copy(
                    nome,
                    preco_f,
                    vendas_f,
                    rating_f,
                    comissao,
                    link
                )

                zap_msg=gerar_copy(
                    nome,
                    preco_f,
                    vendas_f,
                    rating_f,
                    0,
                    link,
                    True
                )

                zap=gerar_link_whatsapp(zap_msg)

                msg+=(
                    f'\n📲 <a href="{html.escape(zap,quote=True)}">'
                    f'Compartilhar no WhatsApp</a>'
                    f'\n━━━━━━━━━━━━━━━'
                    f'\n📢 <b>Ofertas Secretas</b>'
                )

                # MESMO ID usado na seleção, histórico e envio.
                produto_id=gerar_produto_id(nome,link_base)

                selecionadas.append({
                    "msg":msg,
                    "img":imagem,
                    "produto_id":produto_id,
                    "item_raw":item,
                    "nicho_origem":nicho
                })

            except Exception as e:
                logging.error(
                    "❌ Erro produto: %s",
                    e,
                    exc_info=True
                )

        if len(selecionadas)<MIN_OFERTAS:
            logging.warning(
                "⚠️ Só %s ofertas válidas após preparação.",
                len(selecionadas)
            )
            return

        await enviar_lote(context,selecionadas)

        # =========================
        # FREE
        # =========================
        logging.info("========== 🆓 BLOCO FREE ==========")

        estado=carregar_estado()
        idx=int(estado.get("free_nicho_idx",0)or 0)
        nicho_alvo=NICHOS_FREE_ROTA[idx%len(NICHOS_FREE_ROTA)]

        logging.info("🔄 Rodízio FREE -> %s",nicho_alvo)

        oferta_free=next(
            (x for x in selecionadas if x["nicho_origem"]==nicho_alvo),
            None
        )

        if oferta_free:
            if await enviar_produto(
                context,
                oferta_free,
                FREE_CHAT_ID
            ):
                # Já foi registrado no VIP.
                # Não cria outra entrada no histórico.
                logging.info(
                    "🆓 FREE enviado usando produto já registrado: %s",
                    oferta_free["produto_id"]
                )

        else:
            logging.warning(
                "⚠️ Sem oferta do nicho %s neste ciclo.",
                nicho_alvo
            )

        estado["free_nicho_idx"]=(idx+1)%len(NICHOS_FREE_ROTA)
        salvar_estado(estado)

        logging.info("========== ✅ CICLO FINALIZADO ==========")

    except Exception as e:
        logging.error(
            "❌ ERRO CICLO: %s",
            e,
            exc_info=True
        )

# =========================
# LOOP AUTOMÁTICO
# =========================
async def ofertas_loop(app):
    logging.info("🔄 Loop automático iniciado.")
    await asyncio.sleep(10)

    while True:
        try:
            await send_ofertas(
                type("Contexto",(),{"bot":app.bot})()
            )
        except Exception as e:
            logging.error(
                "❌ Erro loop: %s",
                e,
                exc_info=True
            )

        logging.info(
            "⏳ Próximo ciclo em %ss",
            CHECK_INTERVAL
        )

        await asyncio.sleep(CHECK_INTERVAL)

async def keep_alive():
    while True:
        logging.info(
            "💚 BOT VIVO | %s",
            datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M")
        )
        await asyncio.sleep(300)

# =========================
# INICIALIZAÇÃO
# =========================
async def post_init(app):
    app.bot_data["ofertas_task"]=asyncio.create_task(
        ofertas_loop(app)
    )

    app.bot_data["keepalive_task"]=asyncio.create_task(
        keep_alive()
    )

    logging.info("🤖 BOT RODANDO ESTÁVEL")

async def post_shutdown(app):
    for t in ["ofertas_task","keepalive_task"]:
        task=app.bot_data.get(t)
        if task:
            task.cancel()

    await asyncio.gather(
        *[
            x for x in [
                app.bot_data.get(t)
                for t in ["ofertas_task","keepalive_task"]
            ] if x
        ],
        return_exceptions=True
    )

async def error_handler(update,context):
    logging.error(
        "❌ ERRO: %s",
        context.error,
        exc_info=True
    )

def validar_config():
    faltam=[
        x for x in [
            "TELEGRAM_TOKEN",
            "SHOPEE_PASSWORD",
            "SHOPEE_APP_ID"
        ]
        if not globals().get(x,"")
    ]

    if faltam:
        raise RuntimeError(
            "Variáveis ausentes: "+", ".join(faltam)
        )

def iniciar():
    validar_config()

    logging.info("="*40)
    logging.info("SHOPEE BOT V29 - DIVERSIDADE INTELIGENTE")
    logging.info("Produto + família + histórico + exploração")
    logging.info("Moto=2 modelos | Comissão não bloqueia")
    logging.info("="*40)

    while True:
        try:
            app=(
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .post_shutdown(post_shutdown)
                .build()
            )

            app.add_error_handler(error_handler)
            app.run_polling(drop_pending_updates=True)

        except Exception as e:
            logging.error(
                "🔄 Reiniciando em 15s: %s",
                e
            )
            time.sleep(15)

if __name__=="__main__":
    iniciar()


