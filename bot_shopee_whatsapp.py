import asyncio, requests, logging, random, hashlib, time, json, os, html, re, tempfile
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder
print("VERSAO V33-CORRIGIDO+GARANTIA-OFERTAS")
=========================
CONFIG
=========================
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "").strip()
SHOPEE_APP_ID = "18349740277"
CHAT_ID_DESTINO=-1003848415150
FREE_CHAT_ID=-1003886228244
AFILIADO_ID = "18349740277"
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"
CHECK_INTERVAL = 5400
MAX_OFERTAS = 10 # Quantidade no VIP
MIN_OFERTAS = 10 # AGORA EXIGE 10, NÃO ENVIA SE NÃO TIVER
OFERTA_FREE = 1 # Quantidade para o Free
HISTORICO_DIAS = 30
SIMILARIDADE_MAX = .85 # Mais rígido contra repetições
VENDAS_MIN = 1 # Exigir pelo menos 1 venda
AVALIACAO_MIN = 3.5 # Exigir nota mínima
PRECO_MIN = 5 # Abaixado pra não cortar tudo
PRECO_MAX = 10000
COMISSAO_MIN = 3
VERSAO_RODIZIO = 34
LIMITE_POR_FAMILIA = 1
MAX_PAGINA_BUSCA = 4
TIPOS_ORDEM = [1, 2, 3, 4, 5]
FUSO_BR = ZoneInfo("America/Sao_Paulo")
ARQUIVO_ESTADO = "estado_buscas.json"
ARQUIVO_HISTORICO = "historico_envios.json"
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
ULTIMOS_LINKS = []
ULTIMOS_TITULOS = []
ABERTURAS_USADAS = set()
GATILHOS_USADOS = set()
LINKS_CICLO_ATUAL = set()
TERMOS_USADOS_CICLO = set()
=========================
FUNÇÕES BÁSICAS
=========================
def normalizar(texto):
return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9à-ÿ\s]", " ", str(texto or "").lower().strip()))
def horario_valido():
agora = datetime.now(FUSO_BR).time()
return dt_time(5, 30) <= agora <= dt_time(21, 30)
def variar_termo(termo):
base = termo.strip()
REMOVI "barato" pra não zerar buscas
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
=========================
LISTAS DE PRODUTOS
=========================
MOTOS = ["titan 150", "cb 300", "factor 150", "titan 160", "tornado 250", "fazer 150", "bros 160", "twister 250", "biz 125", "pop 110", "xre 300", "crosser 150", "xre 190", "fazer 250", "lander 250"]
PECAS_MOTO = ["kit relacao", "embreagem", "bateria", "filtro oleo", "cabo embreagem", "cabo freio", "vela ignicao", "pneu", "disco freio", "pastilha freio"]
PRODUTOS_POR_NICHO = {
"Casa": ["fritadeira sem oleo", "aspirador", "liquidificador", "cafeteira", "panela eletrica", "ventilador", "batedeira", "lampada led"],
"Bebê": ["carrinho bebe", "berco", "brinquedo bebe", "roupa bebe", "cadeirinha bebe"],
"Eletrônicos": ["smartwatch", "fone ouvido bluetooth", "caixa som bluetooth", "carregador", "cabo usb", "pendrive", "mouse", "teclado"],
"Moda Feminina": ["vestido", "blusa", "calca", "saia", "tenis feminino", "bolsa", "oculos sol"],
"Moda Masculina": ["camiseta", "bermuda", "calca jeans", "tenis masculino", "bone", "cinto"]
}
FAMILIAS_PRODUTOS = {
"fritadeira": ["fritadeira", "air fryer"],
"smartwatch": ["smartwatch", "relogio inteligente"],
"fone": ["fone", "ouvido", "bluetooth"],
"tv": ["tv", "televisao"],
"bebe": ["bebe", "infantil", "crianca"],
"moda_fem": ["vestido", "blusa", "saia", "mulher", "feminina"],
"moda_masc": ["camiseta", "bermuda", "masculino", "homem"],
"casa": ["panela", "utensilio", "cozinha"],
"moto": ["kit relacao", "embreagem", "bateria moto", "filtro oleo",
"cabo embreagem", "cabo freio", "vela ignicao", "pneu moto",
"disco freio", "pastilha freio", "titan", "cb 300", "honda"]
}
=========================
ARQUIVOS DE ESTADO
=========================
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
estado = {"versao_rodizio": VERSAO_RODIZIO, "Moto": {"data": hoje, "indice": 0}}
for nicho in PRODUTOS_POR_NICHO:
estado[nicho] = {"indice": 0, "data": hoje}
return estado
def salvar_estado(estado): salvar_json(ARQUIVO_ESTADO, estado)
def carregar_historico(): return carregar_json(ARQUIVO_HISTORICO, {})
def salvar_historico(dados): salvar_json(ARQUIVO_HISTORICO, dados)
=========================
ROTAÇÃO
=========================
def proxima_busca_moto(estado):
i = estado["Moto"]["indice"]
peca = PECAS_MOTO[i % len(PECAS_MOTO)]
moto = MOTOS[i % len(MOTOS)]
estado["Moto"]["indice"] = (i + 1) % (len(PECAS_MOTO) * len(MOTOS))
logging.info("🏍️ Peça: [%s] | Moto: [%s]", peca, moto)
return peca, moto, estado
def proximo_termo(nicho, estado):
itens = PRODUTOS_POR_NICHO[nicho]
c = estado[nicho]
for _ in range(len(itens)):
t = itens[c["indice"] % len(itens)]
c["indice"] += 1
if termo_ja_usado(t):
logging.info("🛑 Pulado: %s", t)
continue
TERMOS_USADOS_CICLO.add(t)
return t, estado
return itens[c["indice"] % len(itens)], estado
=========================
FILTROS
=========================
def chave_titulo(titulo):
ign = {"premium","novo","promocao","promoção","super","original","kit","completo"}
return " ".join(sorted([p for p in normalizar(titulo).split() if p not in ign and len(p) > 2])[:8])
def tem_bloqueio(texto):
return any(p in normalizar(texto) for p in ["teste","amostra","nao venda","exposicao"])
def duplicata_forte(titulo):
ch = chave_titulo(titulo); nt = normalizar(titulo)
return any(ch == chave_titulo(t) or SequenceMatcher(None, nt, normalizar(t)).ratio() >= SIMILARIDADE_MAX for t in ULTIMOS_TITULOS)
def enviado_anteriormente(chave):
h = carregar_historico()
if chave in h:
try: return (datetime.now(FUSO_BR) - datetime.fromisoformat(h[chave]).replace(tzinfo=FUSO_BR)) < timedelta(days=HISTORICO_DIAS)
except: pass
return False
def registrar_envio(chave):
h = carregar_historico()
h[chave] = datetime.now(FUSO_BR).isoformat()
lim = datetime.now(FUSO_BR) - timedelta(days=HISTORICO_DIAS3)
salvar_historico({k:v for k,v in h.items() if datetime.fromisoformat(v).replace(tzinfo=FUSO_BR) >= lim})
def identificar_familia(titulo):
nt = normalizar(titulo)
for f, ps in FAMILIAS_PRODUTOS.items():
if any(normalizar(p) in nt for p in ps): return f
return "outros"
def pontuar_produto(p, termo=""):
try:
vendas = int(p.get("sales", 0) or 0)
nota = float(p.get("ratingStar", 0) or 0)
comissao = float(p.get("commissionRate", 0) or 0) * 100
preco_str = p.get("priceMin", "0") or "0"
preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
pt = normalizar(termo); tp = normalizar(p.get("productName",""))
pont = min(vendas/5,30) + nota3 + comissao*2
if 50 <= preco <= 500: pont +=8
if pt: pont += 10 if pt in tp else sum(2 for x in pt.split() if x in tp)
return max(0,pont)
except: return 0
def avaliar_rejeicao(p):
titulo = str(p.get("productName","")).strip()
link = str(p.get("offerLink") or p.get("productLink","")).strip()
try:
preco_str = p.get("priceMin", "0") or "0"
preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
except: preco = 0
try: comissao = float(p.get("commissionRate", "0") or 0) * 100
except: comissao = 0
vendas = int(p.get("sales", 0) or 0)
nota = float(p.get("ratingStar", 0) or 0)
if not titulo: return "sem_titulo"
if not link: return "sem_link"
if tem_bloqueio(titulo): return "bloqueado"
if preco < PRECO_MIN: return "preco_baixo"
if preco > PRECO_MAX: return "preco_alto"
if comissao < COMISSAO_MIN: return "comissao_baixa"
if vendas > 0 and vendas < VENDAS_MIN: return "poucas_vendas"
if nota > 0 and nota < AVALIACAO_MIN: return "nota_baixa"
if link in LINKS_CICLO_ATUAL or link in ULTIMOS_LINKS: return "link_repetido"
return None
=========================
BUSCA API
=========================
def buscar_produtos(termo, nicho):
logging.info("🔍 Buscando em %s: %s", nicho, termo)
ts = int(time.time())
ordem = random.choice(TIPOS_ORDEM)
pagina = random.randint(1, MAX_PAGINA_BUSCA)
termo_busca = variar_termo(termo)
logging.info(" ↳ Ordem=%s | Página=%s | Buscando: %s", ordem, pagina, termo_busca)
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
=========================
SELECIONAR
=========================
def selecionar(nicho, termo, qtd, estado, moto=False, peca=None):
tcompleto = f"{peca} {termo}" if moto else termo
res = buscar_produtos(tcompleto, nicho)
val = []; motivos = Counter()
for p in res:
m = avaliar_rejeicao(p)
if m: motivos[m]+=1
else: val.append(p)
logging.info("📊 %s: %s brutos / %s válidos", nicho, len(res), len(val))
if val:
com_pont = [(p, pontuar_produto(p, termo)) for p in val]
pesos = [max(1,n**1.5) for _,n in com_pont]
idx = random.choices(range(len(com_pont)), weights=pesos, k=len(com_pont))
val = [com_pont[i][0] for i in idx]
esc = []; tusados = []; familias=Counter()
for p in val:
if len(esc)>=qtd: break
titulo = str(p.get("productName","")).strip()
link = str(p.get("offerLink") or p.get("productLink","")).strip()
ch = chave_titulo(titulo)
fam = identificar_familia(titulo)
hid = hashlib.md5(f"{ch}|{link}".encode()).hexdigest()
if duplicata_forte(titulo): continue
if familias[fam]>=LIMITE_POR_FAMILIA: continue
if enviado_anteriormente(hid): continue
esc.append(p); tusados.append(titulo); familias[fam]+=1
LINKS_CICLO_ATUAL.add(link); ULTIMOS_LINKS.append(link); ULTIMOS_TITULOS.append(titulo)
registrar_envio(hid)
logging.info("🏆 Selecionado: %s | %s", titulo[:50], fam)
del ULTIMOS_LINKS[:-300]; del ULTIMOS_TITULOS[:-150]
if motivos: logging.info("📋 Excluídos: %s", dict(motivos))
return esc, estado
=========================
BUSCA INTELIGENTE - GARANTIR 10 OFERTAS
=========================
def obter_ofertas_garantidas(estado):
global LINKS_CICLO_ATUAL, TERMOS_USADOS_CICLO
LINKS_CICLO_ATUAL.clear(); TERMOS_USADOS_CICLO.clear()
sel = []
lista_nichos = list(PRODUTOS_POR_NICHO.items())
1. Busca Moto
peca, moto, estado = proxima_busca_moto(estado)
its, estado = selecionar("Moto", moto, 1, estado, True, peca)
sel.extend([("Moto", x) for x in its])
2. Busca nos nichos ATÉ COMPLETAR 10
tentativas = 0
max_tentativas = 50 # Segurança
while len(sel) < MIN_OFERTAS and tentativas < max_tentativas:
tentativas += 1
for nicho, _ in lista_nichos:
if len(sel) >= MIN_OFERTAS:
break
t, estado = proximo_termo(nicho, estado)
its, estado = selecionar(nicho, t, 1, estado)
sel.extend([(nicho, x) for x in its])
if len(sel) >= MIN_OFERTAS:
break
salvar_estado(estado)
Ordenar por qualidade (melhores primeiro)
sel.sort(key=lambda x: pontuar_produto(x[1], x[0]), reverse=True)
Garantir exatamente 10
if len(sel) >= MIN_OFERTAS:
sel = sel[:MAX_OFERTAS]
logging.info("✅ ✅ GARANTIDO: %s ofertas selecionadas", len(sel))
return sel
else:
logging.warning("⚠️ Atingiu limite de tentativas com %s ofertas", len(sel))
return sel
=========================
LISTA OFERTAS
=========================
def obter_ofertas_shopee():
return obter_ofertas_garantidas(carregar_estado())
=========================
MENSAGENS
=========================
ABERTURAS = ["🚨 Isso não aparece todo dia!","👀 Olha o que encontrei…","🔥 Aproveita enquanto dá!","🛑 Para e olha!","🤯 Difícil achar barato assim!","⚠️ Pode sumir a qualquer hora…","📉 Caiu de preço!","🚀 Tá bombando!"]
GATILHOS = ["Bem abaixo do preço normal","Avaliações excelentes","Muita gente comprando","Custo-benefício ótimo","Quem compra recomenda","Produto confiável","Saindo rápido"]
CHAMADAS = ["👇 Corre antes que acabe!","⚡ Clique antes de aumentar!","🚀 Estoque limitado!","💥 Oportunidade!","🎯 Compre antes dos outros!","⏰ Acaba hoje!","💰 Economia real!","🛒 Não perca!"]
def anexar_afiliado(link):
try: u=urlparse(link); p=parse_qs(u.query); p["af_siteid"]=AFILIADO_ID; return urlunparse(u._replace(query=urlencode(p,doseq=True)))
except: return link
def link_whatsai(texto): return f"https://wa.me/?text={quote(re.sub(r'<[^>]+>','',texto))}"
def mensagem_whatsai(nome, preco, vendas, nota, comissao, link):
return (
f"🔥 Produto: {nome}\n\n"
f"💰 Preço: R$ {preco}\n"
f"📊 Vendas: {vendas}\n"
f"⭐ Avaliação: {nota}\n"
f"💼 Comissão: {comissao}%\n\n"
f"🛒 Aproveite pelo link:\n{link}"
)
def montar_tg(nome, preco, vendas, nota, comissao, link, lk_whats, free=False):
Escolhe abertura: se todas usadas, reinicia
disponiveis_ab = [x for x in ABERTURAS if x not in ABERTURAS_USADAS]
if not disponiveis_ab:
ABERTURAS_USADAS.clear()
disponiveis_ab = ABERTURAS
ab = random.choice(disponiveis_ab)
ABERTURAS_USADAS.add(ab)
Escolhe gatilho: se todos usados, reinicia
disponiveis_gt = [x for x in GATILHOS if x not in GATILHOS_USADOS]
if not disponiveis_gt:
GATILHOS_USADOS.clear()
disponiveis_gt = GATILHOS
gt = random.choice(disponiveis_gt)
GATILHOS_USADOS.add(gt)
ch = random.choice(CHAMADAS)
etiqueta = "🎁 OFERTA DESTAQUE" if free else ""
return (
f"{etiqueta}\n\n" if etiqueta else ""
f"{html.escape(ab)}\n\n"
f"🔥 <b>Produto:</b> {html.escape(nome)}\n\n"
f"💰 <b>Preço:</b> R$ {preco}\n"
f"📊 <b>Vendas:</b> {vendas}\n"
f"⭐ <b>Avaliação:</b> {nota}\n"
f"💼 <b>Comissão:</b> {comissao}%\n\n"
f"{html.escape(gt)}\n\n"
f"{html.escape(ch)}\n\n"
f'🛒 COMPRAR AGORA\n'
f'📲 Compartilhar WhatsApp\n'
f'👥 Grupo de ofertas'
)
=========================
ENVIO
=========================
async def enviar_msg(ctx, txt, img, cid):
try: await ctx.bot.send_photo(cid, photo=img, caption=txt, parse_mode="HTML"); return True
except Exception as e: logging.warning("⚠️ Foto: %s", e)
try: await ctx.bot.send_message(cid, text=txt, parse_mode="HTML"); return True
except Exception as e: logging.error("❌ Erro envio: %s", e); return False
async def ciclo(ctx):
try:
logging.info("========== 🔄 INÍCIO ==========")
if not horario_valido(): logging.info("⏹️ Fora do horário"); return
ABERTURAS_USADAS.clear(); GATILHOS_USADOS.clear()
ofertas = obter_ofertas_shopee()
GARANTIR 10 OFERTAS - se não tiver, tenta novamente depois
if len(ofertas) < MIN_OFERTAS:
logging.warning("⚠️ Apenas %s ofertas válidas. Mínimo de %s exigido. Ciclo pulado.", len(ofertas), MIN_OFERTAS)
return
logging.info("✅ Total: %s | Enviando: %s/%s", len(ofertas), len(ofertas), MAX_OFERTAS)
SEPARAR: 1 para Free, 9 para VIP (ou 10 VIP se preferir)
idx_free = random.randint(0, len(ofertas)-1)
oferta_free = ofertas.pop(idx_free) # Remove das VIP
ofertas_vip = ofertas # 9 restantes
await ctx.bot.send_message(CHAT_ID_DESTINO, text="🚨 <b>OFERTAS NOVAS CHEGARAM!</b>", parse_mode="HTML")
await asyncio.sleep(5)
ENVIAR VIP (9 melhores)
enviados=[]
for nicho, p in ofertas_vip:
try:
titulo = str(p.get("productName","")).strip()
lb = str(p.get("offerLink") or p.get("productLink","")).strip()
if not titulo or not lb: continue
link = anexar_afiliado(lb)
try:
preco_str = p.get("priceMin", "0") or "0"
preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
except: preco = 0
vendas = int(p.get("sales", 0) or 0)
nota = float(p.get("ratingStar", 0) or 0)
comissao = round(float(p.get("commissionRate", 0) or 0) * 100, 2)
img = str(p.get("imageUrl","")).strip()
prc = f"{preco:.2f}".replace(".",",")
vnd = f"{vendas:,}".replace(",",".")
nt = f"{nota:.1f}".replace(".",",")
txt_whats = mensagem_whatsai(titulo,prc,vnd,nt,comissao,link)
lk_whats = link_whatsai(txt_whats)
txt_tg = montar_tg(titulo,prc,vnd,nt,comissao,link,lk_whats, free=False)
hid = hashlib.md5(f"{chave_titulo(titulo)}|{lb}".encode()).hexdigest()
enviados.append({"txt":txt_tg,"img":img,"hid":hid,"nicho":nicho})
except Exception as e: logging.error("❌ Montagem: %s", e)
if len(enviados) < MIN_OFERTAS - OFERTA_FREE: return
for item in enviados:
logging.info("📤 Enviando VIP: %s", item["nicho"])
ok = await enviar_msg(ctx, item["txt"], item["img"], CHAT_ID_DESTINO)
if ok: registrar_envio(item["hid"])
await asyncio.sleep(40)
ENVIAR OFERTA FREE
logging.info("🎁 Enviando oferta destaque para grupo FREE")
nicho_free, p_free = oferta_free
try:
titulo = str(p_free.get("productName","")).strip()
lb = str(p_free.get("offerLink") or p_free.get("productLink","")).strip()
link = anexar_afiliado(lb)
try:
preco_str = p_free.get("priceMin", "0") or "0"
preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
except: preco = 0
vendas = int(p_free.get("sales", 0) or 0)
nota = float(p_free.get("ratingStar", 0) or 0)
comissao = round(float(p_free.get("commissionRate", 0) or 0) * 100, 2)
img = str(p_free.get("imageUrl","")).strip()
prc = f"{preco:.2f}".replace(".",",")
vnd = f"{vendas:,}".replace(",",".")
nt = f"{nota:.1f}".replace(".",",")
txt_whats = mensagem_whatsai(titulo,prc,vnd,nt,comissao,link)
lk_whats = link_whatsai(txt_whats)
txt_tg = montar_tg(titulo,prc,vnd,nt,comissao,link,lk_whats, free=True)
hid = hashlib.md5(f"{chave_titulo(titulo)}|{lb}".encode()).hexdigest()
Enviar para grupo FREE
await ctx.bot.send_message(CHAT_ID_FREE, text="🎁 <b>OFERTA DESTAQUE DA SEMANA!</b>", parse_mode="HTML")
await asyncio.sleep(3)
ok = await enviar_msg(ctx, txt_tg, img, CHAT_ID_FREE)
if ok: registrar_envio(hid)
logging.info("✅ Oferta FREE enviada!")
except Exception as e: logging.error("❌ Erro envio FREE: %s", e)
logging.info("========== ✅ CONCLUÍDO ==========")
except Exception as e: logging.error("❌ ERRO: %s", e, exc_info=True)
async def loop(app):
ult=0
while True:
agora=time.time()
if agora-ult>=CHECK_INTERVAL:
await ciclo(type("Ctx",(),{"bot":app.bot})())
ult=agora
await asyncio.sleep(60)
async def manter_vivo():
while True: logging.info("💓 Ativo | %s", datetime.now(FUSO_BR).strftime("%d/%m às %H:%M")); await asyncio.sleep(300)
async def principal():
if not TELEGRAM_TOKEN or not SHOPEE_PASSWORD: raise RuntimeError("Configure TELEGRAM_TOKEN e SHOPEE_PASSWORD")
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
logging.info("🤖 Bot pronto!")
asyncio.create_task(manter_vivo())
await loop(app)
def iniciar():
try: asyncio.run(principal())
except Exception as e: logging.error("🔄 Reiniciando em 15s: %s", e); time.sleep(15); iniciar()
if name == "main": iniciar()
