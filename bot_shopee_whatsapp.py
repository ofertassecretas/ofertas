# PRIMEIRO — TODOS OS IMPORTS
import os
import asyncio, requests, logging, random, hashlib, time, json, html, re, tempfile, secrets
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
# AGORA SIM — DEPOIS DOS IMPORTS, roda o diagnóstico
print("=" * 50)
print("🔍 VERIFICANDO VARIÁVEIS DE AMBIENTE...")
print(f"URL_DO_BANCO_DE_DADOS configurada = {bool(os.getenv('URL_DO_BANCO_DE_DADOS'))}")
print(f"DATABASE_URL configurada = {bool(os.getenv('DATABASE_URL'))}")
print("=" * 50)
print("VERSAO V58-VENCIMENTO-AUTOMATICO")
try:
    import psycopg2
    from psycopg2.extras import Json
    print("✅ psycopg2 carregado com sucesso")
except Exception as e:
    print(f"⚠️ Erro ao carregar psycopg2: {type(e).__name__}: {e}")
    psycopg2 = None
    Json = None
# =========================
# CONFIG — CORRIGIDO
# =========================
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "").strip()
SHOPEE_APP_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
CHAT_ID_FREE = -1003886228244
AFILIADO_ID = "18349740277"
CAKTO_BOT_USERNAME = (os.getenv("CAKTO_BOT_USERNAME") or "CaktoBot").strip().lstrip("@")

# ✅ LINKS DE PAGAMENTO — FIXOS
LINKS_PLANOS = {
    "semanal": "https://pay.cakto.com.br/8kimcbi_1156536",
    "mensal": "https://pay.cakto.com.br/rzwuzen_1156485",
    "anual": "https://pay.cakto.com.br/tikburq_1156549"
}

DURACAO_PLANOS = {
    "semanal": 7,
    "mensal": 30,
    "anual": 365
}

# ✅ Leitura ajustada — PRIORIZA URL_DO_BANCO_DE_DADOS (Railway)
_raw_db_url = os.getenv("URL_DO_BANCO_DE_DADOS") or os.getenv("DATABASE_URL")
if _raw_db_url:
    # Corrige o esquema: postgresql:// → postgres://
    DATABASE_URL = _raw_db_url.replace("postgresql://", "postgres://")
    print(f"✅ URL do banco encontrada e pronta!")
    print("🔗 Endereço do banco carregado (credenciais ocultas).")
else:
    DATABASE_URL = None
    print("⚠️ Nenhuma variável de banco encontrada!")
PLANOS_CAKTO_PRODUTOS = {
    "3092f5b9-4520-4def-8ca7-9bd3401890a5": "semanal",
    "2005e842-e78e-4093-a244-18ab2a180647": "mensal",
    "f13e47fe-2e9e-474a-83b6-d8e7dd73160d": "anual",
}
LINK_GRUPO_OFERTAS = "https://chat.whatsapp.com/GTXOS0u7rZEIEBhLGQG9VM"
SHOPEE_GRAPHQL_URL = "https://open-api.affiliate.shopee.com.br/graphql"
CHECK_INTERVAL = 5400
MAX_OFERTAS = 10
MIN_OFERTAS = 10
OFERTA_FREE = 1
HISTORICO_DIAS = 30
SIMILARIDADE_MAX = .85
VENDAS_MIN = 1
AVALIACAO_MIN = 3.5
PRECO_MIN = 5
PRECO_MAX = 10000
COMISSAO_MIN = 3
VERSAO_RODIZIO = 43
LIMITE_POR_FAMILIA = 1
MAX_PAGINA_BUSCA = 4
TIPOS_ORDEM = [1, 2, 3, 4, 5]
FUSO_BR = ZoneInfo("America/Sao_Paulo")
ARQUIVO_ESTADO = "estado_buscas.json"
ARQUIVO_HISTORICO = "historico_envios.json"
AVISOS_ENVIADOS = {}  # Controla avisos de vencimento para não repetir
# 🚫 PALAVRAS PROIBIDAS
PALAVRAS_PROIBIDAS = [
    "mousepad", "mouse pad", "tapete de mouse", "almofada de mouse",
    "mouse", "pad mouse", "pad para mouse"
]
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
# =========================
# 🤖 ONBOARDING / CLIENTES
# =========================
CLIENTES_TELEGRAM = "clientes_telegram.json"
CLIENTES_CAKTO = "clientes_cakto.json"
DB_PRONTA = False
DB_AVISO_EMITIDO = False

def calcular_data_fim(plano, data_inicio=None):
    """Calcula quando o plano vence"""
    if not data_inicio:
        data_inicio = datetime.now(FUSO_BR)
    dias = DURACAO_PLANOS.get(plano, 7)
    return data_inicio + timedelta(dias=dias)

def verificar_status_cliente(cliente):
    """Verifica se o cliente está ativo, quantos dias faltam e se deve avisar"""
    if not cliente.get("ativo"):
        return False, -1, "inativo"
    
    data_fim_str = cliente.get("data_fim_plano")
    if not data_fim_str:
        # Se não tem data de fim, calcula a partir do início
        data_inicio_str = cliente.get("inicio_plano")
        if not data_inicio_str:
            return True, 999, "sem_data"
        try:
            data_inicio = datetime.fromisoformat(data_inicio_str)
            data_fim = calcular_data_fim(cliente.get("plano", "semanal"), data_inicio)
        except:
            return True, 999, "data_invalida"
    else:
        try:
            data_fim = datetime.fromisoformat(data_fim_str)
        except:
            return True, 999, "data_invalida"
    
    agora = datetime.now(FUSO_BR)
    dias_restantes = (data_fim - agora).days
    
    if dias_restantes < 0:
        return False, dias_restantes, "vencido"
    return True, dias_restantes, "ativo"

def mensagem_vencimento(plano, dias_restantes):
    """Gera mensagem de aviso com os 3 links"""
    links_texto = (
        f"💳 Escolha o plano ideal pra você:\n\n"
        f"📅 Semanal (R$ 7,90/semana):\n{LINKS_PLANOS['semanal']}\n\n"
        f"📆 Mensal (mais econômico):\n{LINKS_PLANOS['mensal']}\n\n"
        f"🚀 Anual (melhor valor!):\n{LINKS_PLANOS['anual']}"
    )
    
    if dias_restantes == 3:
        return (
            f"⚠️ <b>SEU PLANO VENCE EM 3 DIAS!</b>\n\n"
            f"Faltam apenas 3 dias para o seu acesso terminar.\n"
            f"Renove agora pra não perder as ofertas!\n\n"
            f"{links_texto}"
        )
    elif dias_restantes == 2:
        return (
            f"⚠️ <b>SEU PLANO VENCE EM 2 DIAS!</b>\n\n"
            f"Faltam só 2 dias! Renove pra continuar recebendo as melhores ofertas.\n\n"
            f"{links_texto}"
        )
    elif dias_restantes == 1:
        return (
            f"🚨 <b>ÚLTIMO DIA DE ACESSO!</b>\n\n"
            f"Hoje é o último dia do seu plano! Após hoje, as ofertas serão pausadas.\n"
            f"Renove agora e não perca nada!\n\n"
            f"{links_texto}"
        )
    elif dias_restantes == 0:
        return (
            f"❌ <b>SEU PLANO VENCEU HOJE!</b>\n\n"
            f"O acesso foi pausado. Renove para voltar a receber ofertas.\n\n"
            f"{links_texto}"
        )
    return None

async def enviar_aviso_vencimento(bot, cliente, dias_restantes):
    """Envia aviso de vencimento uma única vez por período"""
    telegram_id = cliente.get("telegram_id")
    if not telegram_id:
        return False
    
    chave_aviso = f"{telegram_id}_{dias_restantes}"
    if AVISOS_ENVIADOS.get(chave_aviso):
        return False  # Já avisou nesse período
    
    mensagem = mensagem_vencimento(cliente.get("plano", "semanal"), dias_restantes)
    if not mensagem:
        return False
    
    try:
        await bot.send_message(chat_id=telegram_id, text=mensagem, parse_mode="HTML")
        AVISOS_ENVIADOS[chave_aviso] = True
        logging.info(f"📤 Aviso de vencimento enviado | cliente={telegram_id} | dias={dias_restantes}")
        return True
    except Exception as e:
        logging.warning(f"⚠️ Não consegui enviar aviso para {telegram_id}: {e}")
        return False

def _db_conectar():
    if not DATABASE_URL or psycopg2 is None:
        logging.warning("⚠️ Banco indisponível — DATABASE_URL configurada: %s | psycopg2 disponível: %s" % (bool(DATABASE_URL), psycopg2 is not None))
        return None
    try:
        return psycopg2.connect(DATABASE_URL, connect_timeout=10)
    except Exception as e:
        logging.error("❌ Falha na conexão com o banco: %s", e)
        return None

def inicializar_banco_persistente():
    """Cria as tabelas e migra o JSON local apenas se a tabela estiver vazia."""
    global DB_PRONTA, DB_AVISO_EMITIDO
    if not DATABASE_URL:
        logging.warning("⚠️ DATABASE_URL não configurada — clientes continuam no JSON local")
        return
    if psycopg2 is None:
        logging.error("❌ psycopg2 não instalado — configure psycopg2-binary no requirements.txt")
        return
    try:
        with _db_conectar() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS radar_clientes_telegram (
                        chave TEXT PRIMARY KEY,
                        dados JSONB NOT NULL,
                        atualizado_em TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS radar_clientes_cakto (
                        chave TEXT PRIMARY KEY,
                        dados JSONB NOT NULL,
                        atualizado_em TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                cur.execute("SELECT COUNT(*) FROM radar_clientes_telegram")
                vazio_tg = cur.fetchone()[0] == 0
                cur.execute("SELECT COUNT(*) FROM radar_clientes_cakto")
                vazio_ck = cur.fetchone()[0] == 0
                if vazio_tg:
                    locais = carregar_json(CLIENTES_TELEGRAM, {})
                    for chave, dados in locais.items():
                        cur.execute(
                            "INSERT INTO radar_clientes_telegram (chave, dados) VALUES (%s, %s) ON CONFLICT (chave) DO NOTHING",
                            (str(chave), Json(dados))
                        )
                    if locais:
                        logging.info("🗄️ Migração inicial: %s cliente(s) Telegram para o banco", len(locais))
                if vazio_ck:
                    locais = carregar_json(CLIENTES_CAKTO, {})
                    for chave, dados in locais.items():
                        cur.execute(
                            "INSERT INTO radar_clientes_cakto (chave, dados) VALUES (%s, %s) ON CONFLICT (chave) DO NOTHING",
                            (str(chave), Json(dados))
                        )
                    if locais:
                        logging.info("🗄️ Migração inicial: %s registro(s) Cakto para o banco", len(locais))
        DB_PRONTA = True
        logging.info("🗄️ Banco persistente PostgreSQL ativo para clientes")
    except Exception as e:
        logging.error("❌ Falha iniciando banco persistente: %s", e, exc_info=True)
        DB_PRONTA = False

def _db_carregar(tabela):
    try:
        with _db_conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT chave, dados FROM {tabela}")
                return {str(chave): (dados or {}) for chave, dados in cur.fetchall()}
    except Exception as e:
        logging.error("❌ Falha lendo %s: %s", tabela, e)
        return None

def _db_salvar(tabela, dados):
    try:
        with _db_conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DELETE FROM {tabela}")
                for chave, registro in dados.items():
                    cur.execute(
                        f"INSERT INTO {tabela} (chave, dados, atualizado_em) VALUES (%s, %s, NOW())",
                        (str(chave), Json(registro))
                    )
        return True
    except Exception as e:
        logging.error("❌ Falha salvando %s: %s", tabela, e)
        return False

def carregar_clientes_telegram():
    if DB_PRONTA:
        dados = _db_carregar("radar_clientes_telegram")
        if dados is not None:
            return dados
    return carregar_json(CLIENTES_TELEGRAM, {})

def salvar_clientes_telegram(dados):
    if DB_PRONTA and _db_salvar("radar_clientes_telegram", dados):
        return
    salvar_json(CLIENTES_TELEGRAM, dados)

def carregar_clientes_cakto():
    if DB_PRONTA:
        dados = _db_carregar("radar_clientes_cakto")
        if dados is not None:
            return dados
    return carregar_json(CLIENTES_CAKTO, {})

def salvar_clientes_cakto(dados):
    if DB_PRONTA and _db_salvar("radar_clientes_cakto", dados):
        return
    salvar_json(CLIENTES_CAKTO, dados)

def email_normalizado(email):
    return (email or "").strip().lower()

def classificar_plano(oferta="", preco=None, periodo=None):
    texto = (oferta or "").lower()
    if "seman" in texto:
        return "semanal"
    if "anual" in texto:
        return "anual"
    if "mensal" in texto:
        return "mensal"
    try:
        valor = float(preco or 0)
        if abs(valor - 7.90) < 0.02:
            return "semanal"
        if abs(valor - 19.90) < 0.02:
            return "mensal"
        if abs(valor - 199.90) < 0.02:
            return "anual"
    except Exception:
        pass
    try:
        dias = int(periodo or 0)
        if dias == 7:
            return "semanal"
        if 28 <= dias <= 31:
            return "mensal"
        if 360 <= dias <= 370:
            return "anual"
    except Exception:
        pass
    return "desconhecido"

def status_ativo_cakto(evento, status):
    texto = f"{evento or ''} {status or ''}".lower()
    if any(x in texto for x in ["cancel", "refund", "reembolso", "chargeback", "cancelad"]):
        return False
    if any(x in texto for x in ["approved", "aprovad", "paid", "pago", "active", "ativo", "renew", "renov"]):
        return True
    return None

def encontrar_cliente_por_telegram(telegram_id):
    clientes = carregar_clientes_telegram()
    return clientes.get(str(telegram_id), {})

def encontrar_cakto_por_email(email):
    registro = carregar_clientes_cakto().get(email_normalizado(email))
    if not registro:
        return None
    produto_id = str(registro.get("produto_id", ""))
    plano_id = PLANOS_CAKTO_PRODUTOS.get(produto_id)
    if plano_id and registro.get("plano") != plano_id:
        registro["plano"] = plano_id
        dados = carregar_clientes_cakto()
        dados[email_normalizado(email)] = registro
        salvar_clientes_cakto(dados)
    elif registro.get("plano") == "desconhecido":
        plano = classificar_plano(registro.get("oferta", ""), registro.get("oferta_preco"), registro.get("subscription_period"))
        if plano != "desconhecido":
            registro["plano"] = plano
            dados = carregar_clientes_cakto()
            dados[email_normalizado(email)] = registro
            salvar_clientes_cakto(dados)
    return registro

async def comando_start(update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    clientes = carregar_clientes_telegram()
    chave = str(user.id)
    cliente = clientes.get(chave, {})
    cliente.update({
        "telegram_id": user.id,
        "username": user.username or "",
        "nome": user.full_name or "",
        "ultimo_start": datetime.now(FUSO_BR).isoformat()
    })
    clientes[chave] = cliente
    salvar_clientes_telegram(clientes)
    nome = html.escape(user.first_name or "cliente")
    compra = encontrar_cakto_por_email(cliente.get("email_cakto")) if cliente.get("email_cakto") else None
    
    # ✅ Atualiza data de início e fim do plano quando encontra compra ativa
    if compra and compra.get("ativo"):
        plano_atual = compra.get("plano", cliente.get("plano", "desconhecido"))
        precisa_atualizar = False
        if not cliente.get("inicio_plano") or cliente.get("plano") != plano_atual:
            cliente["inicio_plano"] = datetime.now(FUSO_BR).isoformat()
            precisa_atualizar = True
        if not cliente.get("data_fim_plano") or cliente.get("plano") != plano_atual:
            cliente["plano"] = plano_atual
            cliente["data_fim_plano"] = calcular_data_fim(plano_atual).isoformat()
            precisa_atualizar = True
        if precisa_atualizar:
            cliente["ativo"] = True
            clientes[chave] = cliente
            salvar_clientes_telegram(clientes)
            logging.info(f"📅 Datas do plano atualizadas | cliente={chave} | plano={plano_atual}")
    
    if compra and compra.get("ativo"):
        cliente["ativo"] = True
        cliente["plano"] = compra.get("plano", cliente.get("plano", "desconhecido"))
        clientes[chave] = cliente
        salvar_clientes_telegram(clientes)
        ativo, dias, status = verificar_status_cliente(cliente)
        if cliente.get("afiliado_id") and cliente.get("chat_id"):
            texto = (
                f"👋 Olá, <b>{nome}</b>!\n\n"
                "✅ Seu cadastro está ativo.\n"
                f"📦 Plano: <b>{html.escape(cliente.get('plano', 'desconhecido'))}</b>\n"
                f"⏳ Vence em <b>{dias} dias</b>\n\n"
                "Seu grupo já está configurado. O Radar continuará enviando as ofertas automaticamente."
            )
        elif cliente.get("afiliado_id"):
            texto = (
                f"👋 Olá, <b>{nome}</b>!\n\n"
                "✅ Seu Telegram está vinculado e seu ID de afiliado já foi salvo.\n\n"
                "Agora adicione o Radar e o bot da Cakto como administradores do seu grupo e envie <b>/configurar</b> dentro dele."
            )
        else:
            texto = (
                f"👋 Olá, <b>{nome}</b>!\n\n"
                "✅ Seu Telegram já está vinculado ao Radar.\n\n"
                "Agora me envie seu <b>ID de afiliado Shopee</b>."
            )
    else:
        texto = (
            f"👋 Olá, <b>{nome}</b>!\n\n"
            "Você chegou ao <b>Radar de Promoções VIP</b>. 🛒\n\n"
            "✅ Seu Telegram foi identificado com sucesso.\n\n"
            "📧 Para localizar sua compra no Cakto, envie agora o "
            "<b>e-mail usado na compra</b>."
        )
    await update.message.reply_text(texto, parse_mode="HTML")
    logging.info("🤖 /start recebido | telegram_id=%s | nome=%s", user.id, user.full_name)

async def receber_dados_onboarding(update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    if getattr(update.effective_chat, "type", "") != "private":
        return
    texto = (update.message.text or "").strip()
    if not texto or texto.startswith("/"):
        return
    user_id = update.effective_user.id
    clientes = carregar_clientes_telegram()
    cliente = clientes.get(str(user_id), {})
    email = email_normalizado(texto)
    # Primeiro passo: vincular Telegram à compra Cakto pelo e-mail.
    if not cliente.get("email_cakto"):
        if "@" not in email or "." not in email.split("@")[-1]:
            await update.message.reply_text("📧 Envie somente o e-mail usado na compra do Radar no Cakto.")
            return
        compra = encontrar_cakto_por_email(email)
        if not compra:
            await update.message.reply_text(
                "❌ Não encontrei uma compra do Radar para esse e-mail.\n\n"
                "Confira se é exatamente o mesmo e-mail usado no Cakto."
            )
            logging.warning("⚠️ E-mail sem compra Cakto | telegram_id=%s | email=%s", user_id, email)
            return
        if not compra.get("ativo"):
            await update.message.reply_text("⚠️ Encontrei seu cadastro, mas a assinatura não está ativa no momento.")
            return
        # ✅ Define datas do plano na ativação
        plano = compra.get("plano", "desconhecido")
        cliente["email_cakto"] = email
        cliente["plano"] = plano
        cliente["ativo"] = True
        cliente["inicio_plano"] = datetime.now(FUSO_BR).isoformat()
        cliente["data_fim_plano"] = calcular_data_fim(plano).isoformat()
        cliente["cakto_atualizado"] = compra.get("atualizado_em", "")
        clientes[str(user_id)] = cliente
        salvar_clientes_telegram(clientes)
        await update.message.reply_text(
            "🎉 <b>Compra localizada!</b>\n\n"
            f"Plano: <b>{html.escape(plano)}</b>\n"
            f"Válido até: {datetime.fromisoformat(cliente['data_fim_plano']).strftime('%d/%m/%Y')}\n"
            "Telegram vinculado com sucesso.\n\n"
            "Agora me envie seu <b>ID de afiliado Shopee</b>.",
            parse_mode="HTML"
        )
        logging.info("🔗 Cliente vinculado | telegram_id=%s | plano=%s", user_id, plano)
        return
    # Segundo passo: guardar o ID de afiliado Shopee.
    if not cliente.get("afiliado_id"):
        if not texto.isdigit() or not 6 <= len(texto) <= 20:
            await update.message.reply_text("🛒 Envie somente o seu ID numérico de afiliado Shopee.")
            return
        cliente["afiliado_id"] = texto
        cliente["atualizado_em"] = datetime.now(FUSO_BR).isoformat()
        clientes[str(user_id)] = cliente
        salvar_clientes_telegram(clientes)
        await update.message.reply_text(
            "✅ <b>ID de afiliado salvo!</b>\n\n"
            "Agora falta só configurar o seu destino.\n\n"
            "1️⃣ Adicione <b>este Radar</b> como administrador.\n"
            "2️⃣ Mantenha também o <b>bot da Cakto</b> como administrador para o funcionamento da integração da Cakto.\n"
            "3️⃣ Dentro do seu grupo/canal, envie <b>/configurar</b>.\n\n"
            "Para ativar o Radar, a assinatura ativa e o Radar como administrador são os requisitos obrigatórios.",
            parse_mode="HTML"
        )
        logging.info("🛒 Afiliado salvo | telegram_id=%s | afiliado_id=%s", user_id, texto)

async def localizar_admins_grupo(bot, chat_id):
    """Verifica Radar e CaktoBot de forma robusta, inclusive em canais."""
    try:
        admins = await bot.get_chat_administrators(chat_id)
        me = await bot.get_me()
        bot_admin = any(m.user and m.user.id == me.id for m in admins)
        cakto_admin = False
        cakto_encontrado = ""
        resumo_admins = []
        alvo = CAKTO_BOT_USERNAME.lower().lstrip("@")
        for m in admins:
            if not m.user:
                continue
            u = m.user
            username = (u.username or "").strip().lower().lstrip("@")
            first_name = (u.first_name or "").strip().lower()
            last_name = (u.last_name or "").strip().lower()
            full_name = (u.full_name or "").strip().lower()
            texto_identificacao = " ".join(
                x for x in (username, first_name, last_name, full_name) if x
            )
            resumo_admins.append(
                f"id={u.id}|user=@{username or '-'}|nome={u.full_name or '-'}|bot={getattr(u, 'is_bot', False)}"
            )
            eh_cakto = (
                (alvo and alvo in texto_identificacao)
                or "cakto" in texto_identificacao
            )
            if eh_cakto:
                cakto_admin = True
                cakto_encontrado = (
                    f"@{username}" if username else (u.full_name or u.first_name or str(u.id))
                )
        logging.info(
            "🔎 ADMINISTRADORES ENCONTRADOS | chat_id=%s | total=%s | %s",
            chat_id, len(resumo_admins), " || ".join(resumo_admins) if resumo_admins else "nenhum"
        )
        logging.info(
            "🔎 Admins grupo | chat_id=%s | Radar=%s | Cakto=%s | identificado=%s",
            chat_id, bot_admin, cakto_admin, cakto_encontrado or "nenhum"
        )
        return bot_admin, cakto_admin
    except Exception as e:
        logging.error(
            "❌ Erro verificando administradores | chat_id=%s | %s",
            chat_id, e, exc_info=True
        )
        return False, False

def gerar_codigo_configuracao():
    return "RADAR-" + secrets.token_hex(3).upper()

def salvar_codigo_configuracao(clientes, user_id, cliente):
    codigo = gerar_codigo_configuracao()
    cliente["codigo_configuracao"] = codigo
    cliente["codigo_configuracao_expira"] = (datetime.now(FUSO_BR) + timedelta(minutes=30)).isoformat()
    clientes[str(user_id)] = cliente
    salvar_clientes_telegram(clientes)
    return codigo

def localizar_cliente_por_codigo(codigo):
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None, None, "nao_encontrado"
    clientes = carregar_clientes_telegram()
    agora = datetime.now(FUSO_BR)
    for chave, cliente in clientes.items():
        if str(cliente.get("codigo_configuracao", "")).upper() != codigo:
            continue
        expira = cliente.get("codigo_configuracao_expira", "")
        try:
            if expira and datetime.fromisoformat(expira) < agora:
                return None, None, "expirado"
        except Exception:
            return None, None, "invalido"
        return chave, cliente, None
    return None, None, "nao_encontrado"

async def emitir_codigo_configuracao(update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    user = update.effective_user
    clientes = carregar_clientes_telegram()
    cliente = clientes.get(str(user.id), {})
    email = cliente.get("email_cakto", "")
    compra = encontrar_cakto_por_email(email) if email else None
    if not email:
        await update.message.reply_text(
            "📧 <b>Antes de configurar o destino, preciso vincular sua compra.</b>\n\n"
            "Envie agora o <b>e-mail usado na compra do Radar no Cakto</b>.\n\n"
            "Assim que eu localizar sua assinatura, vou vincular seu Telegram e continuar a configuração automaticamente.",
            parse_mode="HTML"
        )
        logging.info("🔗 /configurar aguardando e-mail Cakto | telegram_id=%s", user.id)
        return
    if not compra or not compra.get("ativo"):
        await update.message.reply_text(
            "⚠️ Não consegui validar uma assinatura ativa para o e-mail vinculado a este Telegram.\n\n"
            "Se você acabou de comprar, confirme se está usando o mesmo e-mail informado no Cakto."
        )
        return
    if not cliente.get("afiliado_id"):
        await update.message.reply_text(
            "⚠️ Primeiro conclua seu cadastro no privado do bot com seu ID de afiliado Shopee."
        )
        return
    codigo = salvar_codigo_configuracao(clientes, user.id, cliente)
    await update.message.reply_text(
        "🔐 <b>Código de configuração gerado</b>\n\n"
        f"<code>{codigo}</code>\n\n"
        "⏱️ Este código vale por <b>30 minutos</b> e é de uso único.\n\n"
        "Agora vá para o <b>canal/grupo que receberá as ofertas</b> e publique exatamente:\n\n"
        f"<code>/configurar {codigo}</code>\n\n"
        "✅ O Radar precisa estar como administrador.\n"
        "ℹ️ O CaktoBot pode permanecer como administrador para a integração da Cakto, mas não bloqueia a ativação do Radar."
        , parse_mode="HTML"
    )
    logging.info("🔐 Código de configuração gerado | telegram_id=%s | expira_em=30min", user.id)

async def comando_configurar(update, context: ContextTypes.DEFAULT_TYPE):
    raw = {}
    try:
        raw = update.to_dict() if update else {}
    except Exception:
        raw = {}
    mensagem = (
        getattr(update, "message", None)
        or getattr(update, "edited_message", None)
        or getattr(update, "channel_post", None)
        or getattr(update, "edited_channel_post", None)
    )
    if not mensagem:
        logging.warning(
            "🚨 V55 /configurar SEM OBJETO MESSAGE | update=%s | chaves=%s | raw_message=%s | raw_chat=%s | raw_from=%s",
            type(update).__name__, list(raw.keys()),
            bool(raw.get("message") or raw.get("edited_message")),
            bool((raw.get("message") or raw.get("edited_message") or {}).get("chat")),
            bool((raw.get("message") or raw.get("edited_message") or {}).get("from"))
        )
    raw_msg = (raw.get("message") or raw.get("edited_message") or raw.get("channel_post") or raw.get("edited_channel_post") or {})
    raw_chat = raw_msg.get("chat") or {}
    raw_from = raw_msg.get("from") or {}
    raw_sender_chat = raw_msg.get("sender_chat") or {}
    chat_mensagem = getattr(mensagem, "chat", None) if mensagem else None
    chat_efetivo = getattr(update, "effective_chat", None)
    chat = chat_mensagem or chat_efetivo
    chat_id = getattr(chat_mensagem, "id", None) or getattr(chat_efetivo, "id", None) or raw_chat.get("id")
    chat_type = getattr(chat_mensagem, "type", None) or getattr(chat_efetivo, "type", None) or raw_chat.get("type", "")
    chat_title = getattr(chat_mensagem, "title", None) or getattr(chat_efetivo, "title", None) or raw_chat.get("title", "")
    usuario = getattr(update, "effective_user", None)
    if not usuario and mensagem:
        usuario = getattr(mensagem, "from_user", None)
    user_id = getattr(usuario, "id", None) or raw_from.get("id")
    sender_chat = getattr(mensagem, "sender_chat", None) if mensagem else None
    sender_chat_id = getattr(sender_chat, "id", None) or raw_sender_chat.get("id")
    texto_comando = ""
    if mensagem:
        texto_comando = (getattr(mensagem, "text", None) or getattr(mensagem, "caption", None) or "").strip()
    if not texto_comando:
        texto_comando = (raw_msg.get("text") or raw_msg.get("caption") or "").strip()
    bot_username = (getattr(context.bot, "username", "") or "").strip()
    logging.info(
        "⚙️ V55 /configurar RECEBIDO | update_id=%s | chat_mensagem_id=%s | chat_mensagem_tipo=%s | effective_chat_id=%s | effective_chat_tipo=%s | usuario_id=%s | sender_chat_id=%s | comando=%s | bot=@%s",
        getattr(update, "update_id", None),
        getattr(chat_mensagem, "id", None), getattr(chat_mensagem, "type", None),
        getattr(chat_efetivo, "id", None), getattr(chat_efetivo, "type", None),
        user_id, sender_chat_id, texto_comando or "(sem texto)", bot_username
    )
    if not chat_id:
        logging.warning("🚨 V50 UPDATE SEM CHAT | raw=%s", raw)
        return
    async def responder(texto, parse_mode="HTML"):
        try:
            if mensagem:
                await mensagem.reply_text(texto, parse_mode=parse_mode)
            else:
                await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode=parse_mode)
        except Exception as e:
            logging.error("❌ V50 falha ao responder | chat_id=%s | erro=%s", chat_id, e, exc_info=True)
    if chat_type == "channel":
        partes = texto_comando.split() if texto_comando else []
        codigo = partes[1].strip() if len(partes) >= 2 else ""
        if not codigo:
            await responder(
                "⚠️ <b>Este destino é um canal do Telegram.</b>\n\n"
                "No canal, a configuração precisa ser autorizada pelo código gerado no privado do bot.\n\n"
                "1️⃣ Abra a conversa privada com o Radar.\n"
                "2️⃣ Envie <b>/configurar</b>.\n"
                "3️⃣ Copie o código recebido.\n"
                "4️⃣ Volte para este canal e publique:\n"
                "<code>/configurar SEU_CODIGO</code>"
            )
            return
        chave, cliente, erro_codigo = localizar_cliente_por_codigo(codigo)
        if erro_codigo:
            await responder("❌ Código de configuração inválido, expirado ou já utilizado. Gere um novo código no privado do Radar com <b>/configurar</b>.")
            logging.warning("⚠️ Código de configuração rejeitado | chat_id=%s | motivo=%s", chat_id, erro_codigo)
            return
        email = cliente.get("email_cakto", "")
        compra = encontrar_cakto_por_email(email) if email else None
        if not compra or not compra.get("ativo"):
            await responder("⚠️ A assinatura Cakto vinculada a este código não está ativa.")
            return
        if not cliente.get("afiliado_id"):
            await responder("⚠️ O cadastro deste cliente ainda não possui ID de afiliado Shopee.")
            return
        bot_admin, cakto_admin = await localizar_admins_grupo(context.bot, chat_id)
        logging.info("🔎 Canal verificado | chat_id=%s | Radar=%s | Cakto=%s", chat_id, bot_admin, cakto_admin)
        if not cakto_admin:
            logging.warning(
                "⚠️ CaktoBot não retornado pela API do Telegram | chat_id=%s | "
                "prosseguindo porque assinatura Cakto está ativa e Radar é administrador",
                chat_id
            )
        if not bot_admin:
            await responder(
                "⚠️ <b>O Radar ainda não está como administrador deste canal.</b>\n\n"
                "Adicione este Radar como administrador e publique novamente o comando com o mesmo código."
            )
            return
        ativo, dias, status = verificar_status_cliente(cliente)
        cliente.update({
            "chat_id": chat_id,
            "grupo_nome": chat_title or "Canal sem nome",
            "grupo_username": getattr(chat, "username", "") or raw_chat.get("username", "") or "",
            "grupo_configurado": True,
            "grupo_ativo": ativo,
            "bot_admin": True,
            "cakto_bot_admin": bool(cakto_admin),
            "tipo_destino": "channel",
            "configurado_em": datetime.now(FUSO_BR).isoformat(),
            "plano": compra.get("plano", cliente.get("plano", "desconhecido")),
            "ativo": ativo,
            "codigo_configuracao": "",
            "codigo_configuracao_expira": "",
        })
        clientes = carregar_clientes_telegram()
        clientes[str(chave)] = cliente
        salvar_clientes_telegram(clientes)
        status_texto = f"Vence em {dias} dias" if ativo else "INATIVO — envio pausado"
        await responder(
            "🎉 <b>CANAL CONFIGURADO COM SUCESSO!</b>\n\n"
            f"📦 Plano: <b>{html.escape(cliente.get('plano', 'desconhecido'))}</b>\n"
            f"🔗 Shopee ID: <b>{html.escape(str(cliente.get('afiliado_id')))}</b>\n"
            f"📢 Canal: <b>{html.escape(chat_title or 'Canal')}</b>\n"
            f"⏳ Status: <b>{status_texto}</b>\n\n"
            "✅ Radar administrador\n"
            + ("✅ CaktoBot administrador\n" if cakto_admin else "ℹ️ CaktoBot não retornado pela API do Telegram — não bloqueia a ativação\n")
            + ("🚀 A partir do próximo ciclo, as ofertas serão enviadas automaticamente aqui." if ativo else "⚠️ As ofertas não serão enviadas — renove sua assinatura para reativar.")
            , parse_mode="HTML"
        )
        logging.info("✅ Canal configurado | telegram_id=%s | chat_id=%s | canal=%s", chave, chat_id, chat_title)
        return
    if chat_type == "private" and user_id:
        await emitir_codigo_configuracao(update, context)
        return
    if chat_type not in ("group", "supergroup"):
        await responder("⚠️ O comando <b>/configurar</b> não chegou como grupo ou canal. Tipo detectado: <b>%s</b>." % html.escape(str(chat_type or "desconhecido")))
        return
    if not user_id:
        logging.warning(
            "⚠️ V55 /configurar sem usuario identificavel | chat_id=%s | sender_chat_id=%s",
            chat_id, sender_chat_id
        )
        await responder(
            "⚠️ <b>O Telegram não informou qual administrador enviou este comando.</b>\n\n"
            "Isso normalmente acontece quando o administrador está usando <b>Permanecer anônimo</b>.\n\n"
            "Desative essa opção para o seu usuário neste grupo e envie novamente:\n"
            "<b>/configurar@%s</b>" % html.escape(bot_username or "promodasofertas_bot")
        )
        return
    clientes = carregar_clientes_telegram()
    cliente = clientes.get(str(user_id), {})
    email = cliente.get("email_cakto", "")
    compra = encontrar_cakto_por_email(email) if email else None
    if not compra or not compra.get("ativo"):
        logging.warning("⚠️ /configurar bloqueado | chat_id=%s | usuario_id=%s | compra_ativa=False", chat_id, user_id)
        await responder("⚠️ Sua assinatura não está ativa ou ainda não foi vinculada ao Telegram.")
        return
    if not cliente.get("afiliado_id"):
        logging.warning("⚠️ /configurar bloqueado | chat_id=%s | usuario_id=%s | afiliado_nao_cadastrado", chat_id, user_id)
        await responder("⚠️ Primeiro conclua seu cadastro no privado do bot com seu ID de afiliado Shopee.")
        return
    try:
        membro = await context.bot.get_chat_member(chat_id, user_id)
        if membro.status not in ("administrator", "creator"):
            await responder("⚠️ Só o comprador que é administrador do grupo pode concluir esta configuração.")
            return
    except Exception as e:
        logging.exception("❌ Falha verificando administrador | chat_id=%s | usuario_id=%s | erro=%s", chat_id, user_id, e)
        await responder("⚠️ Não consegui verificar suas permissões de administrador neste grupo.")
        return
    bot_admin, cakto_admin = await localizar_admins_grupo(context.bot, chat_id)
    logging.info(
        "🔎 Admins verificados | chat_id=%s | radar_admin=%s | cakto_admin=%s",
        chat_id, bot_admin, cakto_admin
    )
    if not bot_admin:
        await responder(
            "⚠️ O Radar ainda não está como administrador deste grupo.\n\n"
            "Adicione este bot como administrador e envie <b>/configurar</b> novamente."
        )
        return
    if not cakto_admin:
        logging.warning(
            "⚠️ CaktoBot não retornado pela API do Telegram | chat_id=%s | "
            "prosseguindo com a configuração porque assinatura Cakto está ativa e Radar é administrador",
            chat_id
        )
    ativo, dias, status = verificar_status_cliente(cliente)
    cliente.update({
        "chat_id": chat_id,
        "grupo_nome": chat_title or "Grupo sem nome",
        "grupo_username": getattr(chat, "username", "") or raw_chat.get("username", "") or "",
        "grupo_configurado": True,
        "grupo_ativo": ativo,
        "bot_admin": True,
        "cakto_bot_admin": bool(cakto_admin),
        "configurado_em": datetime.now(FUSO_BR).isoformat(),
        "plano": compra.get("plano", cliente.get("plano", "desconhecido")),
        "ativo": ativo,
    })
    clientes[str(user_id)] = cliente
    salvar_clientes_telegram(clientes)
    status_texto = f"Vence em {dias} dias" if ativo else "INATIVO — envio pausado"
    await responder(
        "🎉 <b>GRUPO CONFIGURADO COM SUCESSO!</b>\n\n"
        f"📦 Plano: <b>{html.escape(cliente.get('plano', 'desconhecido'))}</b>\n"
        f"🔗 Shopee ID: <b>{html.escape(str(cliente.get('afiliado_id')))}</b>\n"
        f"👥 Grupo: <b>{html.escape(chat_title or 'Grupo')}</b>\n"
        f"⏳ Status: <b>{status_texto}</b>\n\n"
        "✅ Radar administrador\n"
        + ("✅ CaktoBot administrador\n" if cakto_admin else "ℹ️ CaktoBot não retornado pela API do Telegram — não bloqueia a ativação\n")
        + ("🚀 A partir do próximo ciclo, as ofertas serão enviadas automaticamente aqui." if ativo else "⚠️ As ofertas não serão enviadas — renove sua assinatura para reativar.")
        , parse_mode="HTML"
    )
    logging.info("✅ Grupo configurado | telegram_id=%s | chat_id=%s | grupo=%s", user_id, chat_id, chat_title)
    global LINKS_CICLO_ATUAL, TERMOS_USADOS_CICLO
    LINKS_CICLO_ATUAL.clear()
    TERMOS_USADOS_CICLO.clear()

async def validar_cliente_grupo(bot, cliente):
    if not cliente.get("grupo_configurado") or not cliente.get("chat_id"):
        return False
    ativo, dias, status = verificar_status_cliente(cliente)
    if not ativo:
        # ✅ Envia aviso de vencimento quando for o momento
        if dias in [3, 2, 1, 0]:
            
        
