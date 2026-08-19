import asyncio,requests,logging,random,hashlib,time,json,os,html,re,tempfile
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime,time as dt_time,timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse,parse_qs,urlencode,urlunparse,quote
from telegram.ext import ApplicationBuilder,ContextTypes
print("VERSAO SHOPEE V24-ROTACAO - RAILWAY COMPACTA")
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
RODIZIO_BUSCAS_VERSAO=5
FUSO_BR=ZoneInfo("America/Sao_Paulo")
ESTADO_FILE="estado_buscas.json"
HISTORICO_FILE="historico_envios.json"
logging.basicConfig(level=logging.INFO,format="%(asctime)s - %(levelname)s - %(message)s")
ULTIMAS_BUSCAS_SHOPEE,ULTIMOS_TITULOS=[],[]
usadas_abertura,usadas_gatilho,usados_no_ciclo,BASES_VISTAS=set(),set(),set(),set()
REJEICOES=Counter()
# =========================
# CATÁLOGOS
# =========================
MOTOS=["titan 150","cb 300","factor 150","titan 160","tornado 250","fazer 150","titan 125","bros 160","twister 250","biz 125","pop 110","xre 300","crosser 150","xre 190","fazer 250","lander 250","bros 150","tenere 250","biz 100","twister 300"]
PECAS_MOTO=["kit relacao","kit embreagem","bateria","refil bomba combustivel","chicote fiação principal","bucha balança","burrinho de freio","estribo","pedal de marcha","pedal de freio","rolamento virabrequim","estator","chave ignição","punho chave luz","kit pisca seta","par pneu","bloco optico","retentor de bengala","bucha amortecedor","carburador corpo de injeção","kit cilindro","jogo de juntas","biela","valvulas escape admissão","kit freio a disco","disco de freio","tubo interno","vela iridium","pastilha freio","guidao","manopla","amortecedor","retrovisor","farol","lona de freio","cabo embreagem","cabo acelerador","coroa moto","pinhao moto","corrente moto","pedaleira","carenagem","lanterna traseira","capacete"]
PRODUTOS_NICHO={
"Casa":["air fryer","fritadeira eletrica","aspirador","aspirador vertical","liquidificador","cafeteira","panela eletrica","panela de pressão","capa para colchão","jogo de pratos","jogo de copos","copo stanley","talher","panos de prato","toalhas de banho","coberta manta","lençol","cobre leito","mangueira de jardim","tapete","tapete sala","torneira de cozinha","filtro de barro","guarda roupas casal","guarda roupas portatil","cama casal","forma de silicone","sapateira","umidificador","ar condicionado","jogo de panelas","cortinas","tintas parede","tinta spray","frigideiras","rede de dormir","pipoqueira","mop","ventilador","batedeira","escorredor de louça","caixa organizadora","papel de parede","luminaria"],
"Maternidade":["carrinho bebe","berco bebe","fralda descartavel","fralda de pano","naninha","sapatinho","pagãozinho","coberdrom dupla face","kit toalha umedecida","toalha infantil banho","banheira","mictorio infantil","bebê reborn","carrinhos","piscina de bolinhas","kit bolsa maternidade","canguru","mosqueteiro","kit mamadeira","kit bicos","baba eletronica","babá eletronica","ninho bebe","kit enxoval bebe","babador bebe","mordedor bebe","tapete infantil","cadeirinha bebe","almofada amamentacao","termometro infantil"],
"Eletroeletrônicos":["smartwatch","relogio inteligente","fone bluetooth","headset gamer","caixa de som bluetooth","caixa de som","soundbar","bastão pau de selfie","celular","smartphone","smart tv","televisão","video game","fones de ouvido","capinha celular","pelicula celular","massageador","balança digital","aparelho medidor de pressão","massageador portatil","webcam camera","pen drive","impressora termica","maquina de impressão 3d","computador","cpu gamer","cpu","notebook","drone","camera de segurança","gopro","tablet","ssd","mouse gamer","teclado mecanico","power bank","carregador turbo","suporte celular carro"],
"Moda feminina":["vestido feminino","conjunto feminino","kit calcinhas","biquines","biquini","saida de praia","maquiagens","roupa academia","calça jean","calça leggin","saia longa","vestido lovito","sandalias","pijamas","pijamas mãe e filha","blusa regata","kit sutian","bermuda modeladora","oculos de sol","calça social","vestido midi","jaqueta feminina","casaco feminino","conjunto alfaiataria","short feminino","macacao feminino","tenis feminino","bolsa feminina","blazer feminino","saia jeans","top feminino","body feminino"],
"Moda masculina":["camiseta masculina","relogios esportivos","bermudas jeans","relogio de quartzo","camisetas regatas","camisa polo","camisa de linho","terno","blazer","camisa tshort","kit meias","barbeador","meias esportivas","oculos de sol","toucas","calção de futebol","tenis futebol","chuteiras","camisa termica","bermuda masculina","jaqueta masculina","tenis masculino","carteira masculina","kit cueca","calça jeans masculina","camisa social masculina","moletom masculino","sapatenis masculino"]
}
FAMILIAS_EXTRA={"air_fryer":["air fryer","airfryer","fritadeira"],"fone_bluetooth":["fone bluetooth","fones de ouvido","headset"],"smartwatch":["smartwatch","relogio inteligente"],"caixa_som":["caixa de som","speaker","soundbar"],"smart_tv":["smart tv","televisão","tv"],"notebook":["notebook","laptop"],"tablet":["tablet","ipad"],"celular":["celular","smartphone","iphone"],"maternidade_bebe":["bebe","bebê","fralda","carrinho","berco","mamadeira","ninho"],"moda_fem":["vestido","conjunto","saia","bolsa","sandalia","tenis feminino","body"],"moda_masc":["camisa","camiseta","calça","tenis masculino","jaqueta","bermuda"],"casa_lar":["tapete","lençol","cortina","organizador","caixa organizadora","luminaria","air fryer"],"moto_geral":["capacete","vela","pastilha","lona","kit relação","corrente","coroa","pinhão","guidao","retrovisor","farol"]}
NICHOS_FREE_ROTA=["Moto","Casa","Moda feminina","Moda masculina","Maternidade","Eletroeletrônicos"]
# =========================
# ARQUIVOS / ESTADO
# =========================
def salvar_json_seguro(arquivo,dados):
    try:
        pasta=os.path.dirname(os.path.abspath(arquivo)) or "."
        fd,tmp=tempfile.mkstemp(prefix=".tmp_",dir=pasta,text=True)
        with os.fdopen(fd,"w",encoding="utf-8") as f:json.dump(dados,f,ensure_ascii=False,indent=2)
        os.replace(tmp,arquivo)
    except Exception as e:
        logging.error("Erro salvando %s: %s",arquivo,e)
def carregar_json(arquivo,padrao):
    try:
        if not os.path.exists(arquivo):return padrao
        with open(arquivo,"r",encoding="utf-8") as f:return json.load(f)
    except Exception as e:
        logging.error("Erro lendo %s: %s",arquivo,e);return padrao
def carregar_estado():
    estado=carregar_json(ESTADO_FILE,{})
    if estado.get("rodizio_buscas_versao")!=RODIZIO_BUSCAS_VERSAO:
        logging.info("Reiniciando rodízio versão %s",RODIZIO_BUSCAS_VERSAO)
        estado={"rodizio_buscas_versao":RODIZIO_BUSCAS_VERSAO,"Moto":{"data_rodizio":"","peca_idx":0,"moto_par_idx":0}}
        for n in PRODUTOS_NICHO:estado[n]={"ordem":list(range(len(PRODUTOS_NICHO[n]))),"pos":0}
    estado.setdefault("Moto",{}).setdefault("data_rodizio","")
    estado["Moto"].setdefault("peca_idx",0);estado["Moto"].setdefault("moto_par_idx",0)
    for n in PRODUTOS_NICHO:
        estado.setdefault(n,{}).setdefault("ordem",list(range(len(PRODUTOS_NICHO[n]))))
        estado[n].setdefault("pos",0)
    estado.setdefault("free_nicho_idx",0)
    return estado
def salvar_estado(estado):salvar_json_seguro(ESTADO_FILE,estado)
def carregar_historico():return carregar_json(HISTORICO_FILE,{})
def salvar_historico(hist):salvar_json_seguro(HISTORICO_FILE,hist)
# =========================
# ROTAÇÃO MOTO+PEÇA (LÓGICA PRINCIPAL CORRIGIDA)
# =========================
def gerar_pares_motos():
    pares=[MOTOS[i:i+2] for i in range(0,len(MOTOS),2)]
    if len(MOTOS)%2:pares[-1].append(MOTOS[0])
    return pares
def get_combinacao_moto_dia(estado):
    hoje=datetime.now(FUSO_BR).strftime("%Y%m%d")
    pecas,pares=PECAS_MOTO,gerar_pares_motos()
    if estado["Moto"]["data_rodizio"]!=hoje:
        logging.info("Novo dia → reiniciando sequência peças/motos")
        estado["Moto"]["data_rodizio"]=hoje
        estado["Moto"]["peca_idx"]=estado["Moto"]["moto_par_idx"]=0
    pi,mi=estado["Moto"]["peca_idx"]%len(pecas),estado["Moto"]["moto_par_idx"]%len(pares)
    peca=pecas[pi]
    motos=pares[mi]
    estado["Moto"]["moto_par_idx"]+=1
    if estado["Moto"]["moto_par_idx"]>=len(pares):
        estado["Moto"]["moto_par_idx"]=0
        estado["Moto"]["peca_idx"]+=1
    logging.info("RODÍZIO MOTO → Peça: %s | Motos: %s",peca," + ".join(motos))
    return peca,motos,estado
# =========================
# TEXTO / FILTROS
# =========================
def dentro_do_horario():
    agora=datetime.now(FUSO_BR).time()
    return dt_time(5,30)<=agora<=dt_time(21,30)
def normalizar_texto(txt):
    if not txt:return ""
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9à-ÿ\s]"," ",str(txt).lower().strip()))
def chave_base_titulo(titulo):
    stop={"premium","novo","promocao","promoção","super","original","profissional","casual","masculino","feminino","infantil","adulto","unissex","estica","kit","com","de","para","o","a","promo","oferta","modelo","versao","versão","linha","envio","usado","branco","preto","azul","vermelho","rosa","verde","amarelo","tamanho","tamanhos","unico","único","gamer","led","usb"}
    palavras=[x for x in normalizar_texto(titulo).split() if x not in stop and len(x)>2]
    return " ".join(sorted(palavras)[:8])
def tem_bloqueio(titulo):
    t=normalizar_texto(titulo)
    return any(x in t for x in ["teste","amostra","não compre","nao compre","produto teste","exemplo","dummy","vela led","vela decorativa","decorativa","decoração","casamento","festa"])
def titulo_duplicado_forte(titulo):
    t,base=normalizar_texto(titulo),chave_base_titulo(titulo)
    return any(t==prev or SequenceMatcher(None,t,prev).ratio()>=SIMILARIDADE_MAX or (base and base==chave_base_titulo(prev)) for prev in ULTIMOS_TITULOS)
def produto_muito_parecido(titulo,titulos):
    t,base=normalizar_texto(titulo),chave_base_titulo(titulo)
    return any(SequenceMatcher(None,t,normalizar_texto(p)).ratio()>=.84 or (base and base==chave_base_titulo(p)) for p in titulos)
def shop_type_score(shop_type):
    try:return 3 if 1 in shop_type else 2 if 4 in shop_type else 1 if 2 in shop_type else 0
    except:return 0
def oferta_score(p,termo=""):
    try:
        vendas,rating=int(p.get("sales",0)or 0),float(p.get("ratingStar",0)or 0)
        comissao,preco=float(p.get("commissionRate",0)or 0),float(p.get("priceMin",0)or 0)
        nome=normalizar_texto(p.get("productName",""))
        termo_n=normalizar_texto(termo)
        score=min(vendas/8,25)+rating*2+comissao*100+shop_type_score(p.get("shopType",[]))
        if 50<=preco<=5000:score+=6
        if termo_n:score+=8 if termo_n in nome else sum(2 for x in termo_n.split() if x in nome)
        if any(x in nome for x in ["moto","bebê","bebe","smartwatch","ssd","fone","tablet","air fryer","tapete","capacete"]):score+=2
        return score
    except:return 0
def motivo_rejeicao(p):
    titulo=str(p.get("productName","")).strip()
    link=str(p.get("offerLink")or p.get("productLink")or "").strip()
    preco,comissao=float(p.get("priceMin",0)or 0),float(p.get("commissionRate",0)or 0)
    vendas,rating=int(p.get("sales",0)or 0),float(p.get("ratingStar",0)or 0)
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
def historico_bloqueia(chave):
    hist=carregar_historico()
    if chave not in hist:return False
    try:
        d=datetime.fromisoformat(hist[chave])
        if d.tzinfo is None:d=d.replace(tzinfo=FUSO_BR)
        return datetime.now(FUSO_BR)-d<timedelta(days=HISTORICO_DIAS)
    except:return False
def registrar_historico(chave):
    hist=carregar_historico()
    hist[chave]=datetime.now(FUSO_BR).isoformat()
    limite=datetime.now(FUSO_BR)-timedelta(days=HISTORICO_DIAS*3)
    salvar_historico({k:v for k,v in hist.items() if datetime.fromisoformat(v).replace(tzinfo=FUSO_BR)>=limite})
def parse_familia_from_title(titulo):
    t=normalizar_texto(titulo)
    return next((f for f,ts in FAMILIAS_EXTRA.items() if any(normalizar_texto(x)in t for x in ts)),"outros")
# =========================
# RODÍZIO DEMAIS NICHOS
# =========================
def get_proximo_termo(nicho,estado):
    st=estado[nicho];idx=st["pos"]%len(st["ordem"]);pos=st["ordem"][idx]
    st["pos"]+=1;return PRODUTOS_NICHO[nicho][pos],estado
# =========================
# VALIDAÇÃO
# =========================
def validar_modelo_titulo(titulo,termo):
    t=normalizar_texto(titulo);ps=[x for x in normalizar_texto(termo).split()if len(x)>2]
    return not ps or all(x in t for x in ps)
def validar_peca_moto(titulo,peca):
    t,p=normalizar_texto(titulo),normalizar_texto(peca)
    aliases={"kit relacao":["kit relacao","kit relação","relação completa"],"jogo de juntas":["jogo de juntas","juntas"],"burrinho de freio":["burrinho de freio","cilindro mestre"],"par pneu":["par pneu","kit pneu","pneus"]}
    return any(x in t for x in aliases.get(p,[p]))
def validar_relevancia_nicho(nicho,titulo,termo=None,modelo=None,peca=None):
    t=normalizar_texto(titulo)
    if nicho=="Eletroeletrônicos" and any(x in t for x in ["capa","pelicula"]) and not any(x in t for x in ["celular","tablet","iphone"]):return False
    if nicho=="Casa" and any(x in t for x in ["tinta"]) and not any(x in t for x in ["parede","spray"]):return False
    if nicho=="Moda feminina" and any(x in t for x in ["masculino","homem"]):return False
    if nicho=="Moda masculina" and any(x in t for x in ["feminino","mulher"]):return False
    if nicho=="Maternidade" and any(x in t for x in ["organizador","cozinha"]) and not any(x in t for x in ["bebe","infantil"]):return False
    if nicho=="Moto":
        if modelo and not validar_modelo_titulo(titulo,modelo):return False
        if peca and not validar_peca_moto(titulo,peca):return False
    return True
# =========================
# SHOPEE API
# =========================
def buscar_produtos_da_categoria_kw(palavra_chave,categoria):
    logging.info("Buscando em %s: %s",categoria,palavra_chave)
    timestamp=int(time.time())
    keyword=json.dumps(palavra_chave,ensure_ascii=False)
    query=f'query {{productOfferV2(sortType:2,limit:50,keyword:{keyword},isAMSOffer:true){{nodes{{productName,priceMin,priceMax,commissionRate,sales,ratingStar,productLink,offerLink,imageUrl,shopType}}}}}}}'
    payload=json.dumps({"query":query},ensure_ascii=False)
    assinatura=SHOPEE_APP_ID+str(timestamp)+payload+SHOPEE_PASSWORD
    signature=hashlib.sha256(assinatura.encode()).hexdigest()
    headers={"Content-Type":"application/json","Authorization":f"SHA256 Credential={SHOPEE_APP_ID}, Timestamp={timestamp}, Signature={signature}","User-Agent":"Mozilla/5.0"}
    try:
        r=requests.post(SHOPEE_GRAPHQL_URL,data=payload.encode("utf-8"),headers=headers,timeout=25)
        r.raise_for_status();data=r.json()
        if data.get("errors"):logging.error("Erro GraphQL: %s",data["errors"]);return []
        prods=data.get("data",{}).get("productOfferV2",{}).get("nodes",[]) or []
        logging.info("Retornou %s produtos",len(prods));return prods
    except Exception as e:logging.error("Erro Shopee: %s",e);return []
def selecionar_ofertas_termo(nicho,termo,cota,estado,e_moto=False,peca=None):
    kw=termo if not e_moto else f"{peca} {termo}"
    resultados=buscar_produtos_da_categoria_kw(kw,nicho)
    filtrados,motivos=[],Counter()
    for p in resultados:
        m=motivo_rejeicao(p)
        if m is None:filtrados.append(p)
        else:motivos[m]+=1;REJEICOES[m]+=1
    logging.info("%s: %s brutos / %s válidos",nicho,len(resultados),len(filtrados))
    filtrados.sort(key=lambda x:oferta_score(x,termo),reverse=True)
    escolhidos,titulos_ciclo,familias_ciclo=[],[],Counter()
    for p in filtrados:
        if len(escolhidos)>=cota:break
        titulo=str(p.get("productName","")).strip()
        link=str(p.get("offerLink")or p.get("productLink")or "").strip()
        base=chave_base_titulo(titulo);familia=parse_familia_from_title(titulo)
        assinatura=f"{base}|{link}";produto_id=hashlib.md5(assinatura.encode()).hexdigest()
        if not link:motivos["sem_link"]+=1;continue
        if base and base in BASES_VISTAS:motivos["base_repetida"]+=1;continue
        if link in usados_no_ciclo:motivos["link_repetido"]+=1;continue
        if historico_bloqueia(produto_id):motivos["historico"]+=1;continue
        if titulo_duplicado_forte(titulo):motivos["titulo"]+=1;continue
        if produto_muito_parecido(titulo,titulos_ciclo):motivos["similaridade"]+=1;continue
        if not validar_relevancia_nicho(nicho,titulo,termo=termo,modelo=termo if e_moto else None,peca=peca):motivos["relevancia"]+=1;continue
        if familia!="outros" and familias_ciclo[familia]>=2:motivos["familia_limite"]+=1;continue
        escolhidos.append(p);titulos_ciclo.append(normalizar_texto(titulo))
        familias_ciclo[familia]+=1;BASES_VISTAS.add(base);usados_no_ciclo.add(link)
        ULTIMAS_BUSCAS_SHOPEE.append(link);ULTIMOS_TITULOS.append(normalizar_texto(titulo))
    del ULTIMAS_BUSCAS_SHOPEE[:-300];del ULTIMOS_TITULOS[:-150]
    if motivos:logging.info("Motivos: %s",dict(motivos))
    return escolhidos,estado
# =========================
# COLETA PRINCIPAL
# =========================
def get_shopee_offers():
    global usados_no_ciclo,BASES_VISTAS
    usados_no_ciclo,BASES_VISTAS=set(),set()
    candidatos,estado=[],carregar_estado()
    ordem,cotas=["Moto","Casa","Maternidade","Eletroeletrônicos","Moda feminina","Moda masculina"],{"Moto":2,"Casa":2,"Maternidade":2,"Eletroeletrônicos":2,"Moda feminina":1,"Moda masculina":1}
    for nicho in ordem:
        try:
            for _ in range(cotas[nicho]):
                if nicho=="Moto":
                    peca,motos,estado=get_combinacao_moto_dia(estado)
                    for moto in motos:
                        escolhidos,estado=selecionar_ofertas_termo(nicho,moto,1,estado,True,peca)
                        candidatos.extend((nicho,p)for p in escolhidos)
                else:
                    termo,estado=get_proximo_termo(nicho,estado)
                    escolhidos,estado=selecionar_ofertas_termo(nicho,termo,1,estado)
                    candidatos.extend((nicho,p)for p in escolhidos)
        except Exception as e:logging.error("Erro nicho %s: %s",nicho,e,exc_info=True)
    salvar_estado(estado)
    candidatos.sort(key=lambda x:oferta_score(x[1]),reverse=True)
    logging.info("Total ofertas: %s",len(candidatos))
    return candidatos[:MAX_OFERTAS]
# =========================
# COPY / MENSAGENS
# =========================
CHAMADAS=["👇 CORRE QUE TÁ ACABANDO!","⚡ CLIQUE ANTES QUE AUMENTE!","🚀 ESTOQUE LIMITADO - AGORA!","💥 MELHOR PREÇO DO ANO!","🎯 COMPRE ANTES DOS OUTROS!","🔥 VOOU DAS PRATELEIRAS!","⏰ PROMOÇÃO ACABA HOJE!","💰 ECONOMIA REAL - CORRE!","⭐ OFERTA QUENTE AGORA!","🛒 NÃO DEIXA ESCAPAR!"]
ABERTURAS=["🚨 Isso aqui não é comum aparecer assim","👀 Achei isso aqui e fui conferir…","🔥 Isso aqui tá com cara de oportunidade","💥 Esse aqui tá chamando atenção de quem compra","🛑 Para tudo e olha isso aqui","🤯 Sério… olha esse achado","⚠️ Isso aqui pode desaparecer rápido","👁️ Pouca gente viu isso ainda","📉 Esse preço aqui não costuma durar","🚀 Esse aqui tá começando a rodar forte"]
GATILHOS=["Preço muito abaixo do que costuma aparecer","Avaliações acima da média","Volume de vendas alto","Simples e funcional","Custo-benefício forte","Quem compra recomenda","Produto direto ao ponto","Tá vendendo bem","Boa margem pra afiliado","Resolve de verdade"]
def aplicar_id_afiliado(link):
    try:p=urlparse(link);q=parse_qs(p.query);q["af_siteid"]=AFILIADO_ID;return urlunparse(p._replace(query=urlencode(q,doseq=True)))
    except:return link
def gerar_link_whatsapp(msg):return f"https://wa.me/?text={quote(re.sub(r'<[^>]+>','',msg))}"
def gerar_copy(nome,preco,vendas,avaliacao,comissao,link,for_whatsapp=False):
    abertura=random.choice([x for x in ABERTURAS if x not in usadas_abertura] or ABERTURAS)
    gatilho=random.choice([x for x in GATILHOS if x not in usadas_gatilho] or GATILHOS)
    acao=random.choice(CHAMADAS);usadas_abertura.add(abertura);usadas_gatilho.add(gatilho)
    grupo=f"📢 Quer mais ofertas assim? Entre no nosso grupo: {LINK_GRUPO_OFERTAS}"
    if for_whatsapp:return f"{abertura}\n\n🔥 {nome}\n\n{gatilho}\n\n{acao}\n\n💰 R$ {preco}\n⭐ {avaliacao} | 🛒 {vendas} vendas\n\n⚠️ Pode subir de preço\n\n🛒 COMPRAR AGORA: {link}\n{grupo}"
    return f"{html.escape(abertura)}\n\n🔥 <b>{html.escape(nome)}</b>\n\n{html.escape(gatilho)}\n\n{html.escape(acao)}\n\n💰 <b>R$ {html.escape(str(preco))}</b>\n⭐ <b>{html.escape(str(avaliacao))} | {html.escape(str(vendas))} vendas</b>\n💸 Comissão: <b>{html.escape(str(comissao))}%</b>\n\n⚠️ Pode subir de preço\n\n<a href=\"{html.escape(link,quote=True)}\">🛒 COMPRAR AGORA</a>\n<a href=\"{html.escape(LINK_GRUPO_OFERTAS,quote=True)}\">📲 Entrar no grupo de ofertas</a>"
# =========================
# ENVIO TELEGRAM
# =========================
async def enviar_produto(context,item,chat_id):
    try:await context.bot.send_photo(chat_id=chat_id,photo=item["img"],caption=item["msg"],parse_mode="HTML");return True
    except Exception as e:logging.warning("Foto falhou: %s",e)
    try:await context.bot.send_message(chat_id=chat_id,text=item["msg"],parse_mode="HTML",disable_web_page_preview=False);return True
    except Exception as e2:logging.error("Falha envio: %s",e2);return False
async def enviar_lote(context,selecionadas):
    await context.bot.send_message(chat_id=CHAT_ID_DESTINO,text="🚨 <b>OFERTAS NOVAS CHEGANDO...</b>",parse_mode="HTML")
    await asyncio.sleep(5)
    for item in selecionadas:
        logging.info("Enviando VIP | nicho=%s",item["nicho_origem"])
        if await enviar_produto(context,item,CHAT_ID_DESTINO):registrar_historico(item["produto_id"])
        await asyncio.sleep(40)
# =========================
# CICLO PRINCIPAL
# =========================
async def send_ofertas(context):
    try:
        logging.info("========== INÍCIO DO CICLO ==========")
        if not dentro_do_horario():logging.info("Fora do horário 05:30–21:30");return
        usadas_abertura.clear();usadas_gatilho.clear()
        shopee_ofertas=get_shopee_offers()
        if len(shopee_ofertas)<MIN_OFERTAS:logging.warning("Só %s ofertas. Mínimo %s. Não enviando.",len(shopee_ofertas),MIN_OFERTAS);return
        selecionadas=[]
        for nicho,item in shopee_ofertas[:MAX_OFERTAS]:
            try:
                nome=str(item.get("productName","")).strip()
                link_base=str(item.get("offerLink")or item.get("productLink")or "").strip()
                if not nome or not link_base:continue
                link=aplicar_id_afiliado(link_base)
                preco=float(item.get("priceMin",0)or 0);vendas=int(item.get("sales",0)or 0)
                rating=float(item.get("ratingStar",4.5)or 4.5);comissao=round(float(item.get("commissionRate",0)or 0)*100,2)
                imagem=str(item.get("imageUrl")or "").strip()
                preco_f=f"{preco:.2f}".replace(".",",");vendas_f=f"{vendas:,}".replace(",",".");rating_f=f"{rating:.1f}"
                msg=gerar_copy(nome,preco_f,vendas_f,rating_f,comissao,link)
                zap_msg=gerar_copy(nome,preco_f,vendas_f,rating_f,0,link,True)
                zap=gerar_link_whatsapp(zap_msg)
                msg+=f'\n📲 <a href="{html.escape(zap,quote=True)}">Compartilhar no WhatsApp</a>\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>'
                produto_id=hashlib.md5(f"{nome}|{link_base}".encode()).hexdigest()
                selecionadas.append({"msg":msg,"img":imagem,"produto_id":produto_id,"item_raw":item,"nicho_origem":nicho})
            except Exception as e:logging.error("Erro produto: %s",e,exc_info=True)
        if len(selecionadas)<MIN_OFERTAS:logging.warning("Só %s ofertas válidas após preparação.",len(selecionadas));return
        await enviar_lote(context,selecionadas)
        # BLOCO FREE — 1 produto em outro grupo
        logging.info("========== BLOCO FREE ==========")
        estado=carregar_estado();idx=int(estado.get("free_nicho_idx",0)or 0)
        nicho_alvo=NICHOS_FREE_ROTA[idx%len(NICHOS_FREE_ROTA)]
        logging.info("Rodízio FREE -> %s",nicho_alvo)
        oferta_free=next((x for x in selecionadas if x["nicho_origem"]==nicho_alvo),None)
        if oferta_free:
            if await enviar_produto(context,oferta_free,FREE_CHAT_ID):registrar_historico(oferta_free["produto_id"])
        else:logging.warning("Sem oferta do nicho %s neste ciclo.",nicho_alvo)
        estado["free_nicho_idx"]=(idx+1)%len(NICHOS_FREE_ROTA);salvar_estado(estado)
        logging.info("========== CICLO FINALIZADO ==========")
    except Exception as e:logging.error("ERRO CICLO: %s",e,exc_info=True)
# =========================
# LOOP AUTOMÁTICO
# =========================
async def ofertas_loop(app):
    logging.info("Loop automático iniciado.");await asyncio.sleep(10)
    while True:
        try:await send_ofertas(type("Contexto",(),{"bot":app.bot})())
        except Exception as e:logging.error("Erro loop: %s",e,exc_info=True)
        logging.info("Próximo ciclo em %ss",CHECK_INTERVAL);await asyncio.sleep(CHECK_INTERVAL)
async def keep_alive():
    while True:logging.info("BOT VIVO | %s",datetime.now(FUSO_BR).strftime("%d/%m/%Y %H:%M"));await asyncio.sleep(300)
# =========================
# INICIALIZAÇÃO
# =========================
async def post_init(app):
    app.bot_data["ofertas_task"]=asyncio.create_task(ofertas_loop(app))
    app.bot_data["keepalive_task"]=asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTÁVEL")
async def post_shutdown(app):
    for t in ["ofertas_task","keepalive_task"]:
        task=app.bot_data.get(t);task and task.cancel()
    await asyncio.gather(*[x for x in [app.bot_data.get(t)for t in["ofertas_task","keepalive_task"]]if x],return_exceptions=True)
async def error_handler(update,context):logging.error("ERRO: %s",context.error,exc_info=True)
def validar_config():
    faltam=[x for x in["TELEGRAM_TOKEN","SHOPEE_PASSWORD","SHOPEE_APP_ID"]if not globals().get(x,"")]
    if faltam:raise RuntimeError("Variáveis ausentes: "+", ".join(faltam))
def iniciar():
    validar_config()
    logging.info("="*40);logging.info("SHOPEE BOT V24-ROTACAO");logging.info("Horário: 05:30–21:30 | Intervalo: 1h30");logging.info("="*40)
    while True:
        try:
            app=ApplicationBuilder().token(TELEGRAM_TOKEN).post_init(post_init).post_shutdown(post_shutdown).build()
            app.add_error_handler(error_handler);app.run_polling(drop_pending_updates=True)
        except Exception as e:logging.error("Reiniciando em 15s: %s",e);time.sleep(15)
if __name__=="__main__":iniciar()




