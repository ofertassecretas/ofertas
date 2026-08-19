
import asyncio,requests,logging,random,hashlib,time,json,os,html,re,tempfile
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime,time as dt_time,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse,parse_qs,urlencode,urlunparse,quote
from telegram.ext import ApplicationBuilder,ContextTypes

print("VERSAO SHOPEE V23 - RAILWAY COMPACTA")

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
COMISSAO_MIN=.03
RODIZIO_BUSCAS_VERSAO=4

FUSO_BR=ZoneInfo("America/Sao_Paulo")
ESTADO_FILE="estado_buscas.json"
HISTORICO_FILE="historico_envios.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

ULTIMAS_BUSCAS_SHOPEE=[]
ULTIMOS_TITULOS=[]
usadas_abertura=set()
usadas_gatilho=set()
usados_no_ciclo=set()
BASES_VISTAS=set()
REJEICOES=Counter()

# =========================
# CATÁLOGOS
# =========================

MOTOS="""titan 150|cb 300|factor 150|titan 160|tornado 250|fazer 150|titan 125|bros 160|twister 250|biz 125|pop 110|xre 300|crosser 150|xre 190|fazer 250|lander 250|bros 150|tenere 250|biz 100|twister 300""".split("|")

PECAS_MOTO="""kit relacao|kit embreagem|bateria|refil bomba combustivel|chicote fiação principal|bucha balança|burrinho de freio|estribo|pedal de marcha|pedal de freio|rolamento virabrequim|estator|chave ignição|punho chave luz|kit pisca seta|par pneu|bloco optico|retentor de bengala|bucha amortecedor|carburador corpo de injeção|kit cilindro|jogo de juntas|biela|valvulas escape admissão|kit freio a disco|disco de freio|tubo interno|vela iridium|pastilha freio|guidao|manopla|amortecedor|retrovisor|farol|lona de freio|cabo embreagem|cabo acelerador|coroa moto|pinhao moto|corrente moto|pedaleira|carenagem|lanterna traseira|capacete""".split("|")

MOTO_CICLOS_PRIORITARIOS=[
    ("titan 150","kit relacao"),
    ("fazer 250","kit relacao"),
    ("biz 100","jogo de juntas"),
    ("tornado 250","jogo de juntas"),
    ("bros 160","burrinho de freio"),
    ("factor 150","burrinho de freio"),
    ("twister 250","kit pneu"),
    ("pop 100","kit pneu")
]

def construir_roteiro_moto():
    r=[];u=set()
    for par in MOTO_CICLOS_PRIORITARIOS+[(m,p) for p in PECAS_MOTO for m in MOTOS]:
        if par not in u:r.append(par);u.add(par)
    return r

MOTO_ROTEIRO=construir_roteiro_moto()

PRODUTOS_NICHO={
"Casa":"""air fryer|fritadeira eletrica|aspirador|aspirador vertical|liquidificador|cafeteira|panela eletrica|panela de pressão|capa para colchão|jogo de pratos|jogo de copos|copo stanley|talher|panos de prato|toalhas de banho|coberta manta|lençol|cobre leito|mangueira de jardim|tapete|tapete sala|torneira de cozinha|filtro de barro|guarda roupas casal|guarda roupas portatil|cama casal|forma de silicone|sapateira|umidificador|ar condicionado|jogo de panelas|cortinas|tintas parede|tinta spray|frigideiras|rede de dormir|pipoqueira|mop|ventilador|batedeira|escorredor de louça|caixa organizadora|papel de parede|luminaria""".split("|"),

"Maternidade":"""carrinho bebe|berco bebe|fralda descartavel|fralda de pano|naninha|sapatinho|pagãozinho|coberdrom dupla face|kit toalha umedecida|toalha infantil banho|banheira|mictorio infantil|bebê reborn|carrinhos|piscina de bolinhas|kit bolsa maternidade|canguru|mosqueteiro|kit mamadeira|kit bicos|baba eletronica|babá eletronica|ninho bebe|kit enxoval bebe|babador bebe|mordedor bebe|tapete infantil|cadeirinha bebe|almofada amamentacao|termometro infantil""".split("|"),

"Eletroeletrônicos":"""smartwatch|relogio inteligente|fone bluetooth|headset gamer|caixa de som bluetooth|caixa de som|soundbar|bastão pau de selfie|celular|smartphone|smart tv|televisão|video game|fones de ouvido|capinha celular|pelicula celular|massageador|balança digital|aparelho medidor de pressão|massageador portatil|webcam camera|pen drive|impressora termica|maquina de impressão 3d|computador|cpu gamer|cpu|notebook|drone|camera de segurança|gopro|tablet|ssd|mouse gamer|teclado mecanico|power bank|carregador turbo|suporte celular carro""".split("|"),

"Moda feminina":"""vestido feminino|conjunto feminino|kit calcinhas|biquines|biquini|saida de praia|maquiagens|roupa academia|calça jean|calça leggin|saia longa|vestido lovito|sandalias|pijamas|pijamas mãe e filha|blusa regata|kit sutian|bermuda modeladora|oculos de sol|calça social|vestido midi|jaqueta feminina|casaco feminino|conjunto alfaiataria|short feminino|macacao feminino|tenis feminino|bolsa feminina|blazer feminino|saia jeans|top feminino|body feminino""".split("|"),

"Moda masculina":"""camiseta masculina|relogios esportivos|bermudas jeans|relogio de quartzo|camisetas regatas|camisa polo|camisa de linho|terno|blazer|camisa tshort|kit meias|barbeador|meias esportivas|oculos de sol|toucas|calção de futebol|tenis futebol|chuteiras|camisa termica|bermuda masculina|jaqueta masculina|tenis masculino|carteira masculina|kit cueca|calça jeans masculina|camisa social masculina|moletom masculino|sapatenis masculino""".split("|")
}

FAMILIAS_EXTRA={
"air_fryer":["air fryer","airfryer","fritadeira"],
"fone_bluetooth":["fone bluetooth","fones de ouvido","headset","earbud"],
"smartwatch":["smartwatch","relogio inteligente","relógio inteligente"],
"caixa_som":["caixa de som","speaker","soundbar"],
"smart_tv":["smart tv","televisão","tv"],
"notebook":["notebook","notbook","laptop"],
"tablet":["tablet","ipad","galaxy tab","xiaomi pad"],
"celular":["celular","smartphone","telefone","iphone"],
"maternidade_bebe":["bebe","bebê","fralda","carrinho","berco","mamadeira","ninho","babá","baba"],
"moda_fem":["vestido","conjunto","saia","bolsa","sandalia","tenis feminino","body"],
"moda_masc":["camisa","camiseta","calça","tenis masculino","jaqueta","bermuda","sapatenis"],
"casa_lar":["tapete","lençol","cortina","organizador","caixa organizadora","luminaria","pipoqueira","air fryer"],
"moto_geral":["capacete","vela","pastilha","lona","kit relação","corrente","coroa","pinhão","guidao","guidão","retrovisor","farol","lanterna"]
}

NICHOS_FREE_ROTA=[
    "Moto","Casa","Moda feminina","Moda masculina",
    "Maternidade","Eletroeletrônicos"
]

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
        try:
            if "tmp" in locals() and os.path.exists(tmp):os.remove(tmp)
        except:pass

def carregar_json(arquivo,padrao):
    try:
        if not os.path.exists(arquivo):return padrao
        with open(arquivo,"r",encoding="utf-8") as f:return json.load(f)
    except Exception as e:
        logging.error("Erro lendo %s: %s",arquivo,e)
        return padrao

def carregar_estado():
    estado=carregar_json(ESTADO_FILE,{})
    estado.setdefault("Moto",{})
    for n in PRODUTOS_NICHO:estado.setdefault(n,{})
    estado.setdefault("free_nicho_idx",0)

    if estado.get("rodizio_buscas_versao")!=RODIZIO_BUSCAS_VERSAO:
        logging.info("Atualizando estrutura do rodízio para versão %s",RODIZIO_BUSCAS_VERSAO)
        estado["Moto"]={"roteiro_idx":0}
        for n,produtos in PRODUTOS_NICHO.items():
            estado[n]={
                "resultado_idx":{},
                "produtos_ordem":list(range(len(produtos))),
                "produto_idx":0
            }
        estado["rodizio_buscas_versao"]=RODIZIO_BUSCAS_VERSAO

    estado["Moto"].setdefault("roteiro_idx",0)

    for n,produtos in PRODUTOS_NICHO.items():
        st=estado[n]
        st.setdefault("resultado_idx",{})
        st.setdefault("produtos_ordem",list(range(len(produtos))))
        st.setdefault("produto_idx",0)
        if len(st["produtos_ordem"])!=len(produtos):
            st["produtos_ordem"]=list(range(len(produtos)))
            st["produto_idx"]=0

    return estado

def salvar_estado(estado):salvar_json_seguro(ESTADO_FILE,estado)

def carregar_historico():return carregar_json(HISTORICO_FILE,{})

def salvar_historico(hist):salvar_json_seguro(HISTORICO_FILE,hist)

# =========================
# TEXTO / FILTROS
# =========================

def dentro_do_horario():
    agora=datetime.now(FUSO_BR).time()
    return dt_time(5,30)<=agora<=dt_time(21,30)

def normalizar_texto(txt):
    if not txt:return ""
    txt=str(txt).lower().strip()
    txt=re.sub(r"[^a-z0-9à-ÿ\s]"," ",txt)
    return re.sub(r"\s+"," ",txt)

def chave_base_titulo(titulo):
    stop={"premium","novo","promocao","promoção","super","original","profissional","casual","masculino","feminino","infantil","adulto","unissex","estica","kit","com","de","para","o","a","promo","oferta","modelo","versao","versão","linha","envio","usado","branco","preto","azul","vermelho","rosa","verde","amarelo","tamanho","tamanhos","unico","único","gamer","led","usb"}
    palavras=[x for x in normalizar_texto(titulo).split() if x not in stop and len(x)>2]
    return " ".join(sorted(palavras)[:8])

def tem_bloqueio(titulo):
    t=normalizar_texto(titulo)
    return any(x in t for x in ["teste","amostra","não compre","nao compre","produto teste","exemplo","dummy","vela led","vela decorativa","decorativa","decoração","casamento","festa"])

def titulo_duplicado_forte(titulo):
    t=normalizar_texto(titulo);base=chave_base_titulo(titulo)
    return any(
        t==prev or
        SequenceMatcher(None,t,prev).ratio()>=SIMILARIDADE_MAX or
        (base and base==chave_base_titulo(prev))
        for prev in ULTIMOS_TITULOS
    )

def produto_muito_parecido(titulo,titulos):
    t=normalizar_texto(titulo);base=chave_base_titulo(titulo)
    for prev in titulos:
        if SequenceMatcher(None,t,normalizar_texto(prev)).ratio()>=.84:return True
        if base and base==chave_base_titulo(prev):return True
    return False

def shop_type_score(shop_type):
    try:
        if 1 in shop_type:return 3
        if 4 in shop_type:return 2
        if 2 in shop_type:return 1
    except:pass
    return 0

def oferta_score(p,termo=""):
    try:
        vendas=int(p.get("sales",0) or 0)
        rating=float(p.get("ratingStar",0) or 0)
        comissao=float(p.get("commissionRate",0) or 0)
        preco=float(p.get("priceMin",0) or 0)
        nome=normalizar_texto(p.get("productName",""))
        termo=normalizar_texto(termo)
        score=min(vendas/8,25)+rating*2+comissao*100+shop_type_score(p.get("shopType",[]))
        if 50<=preco<=5000:score+=6
        if termo:
            score+=8 if termo in nome else sum(2 for x in termo.split() if x in nome)
        if any(x in nome for x in ["moto","bebê","bebe","smartwatch","ssd","fone","tablet","air fryer","tapete","capacete"]):score+=2
        return score
    except:return 0

def motivo_rejeicao(p):
    try:
        titulo=str(p.get("productName","")).strip()
        link=str(p.get("offerLink") or p.get("productLink") or "").strip()
        preco=float(p.get("priceMin",0) or 0)
        comissao=float(p.get("commissionRate",0) or 0)
        vendas=int(p.get("sales",0) or 0)
        rating=float(p.get("ratingStar",0) or 0)

        if not titulo:return "sem_titulo"
        if not link:return "sem_link"
        if tem_bloqueio(titulo):return "bloqueio_texto"
        if preco<PRECO_MIN:return "preco_baixo"
        if preco>PRECO_MAX:return "preco_alto"
        if comissao<COMISSAO_MIN:return "comissao_baixa"
        if vendas<VENDAS_MIN:return "vendas_baixas"
        if rating and rating<RATING_MIN:return "rating_baixo"
        if link in ULTIMAS_BUSCAS_SHOPEE or link in usados_no_ciclo:return "link_repetido"
        return None
    except Exception as e:
        return f"erro_validacao:{type(e).__name__}"

def historico_bloqueia(chave):
    hist=carregar_historico()
    if chave not in hist:return False
    try:
        data=datetime.fromisoformat(hist[chave])
        if data.tzinfo is None:data=data.replace(tzinfo=FUSO_BR)
        return datetime.now(FUSO_BR)-data<timedelta(days=HISTORICO_DIAS)
    except:return False

def registrar_historico(chave):
    hist=carregar_historico()
    hist[chave]=datetime.now(FUSO_BR).isoformat()

    limite=datetime.now(FUSO_BR)-timedelta(days=HISTORICO_DIAS*3)
    novo={}
    for k,v in hist.items():
        try:
            d=datetime.fromisoformat(v)
            if d.tzinfo is None:d=d.replace(tzinfo=FUSO_BR)
            if d>=limite:novo[k]=v
        except:pass

    salvar_historico(novo)

def parse_familia_from_title(titulo):
    t=normalizar_texto(titulo)
    for familia,termos in FAMILIAS_EXTRA.items():
        if any(normalizar_texto(term) in t for term in termos):return familia
    return "outros"

# =========================
# RODÍZIO
# =========================

def montar_catalogo():
    return {n:[(p,"","") for p in ps] for n,ps in PRODUTOS_NICHO.items()}

CATALOGOS=montar_catalogo()

def get_proximo_termo(nicho,estado):
    catalogo=CATALOGOS[nicho]
    st=estado[nicho]
    ordem=st.get("produtos_ordem") or list(range(len(catalogo)))
    idx=st.get("produto_idx",0)
    pos=ordem[idx%len(ordem)]
    st["produto_idx"]=(idx+1)%len(ordem)
    return catalogo[pos],estado

def get_proxima_combinacao_moto(estado):
    st=estado["Moto"]
    idx=st.get("roteiro_idx",0)
    par=MOTO_ROTEIRO[idx%len(MOTO_ROTEIRO)]
    st["roteiro_idx"]=(idx+1)%len(MOTO_ROTEIRO)
    logging.info("RODIZIO MOTO -> %s | %s",par[0],par[1])
    return par,estado

def carregar_indice_resultado(estado,nicho,chave):
    return estado[nicho].setdefault("resultado_idx",{}).get(chave,0)

def salvar_indice_resultado(estado,nicho,chave,valor):
    estado[nicho].setdefault("resultado_idx",{})[chave]=valor

# =========================
# VALIDAÇÃO DE NICHO
# =========================

def validar_modelo_titulo(titulo,termo):
    t=normalizar_texto(titulo)
    palavras=[x for x in normalizar_texto(termo).split() if len(x)>2]
    return not palavras or all(x in t for x in palavras)

def validar_peca_moto(titulo,peca):
    t=normalizar_texto(titulo)
    p=normalizar_texto(peca)
    aliases={
        "kit relacao":["kit relacao","kit relação","relacao completa","relação completa"],
        "jogo de juntas":["jogo de juntas","juntas","junta"],
        "burrinho de freio":["burrinho de freio","burrinho freio","cilindro mestre"],
        "kit pneu":["kit pneu","kit pneus","par pneu","par de pneus","pneus"]
    }
    return any(x in t for x in aliases.get(p,[p]))

def validar_relevancia_nicho(nicho,titulo,termo=None,modelo=None,peca=None):
    t=normalizar_texto(titulo)

    if nicho=="Eletroeletrônicos":
        if any(x in t for x in ["capa","pelicula","case"]) and not any(x in t for x in ["celular","tablet","smartphone","iphone"]):return False
        if any(x in t for x in ["smart tv","televisao","televisão"]) and any(x in t for x in ["mouse","teclado","ssd","notebook"]):return False

    if nicho=="Casa" and any(x in t for x in ["tinta","tintas"]) and not any(x in t for x in ["parede","spray","esmalte"]):return False
    if nicho=="Moda feminina" and any(x in t for x in ["masculino","homem","masc"]):return False
    if nicho=="Moda masculina" and any(x in t for x in ["feminino","mulher","menina"]):return False

    if nicho=="Maternidade" and any(x in t for x in ["organizador","cozinha","banheiro","carro"]) and not any(x in t for x in ["bebe","bebê","infantil","maternidade","fralda","carrinho","mamadeira","ninho"]):return False

    if nicho=="Moto":
        if modelo and not validar_modelo_titulo(titulo,modelo):return False
        if peca and not validar_peca_moto(titulo,peca):return False

    return True

# =========================
# SHOPEE
# =========================

def buscar_produtos_da_categoria_kw(palavra_chave,categoria):
    logging.info("Buscando em %s: %s",categoria,palavra_chave)

    timestamp=int(time.time())
    keyword=json.dumps(palavra_chave,ensure_ascii=False)

    query=f"""
    query {{
      productOfferV2(
        sortType: 2,
        limit: 50,
        keyword: {keyword},
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
        }}
      }}
    }}
    """

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
            logging.error("Erro GraphQL Shopee: %s",data["errors"])
            return []

        produtos=data.get("data",{}).get("productOfferV2",{}).get("nodes",[]) or []
        logging.info("Shopee retornou %s produtos para %s",len(produtos),palavra_chave)
        return produtos

    except requests.Timeout:
        logging.error("Timeout na Shopee para: %s",palavra_chave)
    except requests.RequestException as e:
        logging.error("Erro HTTP Shopee: %s",e)
    except ValueError as e:
        logging.error("JSON inválido da Shopee: %s",e)
    except Exception as e:
        logging.error("Erro inesperado Shopee: %s",e,exc_info=True)

    return []

def selecionar_ofertas_termo(nicho,termo,cota,estado,e_moto=False,peca=None):
    global BASES_VISTAS,REJEICOES

    kw=termo if not e_moto else f"{peca} {termo}"
    resultados=buscar_produtos_da_categoria_kw(kw,nicho)
    filtrados=[]
    rejeitados=Counter()

    for p in resultados:
        motivo=motivo_rejeicao(p)
        if motivo is None:filtrados.append(p)
        else:
            rejeitados[motivo]+=1
            REJEICOES[motivo]+=1

    logging.info("%s: %s brutos / %s filtrados",nicho,len(resultados),len(filtrados))

    if rejeitados:logging.info("%s rejeições: %s",nicho,dict(rejeitados))

    filtrados.sort(key=lambda x:oferta_score(x,termo),reverse=True)

    escolhidos=[]
    titulos_ciclo=[]
    familias_ciclo=Counter()
    motivos=Counter()

    chave_idx=f"{nicho}__{normalizar_texto(kw).replace(' ','_')}"
    idx_resultado=carregar_indice_resultado(estado,nicho,chave_idx)

    if filtrados:
        idx_resultado%=len(filtrados)
        filtrados=filtrados[idx_resultado:]+filtrados[:idx_resultado]

    for pos,p in enumerate(filtrados):
        if len(escolhidos)>=cota:break

        titulo=str(p.get("productName","")).strip()
        link=str(p.get("offerLink") or p.get("productLink") or "").strip()
        base=chave_base_titulo(titulo)
        familia=parse_familia_from_title(titulo)

        assinatura=f"{base}|{link}"
        produto_id=hashlib.md5(assinatura.encode()).hexdigest()

        if not link:
            motivos["sem_link"]+=1
            continue

        if base and base in BASES_VISTAS:
            motivos["base_repetida"]+=1
            continue

        if link in usados_no_ciclo or link in ULTIMAS_BUSCAS_SHOPEE:
            motivos["link_repetido"]+=1
            continue

        if historico_bloqueia(produto_id):
            motivos["historico"]+=1
            continue

        if titulo_duplicado_forte(titulo):
            motivos["titulo"]+=1
            continue

        if produto_muito_parecido(titulo,titulos_ciclo):
            motivos["similaridade"]+=1
            continue

        if not validar_relevancia_nicho(
            nicho,titulo,termo=termo,
            modelo=termo if e_moto else None,
            peca=peca
        ):
            motivos["relevancia"]+=1
            continue

        if familia!="outros" and familias_ciclo[familia]>=2:
            motivos["familia_limite"]+=1
            continue

        escolhidos.append(p)
        titulos_ciclo.append(normalizar_texto(titulo))
        familias_ciclo[familia]+=1

        if base:BASES_VISTAS.add(base)
        usados_no_ciclo.add(link)
        ULTIMAS_BUSCAS_SHOPEE.append(link)
        ULTIMOS_TITULOS.append(normalizar_texto(titulo))

        idx_resultado=(idx_resultado+pos+1)%max(1,len(filtrados))
        salvar_indice_resultado(estado,nicho,chave_idx,idx_resultado)

        logging.info("ESCOLHIDO [%s] %s",nicho,titulo)

    del ULTIMAS_BUSCAS_SHOPEE[:-300]
    del ULTIMOS_TITULOS[:-150]

    if motivos:logging.info("%s seleção: %s",nicho,dict(motivos))
    if len(escolhidos)<cota:logging.warning("%s conseguiu %s/%s",nicho,len(escolhidos),cota)

    return escolhidos,estado

def get_shopee_offers():
    global usados_no_ciclo,BASES_VISTAS

    usados_no_ciclo=set()
    BASES_VISTAS=set()

    candidatos=[]
    estado=carregar_estado()

    ordem=[
        "Moto","Casa","Maternidade",
        "Eletroeletrônicos","Moda feminina","Moda masculina"
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
                    (moto,peca),estado=get_proxima_combinacao_moto(estado)
                    escolhidos,estado=selecionar_ofertas_termo(
                        nicho,moto,1,estado,True,peca
                    )
                else:
                    (termo,_,_),estado=get_proximo_termo(nicho,estado)
                    escolhidos,estado=selecionar_ofertas_termo(
                        nicho,termo,1,estado
                    )

                candidatos.extend((nicho,p) for p in escolhidos)

        except Exception as e:
            logging.error("Erro no nicho %s: %s",nicho,e,exc_info=True)

    salvar_estado(estado)
    candidatos.sort(key=lambda x:oferta_score(x[1]),reverse=True)

    logging.info("TOTAL DE OFERTAS: %s",len(candidatos))
    return candidatos[:MAX_OFERTAS]

# =========================
# COPY
# =========================

CHAMADAS_ACAO=[
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
        parsed=urlparse(link)
        query=parse_qs(parsed.query)
        query["af_siteid"]=AFILIADO_ID
        return urlunparse(parsed._replace(query=urlencode(query,doseq=True)))
    except:return link

def gerar_link_whatsapp(msg):
    texto=re.sub(r"<[^>]+>","",msg)
    return f"https://wa.me/?text={quote(texto)}"

def gerar_copy(nome,preco,vendas,avaliacao,comissao,link,for_whatsapp=False):
    global usadas_abertura,usadas_gatilho

    abertura=random.choice(
        [x for x in ABERTURAS if x not in usadas_abertura] or ABERTURAS
    )
    gatilho=random.choice(
        [x for x in GATILHOS if x not in usadas_gatilho] or GATILHOS
    )
    acao=random.choice(CHAMADAS_ACAO)

    usadas_abertura.add(abertura)
    usadas_gatilho.add(gatilho)

    grupo=f"📢 Quer mais ofertas assim? Entre no nosso grupo: {LINK_GRUPO_OFERTAS}"

    if for_whatsapp:
        return (
            f"{abertura}\n\n"
            f"*🔥 {nome}*\n\n"
            f"{gatilho}\n\n"
            f"{acao}\n\n"
            f"*💰 R$ {preco}*\n"
            f"*⭐ {avaliacao} | 🛒 {vendas} vendas*\n\n"
            f"⚠️ Pode subir de preço\n\n"
            f"🛒 COMPRAR AGORA: {link}\n"
            f"{grupo}"
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
        logging.warning("Foto falhou, tentando mensagem: %s",e)

        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=item["msg"],
                parse_mode="HTML",
                disable_web_page_preview=False
            )
            return True
        except Exception as e2:
            logging.error("Falha total Telegram: %s",e2,exc_info=True)
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
            "Enviando VIP | nicho=%s | produto=%s",
            item["nicho_origem"],
            item["item_raw"].get("productName","")
        )

        ok=await enviar_produto(context,item,CHAT_ID_DESTINO)

        if ok:
            registrar_historico(item["produto_id"])

        await asyncio.sleep(40)

# =========================
# CICLO PRINCIPAL
# =========================

async def send_ofertas(context):
    try:
        logging.info("========== INÍCIO DO CICLO ==========")

        if not dentro_do_horario():
            logging.info("Fora do horário 05:30–21:30")
            return

        usadas_abertura.clear()
        usadas_gatilho.clear()

        shopee_ofertas=get_shopee_offers()

        if len(shopee_ofertas)<MIN_OFERTAS:
            logging.warning(
                "Apenas %s ofertas válidas. Mínimo=%s. Não enviando.",
                len(shopee_ofertas),MIN_OFERTAS
            )
            return

        selecionadas=[]

        for nicho,item in shopee_ofertas[:MAX_OFERTAS]:
            try:
                nome=str(item.get("productName","")).strip()
                link_base=str(item.get("offerLink") or item.get("productLink") or "").strip()

                if not nome or not link_base:
                    continue

                link=aplicar_id_afiliado(link_base)

                preco=float(item.get("priceMin",0) or 0)
                vendas=int(item.get("sales",0) or 0)
                rating=float(item.get("ratingStar",4.5) or 4.5)
                comissao=round(float(item.get("commissionRate",0) or 0)*100,2)

                imagem=str(item.get("imageUrl") or "").strip()

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

                assinatura=f"{nome}|{link_base}"
                produto_id=hashlib.md5(assinatura.encode()).hexdigest()

                selecionadas.append({
                    "msg":msg,
                    "img":imagem,
                    "produto_id":produto_id,
                    "item_raw":item,
                    "nicho_origem":nicho
                })

            except Exception as e:
                logging.error("Erro preparando produto: %s",e,exc_info=True)

        if len(selecionadas)<MIN_OFERTAS:
            logging.warning(
                "Após preparação ficaram somente %s ofertas.",
                len(selecionadas)
            )
            return

        logging.info("Selecionadas para envio: %s",len(selecionadas))

        await enviar_lote(context,selecionadas)

        # =========================
        # FREE
        # =========================

        logging.info("========== BLOCO FREE ==========")

        estado=carregar_estado()
        idx=int(estado.get("free_nicho_idx",0) or 0)
        nicho_alvo=NICHOS_FREE_ROTA[idx%len(NICHOS_FREE_ROTA)]

        logging.info("Rodízio FREE -> %s",nicho_alvo)

        oferta_free=next(
            (x for x in selecionadas if x["nicho_origem"]==nicho_alvo),
            None
        )

        if oferta_free:
            ok=await enviar_produto(
                context,
                oferta_free,
                FREE_CHAT_ID
            )

            if ok:
                registrar_historico(oferta_free["produto_id"])
        else:
            logging.warning(
                "Não existe oferta do nicho %s neste ciclo.",
                nicho_alvo
            )

        estado["free_nicho_idx"]=(idx+1)%len(NICHOS_FREE_ROTA)
        salvar_estado(estado)

        logging.info("========== CICLO FINALIZADO ==========")

    except Exception as e:
        logging.error("ERRO CRÍTICO NO CICLO: %s",e,exc_info=True)

# =========================
# LOOP AUTOMÁTICO
# =========================

async def ofertas_loop(app):
    logging.info("Loop automático iniciado.")

    await asyncio.sleep(10)

    while True:
        try:
            await send_ofertas(
                type(
                    "Contexto",
                    (),
                    {"bot":app.bot}
                )()
            )
        except asyncio.CancelledError:
            logging.info("Loop de ofertas cancelado.")
            raise
        except Exception as e:
            logging.error("Erro no loop: %s",e,exc_info=True)

        logging.info(
            "Próximo ciclo em %s segundos.",
            CHECK_INTERVAL
        )

        try:
            await asyncio.sleep(CHECK_INTERVAL)
        except asyncio.CancelledError:
            logging.info("Sleep do loop cancelado.")
            raise

async def keep_alive():
    while True:
        logging.info("BOT VIVO | %s",datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M:%S"))
        await asyncio.sleep(300)

# =========================
# TELEGRAM
# =========================

async def post_init(app):
    app.bot_data["ofertas_task"]=asyncio.create_task(ofertas_loop(app))
    app.bot_data["keepalive_task"]=asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTÁVEL")

async def post_shutdown(app):
    for chave in ["ofertas_task","keepalive_task"]:
        task=app.bot_data.get(chave)
        if task:
            task.cancel()

    tasks=[
        x for x in [
            app.bot_data.get("ofertas_task"),
            app.bot_data.get("keepalive_task")
        ] if x
    ]

    if tasks:
        await asyncio.gather(*tasks,return_exceptions=True)

    logging.info("Tasks encerradas.")

async def error_handler(update:object,context:ContextTypes.DEFAULT_TYPE):
    logging.error(
        "ERRO TELEGRAM: %s",
        context.error,
        exc_info=True
    )

# =========================
# INICIALIZAÇÃO
# =========================

def validar_config():
    erros=[]

    if not TELEGRAM_TOKEN:
        erros.append("TELEGRAM_TOKEN")

    if not SHOPEE_PASSWORD:
        erros.append("SHOPEE_PASSWORD")

    if not SHOPEE_APP_ID:
        erros.append("SHOPEE_APP_ID")

    if erros:
        raise RuntimeError(
            "Variáveis de ambiente ausentes: "+", ".join(erros)
        )

def iniciar():
    validar_config()

    logging.info("====================================")
    logging.info("SHOPEE BOT V23")
    logging.info("Fuso: %s",FUSO_BR)
    logging.info("Intervalo: %s segundos",CHECK_INTERVAL)
    logging.info("Horário: 05:30 até 21:30")
    logging.info("====================================")

    while True:
        app=None

        try:
            app=(
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .post_shutdown(post_shutdown)
                .build()
            )

            app.add_error_handler(error_handler)

            logging.info("Conectando ao Telegram...")
            app.run_polling(
                allowed_updates=None,
                drop_pending_updates=True
            )

        except KeyboardInterrupt:
            logging.info("Bot encerrado manualmente.")
            break

        except Exception as e:
            logging.error(
                "BOT PAROU. Reiniciando em 15 segundos: %s",
                e,
                exc_info=True
            )
            time.sleep(15)

if __name__=="__main__":
    iniciar()




