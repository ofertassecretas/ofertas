# PRIMEIRO â€” TODOS OS IMPORTS
import os
import asyncio, requests, logging, random, hashlib, time, json, html, re, tempfile, secrets
from collections import Counter
from difflib import SequenceMatcher
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

# AGORA SIM â€” DEPOIS DOS IMPORTS, roda o diagnÃ³stico
print("=" * 50)
print("ðŸ” VERIFICANDO VARIÃVEIS DE AMBIENTE...")
print(f"URL_DO_BANCO_DE_DADOS configurada = {bool(os.getenv('URL_DO_BANCO_DE_DADOS'))}")
print(f"DATABASE_URL configurada = {bool(os.getenv('DATABASE_URL'))}")
print("=" * 50)

print("VERSAO V57-CAKTO-CANAIS-DADOS-PERSISTENTES")

try:
    import psycopg2
    from psycopg2.extras import Json
    print("âœ… psycopg2 carregado com sucesso")
except Exception as e:
    print(f"âš ï¸ Erro ao carregar psycopg2: {type(e).__name__}: {e}")
    psycopg2 = None
    Json = None

# =========================
# CONFIG â€” CORRIGIDO
# =========================
TELEGRAM_TOKEN = (os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
SHOPEE_PASSWORD = os.getenv("SHOPEE_PASSWORD", "").strip()
SHOPEE_APP_ID = "18349740277"
CHAT_ID_DESTINO = -1003848415150
CHAT_ID_FREE = -1003886228244
AFILIADO_ID = "18349740277"
CAKTO_BOT_USERNAME = (os.getenv("CAKTO_BOT_USERNAME") or "CaktoBot").strip().lstrip("@")

# âœ… Leitura ajustada â€” PRIORIZA URL_DO_BANCO_DE_DADOS (Railway)
_raw_db_url = os.getenv("URL_DO_BANCO_DE_DADOS") or os.getenv("DATABASE_URL")
if _raw_db_url:
    # Corrige o esquema: postgresql:// â†’ postgres://
    DATABASE_URL = _raw_db_url.replace("postgresql://", "postgres://")
    print(f"âœ… URL do banco encontrada e pronta!")
    print("ðŸ”— EndereÃ§o do banco carregado (credenciais ocultas).")
else:
    DATABASE_URL = None
    print("âš ï¸ Nenhuma variÃ¡vel de banco encontrada!")
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

# ðŸš« PALAVRAS PROIBIDAS
PALAVRAS_PROIBIDAS = [
    "mousepad", "mouse pad", "tapete de mouse", "almofada de mouse",
    "mouse", "pad mouse", "pad para mouse"
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# =========================
# ðŸ¤– ONBOARDING / CLIENTES
# =========================
CLIENTES_TELEGRAM = "clientes_telegram.json"
CLIENTES_CAKTO = "clientes_cakto.json"
DB_PRONTA = False
DB_AVISO_EMITIDO = False

def _db_conectar():
    if not DATABASE_URL or psycopg2 is None:
        logging.warning("âš ï¸ Banco indisponÃ­vel â€” DATABASE_URL configurada: %s | psycopg2 disponÃ­vel: %s" % (bool(DATABASE_URL), psycopg2 is not None))
        return None
    try:
        return psycopg2.connect(DATABASE_URL, connect_timeout=10)
    except Exception as e:
        logging.error("âŒ Falha na conexÃ£o com o banco: %s", e)
        return None

def inicializar_banco_persistente():
    """Cria as tabelas e migra o JSON local apenas se a tabela estiver vazia."""
    global DB_PRONTA, DB_AVISO_EMITIDO
    if not DATABASE_URL:
        logging.warning("âš ï¸ DATABASE_URL nÃ£o configurada â€” clientes continuam no JSON local")
        return
    if psycopg2 is None:
        logging.error("âŒ psycopg2 nÃ£o instalado â€” configure psycopg2-binary no requirements.txt")
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
                        logging.info("ðŸ—„ï¸ MigraÃ§Ã£o inicial: %s cliente(s) Telegram para o banco", len(locais))
                if vazio_ck:
                    locais = carregar_json(CLIENTES_CAKTO, {})
                    for chave, dados in locais.items():
                        cur.execute(
                            "INSERT INTO radar_clientes_cakto (chave, dados) VALUES (%s, %s) ON CONFLICT (chave) DO NOTHING",
                            (str(chave), Json(dados))
                        )
                    if locais:
                        logging.info("ðŸ—„ï¸ MigraÃ§Ã£o inicial: %s registro(s) Cakto para o banco", len(locais))
        DB_PRONTA = True
        logging.info("ðŸ—„ï¸ Banco persistente PostgreSQL ativo para clientes")
    except Exception as e:
        logging.error("âŒ Falha iniciando banco persistente: %s", e, exc_info=True)
        DB_PRONTA = False

def _db_carregar(tabela):
    try:
        with _db_conectar() as conn:
            with conn.cursor() as cur:
                cur.execute(f"SELECT chave, dados FROM {tabela}")
                return {str(chave): (dados or {}) for chave, dados in cur.fetchall()}
    except Exception as e:
        logging.error("âŒ Falha lendo %s: %s", tabela, e)
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
        logging.error("âŒ Falha salvando %s: %s", tabela, e)
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
    if compra and compra.get("ativo"):
        cliente["ativo"] = True
        cliente["plano"] = compra.get("plano", cliente.get("plano", "desconhecido"))
        clientes[chave] = cliente
        salvar_clientes_telegram(clientes)
        if cliente.get("afiliado_id") and cliente.get("chat_id"):
            texto = (
                f"ðŸ‘‹ OlÃ¡, <b>{nome}</b>!\n\n"
                "âœ… Seu cadastro estÃ¡ ativo.\n"
                f"ðŸ“¦ Plano: <b>{html.escape(cliente.get('plano', 'desconhecido'))}</b>\n\n"
                "Seu grupo jÃ¡ estÃ¡ configurado. O Radar continuarÃ¡ enviando as ofertas automaticamente."
            )
        elif cliente.get("afiliado_id"):
            texto = (
                f"ðŸ‘‹ OlÃ¡, <b>{nome}</b>!\n\n"
                "âœ… Seu Telegram estÃ¡ vinculado e seu ID de afiliado jÃ¡ foi salvo.\n\n"
                "Agora adicione o Radar e o bot da Cakto como administradores do seu grupo e envie <b>/configurar</b> dentro dele."
            )
        else:
            texto = (
                f"ðŸ‘‹ OlÃ¡, <b>{nome}</b>!\n\n"
                "âœ… Seu Telegram jÃ¡ estÃ¡ vinculado ao Radar.\n\n"
                "Agora me envie seu <b>ID de afiliado Shopee</b>."
            )
    else:
        texto = (
            f"ðŸ‘‹ OlÃ¡, <b>{nome}</b>!\n\n"
            "VocÃª chegou ao <b>Radar de PromoÃ§Ãµes VIP</b>. ðŸ›’\n\n"
            "âœ… Seu Telegram foi identificado com sucesso.\n\n"
            "ðŸ“§ Para localizar sua compra no Cakto, envie agora o "
            "<b>e-mail usado na compra</b>."
        )
    await update.message.reply_text(texto, parse_mode="HTML")
    logging.info("ðŸ¤– /start recebido | telegram_id=%s | nome=%s", user.id, user.full_name)

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

    # Primeiro passo: vincular Telegram Ã  compra Cakto pelo e-mail.
    if not cliente.get("email_cakto"):
        if "@" not in email or "." not in email.split("@")[-1]:
            await update.message.reply_text("ðŸ“§ Envie somente o e-mail usado na compra do Radar no Cakto.")
            return

        compra = encontrar_cakto_por_email(email)
        if not compra:
            await update.message.reply_text(
                "âŒ NÃ£o encontrei uma compra do Radar para esse e-mail.\n\n"
                "Confira se Ã© exatamente o mesmo e-mail usado no Cakto."
            )
            logging.warning("âš ï¸ E-mail sem compra Cakto | telegram_id=%s | email=%s", user_id, email)
            return

        if not compra.get("ativo"):
            await update.message.reply_text("âš ï¸ Encontrei seu cadastro, mas a assinatura nÃ£o estÃ¡ ativa no momento.")
            return

        cliente["email_cakto"] = email
        cliente["plano"] = compra.get("plano", "desconhecido")
        cliente["ativo"] = True
        cliente["cakto_atualizado"] = compra.get("atualizado_em", "")
        clientes[str(user_id)] = cliente
        salvar_clientes_telegram(clientes)

        await update.message.reply_text(
            "ðŸŽ‰ <b>Compra localizada!</b>\n\n"
            f"Plano: <b>{html.escape(cliente['plano'])}</b>\n"
            "Telegram vinculado com sucesso.\n\n"
            "Agora me envie seu <b>ID de afiliado Shopee</b>.",
            parse_mode="HTML"
        )
        logging.info("ðŸ”— Cliente vinculado | telegram_id=%s | plano=%s", user_id, cliente["plano"])
        return

    # Segundo passo: guardar o ID de afiliado Shopee.
    if not cliente.get("afiliado_id"):
        if not texto.isdigit() or not 6 <= len(texto) <= 20:
            await update.message.reply_text("ðŸ›’ Envie somente o seu ID numÃ©rico de afiliado Shopee.")
            return
        cliente["afiliado_id"] = texto
        cliente["atualizado_em"] = datetime.now(FUSO_BR).isoformat()
        clientes[str(user_id)] = cliente
        salvar_clientes_telegram(clientes)
        await update.message.reply_text(
            "âœ… <b>ID de afiliado salvo!</b>\n\n"
            "Agora falta sÃ³ configurar o seu destino.\n\n"
            "1ï¸âƒ£ Adicione <b>este Radar</b> como administrador.\n"
            "2ï¸âƒ£ Mantenha tambÃ©m o <b>bot da Cakto</b> como administrador para o funcionamento da integraÃ§Ã£o da Cakto.\n"
            "3ï¸âƒ£ Dentro do seu grupo/canal, envie <b>/configurar</b>.\n\n"
            "Para ativar o Radar, a assinatura ativa e o Radar como administrador sÃ£o os requisitos obrigatÃ³rios.",
            parse_mode="HTML"
        )
        logging.info("ðŸ›’ Afiliado salvo | telegram_id=%s | afiliado_id=%s", user_id, texto)


async def localizar_admins_grupo(bot, chat_id):
    """Verifica Radar e CaktoBot de forma robusta, inclusive em canais.

    O Telegram pode devolver username/nome de formas diferentes para bots.
    Por isso, alÃ©m do username, analisamos first_name, last_name e full_name,
    e registramos todos os administradores encontrados para diagnÃ³stico real.
    """
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

            # IdentificaÃ§Ã£o ampla do CaktoBot. O nome mostrado no Telegram
            # pode ser "Cakto", "Cakto Bot" ou ter username diferente.
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
            "ðŸ”Ž ADMINISTRADORES ENCONTRADOS | chat_id=%s | total=%s | %s",
            chat_id, len(resumo_admins), " || ".join(resumo_admins) if resumo_admins else "nenhum"
        )
        logging.info(
            "ðŸ”Ž Admins grupo | chat_id=%s | Radar=%s | Cakto=%s | identificado=%s",
            chat_id, bot_admin, cakto_admin, cakto_encontrado or "nenhum"
        )

        return bot_admin, cakto_admin

    except Exception as e:
        logging.error(
            "âŒ Erro verificando administradores | chat_id=%s | %s",
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
        return None, None, None
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

    # Se o Telegram ainda nÃ£o foi vinculado Ã  compra, nÃ£o devemos tratar isso
    # como assinatura inativa. Neste primeiro vÃ­nculo, o cliente precisa informar
    # o mesmo e-mail usado no Cakto. Depois disso, /configurar poderÃ¡ gerar o cÃ³digo.
    if not email:
        await update.message.reply_text(
            "ðŸ“§ <b>Antes de configurar o destino, preciso vincular sua compra.</b>\n\n"
            "Envie agora o <b>e-mail usado na compra do Radar no Cakto</b>.\n\n"
            "Assim que eu localizar sua assinatura, vou vincular seu Telegram e continuar a configuraÃ§Ã£o automaticamente.",
            parse_mode="HTML"
        )
        logging.info("ðŸ”— /configurar aguardando e-mail Cakto | telegram_id=%s", user.id)
        return

    if not compra or not compra.get("ativo"):
        await update.message.reply_text(
            "âš ï¸ NÃ£o consegui validar uma assinatura ativa para o e-mail vinculado a este Telegram.\n\n"
            "Se vocÃª acabou de comprar, confirme se estÃ¡ usando o mesmo e-mail informado no Cakto."
        )
        return
    if not cliente.get("afiliado_id"):
        await update.message.reply_text(
            "âš ï¸ Primeiro conclua seu cadastro no privado do bot com seu ID de afiliado Shopee."
        )
        return

    codigo = salvar_codigo_configuracao(clientes, user.id, cliente)
    await update.message.reply_text(
        "ðŸ” <b>CÃ³digo de configuraÃ§Ã£o gerado</b>\n\n"
        f"<code>{codigo}</code>\n\n"
        "â±ï¸ Este cÃ³digo vale por <b>30 minutos</b> e Ã© de uso Ãºnico.\n\n"
        "Agora vÃ¡ para o <b>canal/grupo que receberÃ¡ as ofertas</b> e publique exatamente:\n\n"
        f"<code>/configurar {codigo}</code>\n\n"
        "âœ… O Radar precisa estar como administrador.\n"
        "â„¹ï¸ O CaktoBot pode permanecer como administrador para a integraÃ§Ã£o da Cakto, mas nÃ£o bloqueia a ativaÃ§Ã£o do Radar."
        , parse_mode="HTML"
    )
    logging.info("ðŸ” CÃ³digo de configuraÃ§Ã£o gerado | telegram_id=%s | expira_em=30min", user.id)

async def comando_configurar(update, context: ContextTypes.DEFAULT_TYPE):
    # V49: extracao robusta do update. Em vez de depender somente de
    # effective_message/effective_user, tambem usamos o dicionario bruto
    # quando o Telegram/versao da biblioteca entregar a atualizacao de outra forma.
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
            "ðŸš¨ V55 /configurar SEM OBJETO MESSAGE | update=%s | chaves=%s | raw_message=%s | raw_chat=%s | raw_from=%s",
            type(update).__name__, list(raw.keys()),
            bool(raw.get("message") or raw.get("edited_message")),
            bool((raw.get("message") or raw.get("edited_message") or {}).get("chat")),
            bool((raw.get("message") or raw.get("edited_message") or {}).get("from"))
        )

    raw_msg = (raw.get("message") or raw.get("edited_message") or raw.get("channel_post") or raw.get("edited_channel_post") or {})
    raw_chat = raw_msg.get("chat") or {}
    raw_from = raw_msg.get("from") or {}
    raw_sender_chat = raw_msg.get("sender_chat") or {}

    # V50: prioriza o chat que pertence diretamente Ã  mensagem recebida.
    # effective_chat Ã© usado apenas como fallback, evitando classificar o comando
    # pelo contexto errado quando uma atualizaÃ§Ã£o contÃ©m mais de um campo.
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
        "âš™ï¸ V55 /configurar RECEBIDO | update_id=%s | chat_mensagem_id=%s | chat_mensagem_tipo=%s | effective_chat_id=%s | effective_chat_tipo=%s | usuario_id=%s | sender_chat_id=%s | comando=%s | bot=@%s",
        getattr(update, "update_id", None),
        getattr(chat_mensagem, "id", None), getattr(chat_mensagem, "type", None),
        getattr(chat_efetivo, "id", None), getattr(chat_efetivo, "type", None),
        user_id, sender_chat_id, texto_comando or "(sem texto)", bot_username
    )

    # Se ainda nao conseguimos nem o chat, mostramos o update cru no log para
    # descobrir exatamente qual tipo de update o Telegram esta entregando.
    if not chat_id:
        logging.warning("ðŸš¨ V50 UPDATE SEM CHAT | raw=%s", raw)
        return

    # A partir daqui, quando o objeto Message existe usamos reply_text normalmente.
    # Quando nao existe, enviamos diretamente para o chat_id extraido do update bruto.
    async def responder(texto, parse_mode="HTML"):
        try:
            if mensagem:
                await mensagem.reply_text(texto, parse_mode=parse_mode)
            else:
                await context.bot.send_message(chat_id=chat_id, text=texto, parse_mode=parse_mode)
        except Exception as e:
            logging.error("âŒ V50 falha ao responder | chat_id=%s | erro=%s", chat_id, e, exc_info=True)

    # CANAL: posts chegam como update.channel_post e normalmente nÃ£o possuem
    # usuÃ¡rio em "from". Por isso a configuraÃ§Ã£o de canal usa um cÃ³digo Ãºnico
    # gerado no privado do bot. Isso evita vincular um canal ao cliente errado.
    if chat_type == "channel":
        partes = texto_comando.split() if texto_comando else []
        codigo = partes[1].strip() if len(partes) >= 2 else ""
        if not codigo:
            await responder(
                "âš ï¸ <b>Este destino Ã© um canal do Telegram.</b>\n\n"
                "No canal, a configuraÃ§Ã£o precisa ser autorizada pelo cÃ³digo gerado no privado do Radar.\n\n"
                "1ï¸âƒ£ Abra a conversa privada com o Radar.\n"
                "2ï¸âƒ£ Envie <b>/configurar</b>.\n"
                "3ï¸âƒ£ Copie o cÃ³digo recebido.\n"
                "4ï¸âƒ£ Volte para este canal e publique:\n"
                "<code>/configurar SEU_CODIGO</code>"
            )
            return

        chave, cliente, erro_codigo = localizar_cliente_por_codigo(codigo)
        if erro_codigo:
            await responder("âŒ CÃ³digo de configuraÃ§Ã£o invÃ¡lido, expirado ou jÃ¡ utilizado. Gere um novo cÃ³digo no privado do Radar com <b>/configurar</b>.")
            logging.warning("âš ï¸ CÃ³digo de configuraÃ§Ã£o rejeitado | chat_id=%s | motivo=%s", chat_id, erro_codigo)
            return

        email = cliente.get("email_cakto", "")
        compra = encontrar_cakto_por_email(email) if email else None
        if not compra or not compra.get("ativo"):
            await responder("âš ï¸ A assinatura Cakto vinculada a este cÃ³digo nÃ£o estÃ¡ ativa.")
            return
        if not cliente.get("afiliado_id"):
            await responder("âš ï¸ O cadastro deste cliente ainda nÃ£o possui ID de afiliado Shopee.")
            return

        bot_admin, cakto_admin = await localizar_admins_grupo(context.bot, chat_id)
        logging.info("ðŸ”Ž Canal verificado | chat_id=%s | Radar=%s | Cakto=%s", chat_id, bot_admin, cakto_admin)

        # V55: o CaktoBot nÃ£o bloqueia mais a configuraÃ§Ã£o.
        # A assinatura ativa Ã© validada diretamente pelo cadastro recebido da Cakto
        # e o Radar precisa ser administrador para conseguir publicar as ofertas.
        # A API do Telegram pode nÃ£o retornar o CaktoBot em getChatAdministrators
        # mesmo quando ele aparece na interface do canal.
        if not cakto_admin:
            logging.warning(
                "âš ï¸ CaktoBot nÃ£o retornado pela API do Telegram | chat_id=%s | "
                "prosseguindo porque assinatura Cakto estÃ¡ ativa e Radar Ã© administrador",
                chat_id
            )

        if not bot_admin:
            await responder(
                "âš ï¸ <b>O Radar ainda nÃ£o estÃ¡ como administrador deste canal.</b>\n\n"
                "Adicione este Radar como administrador e publique novamente o comando com o mesmo cÃ³digo."
            )
            return

        cliente.update({
            "chat_id": chat_id,
            "grupo_nome": chat_title or "Canal sem nome",
            "grupo_username": getattr(chat, "username", "") or raw_chat.get("username", "") or "",
            "grupo_configurado": True,
            "grupo_ativo": True,
            "bot_admin": True,
            "cakto_bot_admin": bool(cakto_admin),
            "tipo_destino": "channel",
            "configurado_em": datetime.now(FUSO_BR).isoformat(),
            "plano": compra.get("plano", cliente.get("plano", "desconhecido")),
            "ativo": True,
            "codigo_configuracao": "",
            "codigo_configuracao_expira": "",
        })
        clientes = carregar_clientes_telegram()
        clientes[str(chave)] = cliente
        salvar_clientes_telegram(clientes)
        await responder(
            "ðŸŽ‰ <b>CANAL CONFIGURADO COM SUCESSO!</b>\n\n"
            f"ðŸ“¦ Plano: <b>{html.escape(cliente.get('plano', 'desconhecido'))}</b>\n"
            f"ðŸ”— Shopee ID: <b>{html.escape(str(cliente.get('afiliado_id')))}</b>\n"
            f"ðŸ“¢ Canal: <b>{html.escape(chat_title or 'Canal')}</b>\n\n"
            "âœ… Radar administrador\n"
            + ("âœ… CaktoBot administrador\n" if cakto_admin else "â„¹ï¸ CaktoBot nÃ£o retornado pela API do Telegram â€” nÃ£o bloqueia a ativaÃ§Ã£o\n")
            + "ðŸš€ A partir do prÃ³ximo ciclo, as ofertas serÃ£o enviadas automaticamente aqui."
        )
        logging.info("âœ… Canal configurado | telegram_id=%s | chat_id=%s | canal=%s", chave, chat_id, chat_title)
        return

    # PRIVADO: /configurar gera o cÃ³digo que autoriza a configuraÃ§Ã£o
    # de um canal/grupo. Este bloco precisa vir ANTES da validaÃ§Ã£o de
    # group/supergroup, pois o comprador gera o cÃ³digo justamente no privado.
    if chat_type == "private" and user_id:
        await emitir_codigo_configuracao(update, context)
        return

    # CANAL jÃ¡ foi tratado acima. Qualquer outro tipo de chat nÃ£o pode
    # concluir a configuraÃ§Ã£o desta forma.
    if chat_type not in ("group", "supergroup"):
        await responder("âš ï¸ O comando <b>/configurar</b> nÃ£o chegou como grupo ou canal. Tipo detectado: <b>%s</b>." % html.escape(str(chat_type or "desconhecido")))
        return

    # Sem usuario identificavel, nao podemos vincular com seguranca o grupo a
    # uma compra Cakto. sender_chat indica normalmente envio em nome do grupo.
    if not user_id:
        logging.warning(
            "âš ï¸ V55 /configurar sem usuario identificavel | chat_id=%s | sender_chat_id=%s",
            chat_id, sender_chat_id
        )
        await responder(
            "âš ï¸ <b>O Telegram nÃ£o informou qual administrador enviou este comando.</b>\n\n"
            "Isso normalmente acontece quando o administrador estÃ¡ usando <b>Permanecer anÃ´nimo</b>.\n\n"
            "Desative essa opÃ§Ã£o para o seu usuÃ¡rio neste grupo e envie novamente:\n"
            "<b>/configurar@%s</b>" % html.escape(bot_username or "promodasofertas_bot")
        )
        return

    clientes = carregar_clientes_telegram()
    cliente = clientes.get(str(user_id), {})
    email = cliente.get("email_cakto", "")
    compra = encontrar_cakto_por_email(email) if email else None

    if not compra or not compra.get("ativo"):
        logging.warning("âš ï¸ /configurar bloqueado | chat_id=%s | usuario_id=%s | compra_ativa=False", chat_id, user_id)
        await responder("âš ï¸ Sua assinatura nÃ£o estÃ¡ ativa ou ainda nÃ£o foi vinculada ao Telegram.")
        return

    if not cliente.get("afiliado_id"):
        logging.warning("âš ï¸ /configurar bloqueado | chat_id=%s | usuario_id=%s | afiliado_nao_cadastrado", chat_id, user_id)
        await responder("âš ï¸ Primeiro conclua seu cadastro no privado do bot com seu ID de afiliado Shopee.")
        return

    try:
        membro = await context.bot.get_chat_member(chat_id, user_id)
        if membro.status not in ("administrator", "creator"):
            await responder("âš ï¸ SÃ³ o comprador que Ã© administrador do grupo pode concluir esta configuraÃ§Ã£o.")
            return
    except Exception as e:
        logging.exception("âŒ Falha verificando administrador | chat_id=%s | usuario_id=%s | erro=%s", chat_id, user_id, e)
        await responder("âš ï¸ NÃ£o consegui verificar suas permissÃµes de administrador neste grupo.")
        return

    bot_admin, cakto_admin = await localizar_admins_grupo(context.bot, chat_id)
    logging.info(
        "ðŸ”Ž Admins verificados | chat_id=%s | radar_admin=%s | cakto_admin=%s",
        chat_id, bot_admin, cakto_admin
    )

    if not bot_admin:
        await responder(
            "âš ï¸ O Radar ainda nÃ£o estÃ¡ como administrador deste grupo.\n\n"
            "Adicione este bot como administrador e envie <b>/configurar</b> novamente."
        )
        return

    if not cakto_admin:
        logging.warning(
            "âš ï¸ CaktoBot nÃ£o retornado pela API do Telegram | chat_id=%s | "
            "prosseguindo com a configuraÃ§Ã£o porque assinatura Cakto estÃ¡ ativa e Radar Ã© administrador",
            chat_id
        )

    cliente.update({
        "chat_id": chat_id,
        "grupo_nome": chat_title or "Grupo sem nome",
        "grupo_username": getattr(chat, "username", "") or raw_chat.get("username", "") or "",
        "grupo_configurado": True,
        "grupo_ativo": True,
        "bot_admin": True,
        "cakto_bot_admin": bool(cakto_admin),
        "configurado_em": datetime.now(FUSO_BR).isoformat(),
        "plano": compra.get("plano", cliente.get("plano", "desconhecido")),
        "ativo": True,
    })
    clientes[str(user_id)] = cliente
    salvar_clientes_telegram(clientes)

    await responder(
        "ðŸŽ‰ <b>GRUPO CONFIGURADO COM SUCESSO!</b>\n\n"
        f"ðŸ“¦ Plano: <b>{html.escape(cliente.get('plano', 'desconhecido'))}</b>\n"
        f"ðŸ”— Shopee ID: <b>{html.escape(str(cliente.get('afiliado_id')))}</b>\n"
        f"ðŸ‘¥ Grupo: <b>{html.escape(chat_title or 'Grupo')}</b>\n\n"
        "âœ… Radar administrador\n"
        + ("âœ… CaktoBot administrador\n" if cakto_admin else "â„¹ï¸ CaktoBot nÃ£o retornado pela API do Telegram â€” nÃ£o bloqueia a ativaÃ§Ã£o\n")
        + "ðŸš€ A partir do prÃ³ximo ciclo, as ofertas serÃ£o enviadas automaticamente aqui."
    )
    logging.info("âœ… Grupo configurado | telegram_id=%s | chat_id=%s | grupo=%s", user_id, chat_id, chat_title)
    global LINKS_CICLO_ATUAL, TERMOS_USADOS_CICLO
    LINKS_CICLO_ATUAL.clear()
    TERMOS_USADOS_CICLO.clear()

async def validar_cliente_grupo(bot, cliente):
    if not cliente.get("grupo_configurado") or not cliente.get("chat_id"):
        return False
    email = cliente.get("email_cakto", "")
    compra = encontrar_cakto_por_email(email) if email else None
    if not compra or not compra.get("ativo") or not cliente.get("afiliado_id"):
        return False
    bot_admin, cakto_admin = await localizar_admins_grupo(bot, cliente["chat_id"])
    if not cakto_admin:
        logging.warning(
            "âš ï¸ CaktoBot nÃ£o retornado pela API | chat_id=%s | "
            "cliente continua vÃ¡lido porque assinatura Cakto estÃ¡ ativa e Radar Ã© administrador",
            cliente.get("chat_id")
        )
    # V55: somente a assinatura ativa + Radar administrador sÃ£o obrigatÃ³rios
    # para o envio. O CaktoBot nÃ£o Ã© mais uma trava tÃ©cnica do Radar.
    return bool(bot_admin)

async def enviar_ofertas_clientes(ctx, ofertas):
    clientes = carregar_clientes_telegram()
    prontos = []
    alterados = False
    for chave, cliente in clientes.items():
        if not cliente.get("grupo_configurado") or not cliente.get("chat_id"):
            continue
        if not cliente.get("email_cakto") or not cliente.get("afiliado_id"):
            continue
        ok = await validar_cliente_grupo(ctx.bot, cliente)
        if not ok:
            if cliente.get("grupo_ativo"):
                cliente["grupo_ativo"] = False
                alterados = True
            logging.warning("â¸ï¸ Cliente ignorado | telegram_id=%s | grupo=%s | assinatura/admins nÃ£o vÃ¡lidos", chave, cliente.get("chat_id"))
            continue
        if not cliente.get("grupo_ativo"):
            cliente["grupo_ativo"] = True
            alterados = True
        prontos.append(cliente)
    if alterados:
        salvar_clientes_telegram(clientes)

    if not prontos:
        return

    logging.info("ðŸ‘¥ Clientes ativos para envio: %s", len(prontos))
    for cliente in prontos:
        chat_id = cliente["chat_id"]
        afiliado = cliente["afiliado_id"]
        enviados = 0
        for nicho, p in ofertas:
            try:
                titulo = str(p.get("productName", "")).strip()
                lb = str(p.get("offerLink") or p.get("productLink", "")).strip()
                if not titulo or not lb:
                    continue
                link = anexar_afiliado(lb, afiliado)
                try:
                    preco_str = p.get("priceMin", "0") or "0"
                    preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
                except Exception:
                    preco = 0
                vendas_val = p.get("sales")
                vendas = int(vendas_val) if vendas_val is not None and vendas_val != "" else None
                nota_val = p.get("ratingStar")
                nota = float(nota_val) if nota_val is not None and nota_val != "" else None
                comissao = round(float(p.get("commissionRate", 0) or 0) * 100, 2)
                img = str(p.get("imageUrl", "")).strip()
                prc = f"{preco:.2f}".replace(".", ",")
                vnd = f"{vendas:,}".replace(",", ".") if vendas is not None else "-"
                nt = f"{nota:.1f}".replace(".", ",") if nota is not None else "-"
                txt_whats = mensagem_whatsai(titulo, prc, vnd, nt, comissao, link)
                lk_whats = link_whatsai(txt_whats)
                txt_tg = montar_tg(titulo, prc, vnd, nt, comissao, link, lk_whats, free=False)
                ok = await enviar_msg(ctx, txt_tg, img, chat_id)
                if ok:
                    enviados += 1
                await asyncio.sleep(1)
            except Exception as e:
                logging.error("âŒ Erro envio cliente | chat_id=%s | %s", chat_id, e)
        logging.info("ðŸ“¤ Cliente concluÃ­do | chat_id=%s | ofertas=%s", chat_id, enviados)


ULTIMOS_LINKS = []
ULTIMOS_TITULOS = []
ABERTURAS_USADAS = set()
GATILHOS_USADAS = set()
LINKS_CICLO_ATUAL = set()
TERMOS_USADOS_CICLO = set()

# =========================
# ðŸ›µ PEÃ‡AS E MODELOS
# =========================
PECAS_MOTO = [
    "kit relacao", "estator", "kit cilindro", "painel completo", "guidÃ£o", "regulador de voltagem", "bucha amortecedor",
    "pastilha de freio", "disco de freio", "lonas de freio", "vela iridium", "burrinho de freio", "bomba de combustivel", "bucha pro link",
    "embreagem completa", "disco de embreagem", "cabo de embreagem", "mola de embreagem", "jogo de juntas", "bucha da balanÃ§a", "chave de seta",
    "bateria de moto", "filtro de oleo", "filtro de ar", "vela de ignicao", "corrente comando", "guarniÃ§Ã£o tampa de valvulas", "motor de arranque",
    "retentor", "junta de motor", "pistao e aneis", "cabecote", "burrinho de freio traseiro", "valvula de escape", "chave igniÃ§Ã£o", "escova do arranque",
    "lampada de farol", "seta pisca", "buzina", "tampa lateral", "valvula admissÃ£o", "cdi",
    "pneu dianteiro", "pneu traseiro", "par pneu", "aro de roda", "camara de ar", "caixa direÃ§Ã£o", "caixa de marcha", "tencionador corrente comando",
    "cabo de acelerador", "manete de freio", "manete de embreagem", "pedal de freio", "pedal de marcha", "capa de banco", "guia de valvulas",
    "paralama dianteiro", "paralama traseiro", "bolha de farol", "protetor de motor", "sliders de protecao", "desmultiplicador",
    "punhos de guiador", "espelho retrovisor", "banco assento", "suporte de placa", "pegamao traseiro", "kit rolamentos",
    "amortecedor dianteiro", "amortecedor traseiro", "retentor de bengala", "mola de suspensao"
]

MOTOS = [
    "Titan 150",          "Factor 150",
    "CG 160",             "NXR 160 Bros",
    "CB 250 Twister",     "Fazer 250",
    "XRE 190",            "Crosser 150",
    "Biz 125",            "Biz 110",
    "YBR 150",            "FZ 15",
    "CB 300F Twister",    "XRE 300",
    "Titan 160",          "Start 160",
    "Pulsar N150",        "Dominar 200",
    "Elite 125",          "NMax 160",
    "Lander 250",         "Tenere 250",
    "MT-03",              "CB 500F",
    "Tornado 250",        "CB 300"
]

PRODUTOS_POR_NICHO = {
    # ========== CASA â€” AGORA COMPLETO! ==========
    "Casa": [
        # EletrodomÃ©sticos Grandes
        "geladeira", "refrigerador", "geladeira frost free",
        "fogÃ£o", "fogÃ£o 4 bocas", "fogÃ£o de embutir",
        "mÃ¡quina de lavar", "lava e seca", "secadora de roupas",
        "forno elÃ©trico", "forno de embutir", "micro-ondas",
        "lava louÃ§a", "lava louÃ§as",
        
        # MÃ³veis - Quarto
        "cama de casal", "cama de solteiro", "cama box",
        "guarda-roupa", "guarda roupa", "guarda roupas",
        "cÃ´moda", "criado mudo", "painel quarto",
        
        # MÃ³veis - Sala
        "sofÃ¡", "sofa retrÃ¡til", "mesa de centro",
        "mesa de jantar", "conjunto sala", "rack",
        "estante", "painel para tv", "poltrona",
        
        # MÃ³veis - Cozinha
        "pia de cozinha", "balcÃ£o de cozinha",
        "armÃ¡rio de cozinha", "armÃ¡rio aÃ©reo",
        "armÃ¡rio de pia", "gabiente cozinha",
        
        # EletrodomÃ©sticos Pequenos (mantidos + ampliados)
        "fritadeira sem oleo", "air fryer", "aspirador de pÃ³",
        "liquidificador", "cafeteira", "panela eletrica",
        "ventilador", "batedeira", "panela de pressÃ£o",
        "torradeira", "ferro de passar", "lava e seca",
        "exaustor cozinha", "filtro de Ã¡gua"
    ],
    
    # ========== ELETRÃ”NICOS â€” AGORA COMPLETO! ==========
    "Eletronicos": [
        # Celulares
        "celular", "smartphone", "aparelho celular",
        "iphone", "samsung", "xiaomi", "motorola",
        
        # TV e Ãudio
        "tv", "televisÃ£o", "smart tv", "tv 4k", "tv led",
        "caixa de som", "soundbar", "home theater",
        "aparelho de som", "receptor tv", "antena digital",
        
        # InformÃ¡tica
        "notebook", "computador", "pc gamer", "desktop",
        "monitor", "impressora", "tablet", "ipad",
        "teclado", "mouse", "webcam", "headset",
        
        # Outros EletrÃ´nicos
        "smartwatch", "relogio inteligente",
        "fone ouvido bluetooth", "carregador",
        "cabo usb", "pendrive", "hd externo",
        "cÃ¢mera de seguranÃ§a", "drone", "roteador"
    ],
    
    # ========== BEBÃŠ â€” MANTIDO + AMPLIADO ==========
    "Bebe": [
        "carrinho bebe", "berÃ§o", "berÃ§o montessoriano",
        "brinquedo bebe", "roupa bebe", "cadeirinha bebe",
        "cadeira de alimentaÃ§Ã£o", "bebÃª conforto", "moisÃ©s",
        "trocador bebe", "banheira bebe", "andador bebe"
    ],
    
    # ========== MODA â€” MANTIDO ==========
    "Moda Feminina": ["vestido", "blusa", "calÃ§a", "saia", "tenis feminino", "bolsa", "oculos sol"],
    "Moda Masculina": ["camiseta", "bermuda", "calÃ§a jeans", "tenis masculino", "bone", "cinto"]
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

# =========================
# FUNÃ‡Ã•ES AUXILIARES
# =========================
def normalizar(texto):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", str(texto or "").lower().strip()))

def horario_valido():
    # Pega o horÃ¡rio REAL de BrasÃ­lia, direto do fuso
    agora = datetime.now(FUSO_BR)
    hora = agora.hour
    minuto = agora.minute
    
    # Converte tudo para minutos para comparar mais certo
    total = hora * 60 + minuto
    inicio = 5 * 60 + 30   # 05:30
    fim = 21 * 60 + 30     # 21:30
    
    return inicio <= total <= fim

def sem_acento(texto):
    mapa = str.maketrans("Ã¡Ã Ã¢Ã£Ã©Ã¨ÃªÃ­Ã¯Ã³Ã´ÃµÃ¶ÃºÃ¼Ã§Ã±", "aaaaeeeiioooouucn")
    return texto.translate(mapa)

def tem_palavra_proibida(texto):
    nt = normalizar(texto)
    return any(p in nt for p in PALAVRAS_PROIBIDAS)

def gerar_variacoes_busca(peca, modelo):
    peca_n = sem_acento(peca.lower())
    modelo_n = sem_acento(modelo.lower())
    modelo_junto = re.sub(r'\s+(\d)', r'\1', modelo_n)
    
    variacoes = [
        f"{peca_n} {modelo_n}",
        f"{peca_n} {modelo_junto}",
        f"{modelo_n} {peca_n}",
        f"{modelo_junto} {peca_n}",
    ]
    
    pecas_com_prefixo = {
        "estator": ["magneto", "completo", "bobina", "gerador"],
        "kit relacao": ["transmissao", "coroa e pinhao", "corrente"],
        "pneu": ["dianteiro", "traseiro", "par"],
        "pastilha": ["freio", "dianteira", "traseira"],
        "disco": ["freio", "dianteiro", "traseiro"],
        "embreagem": ["completa", "disco", "kit"],
        "filtro": ["oleo", "ar"],
        "vela": ["ignicao", "iridium"],
        "bateria": ["moto", "selada"],
    }
    
    for palavra_chave, extras in pecas_com_prefixo.items():
        if palavra_chave in peca_n:
            for extra in extras:
                variacoes.extend([
                    f"{extra} {peca_n} {modelo_n}",
                    f"{peca_n} {extra} {modelo_n}",
                ])
            break
    
    vistas = set()
    unicas = []
    for v in variacoes:
        if v not in vistas:
            vistas.add(v)
            unicas.append(v)
    return unicas

GRUPO_SINONIMOS = {
    "smartwatch": {"smartwatch", "relogio inteligente"},
    "airfryer": {"air fryer", "fritadeira sem oleo", "fritadeira eletrica"},
    "fone": {"fone bluetooth", "fone ouvido", "fone sem fio", "fones"},
    "caixa_som": {"caixa de som", "alto falante", "caixa som"},
    "tv": {"smart tv", "televisao", "tv led", "tv 4k", "tv"},
    "notebook": {"notebook", "laptop"},
    "tablet": {"tablet", "ipad"},
    "celular": {"celular", "smartphone", "aparelho celular"},
    "geladeira": {"geladeira", "refrigerador", "geladeira frost free"},
    "fogao": {"fogÃ£o", "fogao", "fogÃ£o de embutir"},
    "cama": {"cama", "cama box", "cama casal", "cama solteiro"},
    "guarda_roupa": {"guarda-roupa", "guarda roupa", "guarda roupas"},
    "mesa": {"mesa", "mesa de jantar", "mesa de centro"},
    "computador": {"computador", "pc", "desktop", "pc gamer"}
}

MAPA_SINONIMOS = {normalizar(t): g for g, ts in GRUPO_SINONIMOS.items() for t in ts}

def termo_ja_usado(termo):
    g = MAPA_SINONIMOS.get(normalizar(termo))
    return bool(g and any(MAPA_SINONIMOS.get(normalizar(t)) == g for t in TERMOS_USADOS_CICLO))

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
        if not os.path.exists(caminho):
            return padrao
        with open(caminho, "r", encoding="utf-8") as arq:
            return json.load(arq)
    except Exception as e:
        logging.error("Erro ler %s: %s", caminho, e)
        return padrao

# =========================
# ðŸ›µ GERENCIAMENTO DE ESTADO
# =========================
def carregar_estado():
    estado = carregar_json(ARQUIVO_ESTADO, {})
    if estado.get("versao_rodizio") != VERSAO_RODIZIO:
        logging.info("ðŸ”„ Atualizando estado para versao %s...", VERSAO_RODIZIO)
        hoje = datetime.now(FUSO_BR).strftime("%Y%m%d")
        estado = {
            "versao_rodizio": VERSAO_RODIZIO,
            "Moto": {
                "data": hoje,
                "indice_peca": 0,
                "modelo_por_peca": {}
            }
        }
        for p in PECAS_MOTO:
            estado["Moto"]["modelo_por_peca"][p] = 0
        for nicho in PRODUTOS_POR_NICHO:
            estado[nicho] = {"indice": 0, "data": hoje}
        logging.info("âœ… Estado atualizado!")
    return estado

def salvar_estado(estado):
    salvar_json(ARQUIVO_ESTADO, estado)

def carregar_historico():
    return carregar_json(ARQUIVO_HISTORICO, {})

def salvar_historico(dados):
    salvar_json(ARQUIVO_HISTORICO, dados)

# =========================
# ðŸ›µ ROTAÃ‡ÃƒO DE MOTO
# =========================
def obter_proximo_modelo(estado, peca, deslocamento=0):
    st = estado["Moto"]
    idx_atual = st["modelo_por_peca"].get(peca, 0)
    idx = (idx_atual + deslocamento) % len(MOTOS)
    if deslocamento == 0:
        st["modelo_por_peca"][peca] = (idx_atual + 1) % len(MOTOS)
    return MOTOS[idx], idx

def proxima_busca_moto(estado):
    st = estado["Moto"]
    idx_peca = st["indice_peca"]
    
    peca1 = PECAS_MOTO[idx_peca % len(PECAS_MOTO)]
    peca2 = PECAS_MOTO[(idx_peca + 1) % len(PECAS_MOTO)]
    
    modelo1, _ = obter_proximo_modelo(estado, peca1, deslocamento=0)
    modelo2, _ = obter_proximo_modelo(estado, peca2, deslocamento=len(MOTOS)//2)
    
    st["indice_peca"] = (idx_peca + 2) % len(PECAS_MOTO)
    
    logging.info("ðŸï¸ Peca 1: [%s] | Modelo: %s", peca1, modelo1)
    logging.info("ðŸï¸ Peca 2: [%s] | Modelo: %s", peca2, modelo2)
    return peca1, modelo1, peca2, modelo2, estado

# =========================
# ðŸ” BUSCA COM VARIAÃ‡Ã•ES
# =========================
def buscar_com_fallback(peca, modelo_inicial, estado, nicho="Moto"):
    st = estado["Moto"]
    idx_inicial = MOTOS.index(modelo_inicial) if modelo_inicial in MOTOS else 0
    
    for deslocamento_modelo in range(len(MOTOS)):
        idx_modelo = (idx_inicial + deslocamento_modelo) % len(MOTOS)
        modelo = MOTOS[idx_modelo]
        
        variacoes = gerar_variacoes_busca(peca, modelo)
        for termo_busca in variacoes:
            logging.info("ðŸ” Tentando: %s", termo_busca)
            resultados, estado = selecionar(nicho, termo_busca, 1, estado, 
                                            moto=True, peca=peca, modelo_moto=modelo)
            if resultados:
                logging.info("âœ… ENCONTRADO com: %s", termo_busca)
                return resultados, estado
        
        logging.info("âš ï¸ Nenhuma variacao funcionou com %s â†’ tentando proximo modelo...", modelo)
    
    logging.warning("âŒ Nenhum resultado para %s em TODOS os modelos e variacoes!", peca)
    return [], estado

# =========================
# DEMAIS FUNÃ‡Ã•ES
# =========================
def proximo_termo(nicho, estado):
    itens = PRODUTOS_POR_NICHO[nicho]
    c = estado[nicho]
    for _ in range(len(itens)):
        t = itens[c["indice"] % len(itens)]
        c["indice"] += 1
        if termo_ja_usado(t):
            logging.info("ðŸ›‘ Pulado: %s", t)
            continue
        TERMOS_USADOS_CICLO.add(t)
        return t, estado
    return itens[c["indice"] % len(itens)], estado

def chave_titulo(titulo):
    ign = {"premium","novo","promocao","promocao","super","original","kit","completo"}
    return " ".join(sorted([p for p in normalizar(titulo).split() if p not in ign and len(p) > 2])[:8])

def tem_bloqueio(texto):
    return any(p in normalizar(texto) for p in ["teste","amostra","nao venda","exposicao"])

def duplicata_forte(titulo):
    ch = chave_titulo(titulo)
    nt = normalizar(titulo)
    return any(ch == chave_titulo(t) or SequenceMatcher(None, nt, normalizar(t)).ratio() >= SIMILARIDADE_MAX for t in ULTIMOS_TITULOS)

def enviado_anteriormente(chave):
    h = carregar_historico()
    if chave in h:
        try:
            return (datetime.now(FUSO_BR) - datetime.fromisoformat(h[chave]).replace(tzinfo=FUSO_BR)) < timedelta(days=HISTORICO_DIAS)
        except:
            pass
    return False

def registrar_envio(chave):
    h = carregar_historico()
    h[chave] = datetime.now(FUSO_BR).isoformat()
    lim = datetime.now(FUSO_BR) - timedelta(days=HISTORICO_DIAS*3)
    salvar_historico({k: v for k, v in h.items() if datetime.fromisoformat(v).replace(tzinfo=FUSO_BR) >= lim})

def identificar_familia(titulo):
    nt = normalizar(titulo)
    for f, ps in FAMILIAS_PRODUTOS.items():
        if any(normalizar(p) in nt for p in ps):
            return f
    return "outros"

# âœ… CORRIGIDO: Tratar dados nulos/vazios da API
def pontuar_produto(p, termo="", modelo_moto=""):
    try:
        vendas_val = p.get("sales")
        vendas = int(vendas_val) if vendas_val is not None and vendas_val != "" else None
        
        nota_val = p.get("ratingStar")
        nota = float(nota_val) if nota_val is not None and nota_val != "" else None
        
        comissao = float(p.get("commissionRate", 0) or 0) * 100
        preco_str = p.get("priceMin", "0") or "0"
        preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
        
        pt = normalizar(termo)
        tp = normalizar(p.get("productName", ""))
        
        pont = 0
        if vendas is not None:
            pont += min(vendas/5, 30)
        if nota is not None:
            pont += nota * 3
        pont += comissao * 2
        
        if 50 <= preco <= 500:
            pont += 8
        if pt:
            pont += 10 if pt in tp else sum(2 for x in pt.split() if x in tp)
        if modelo_moto:
            nm = sem_acento(modelo_moto).lower().replace(" ", "")
            nm_espaco = sem_acento(modelo_moto).lower()
            if nm in tp or nm_espaco in tp:
                pont += 25
                logging.info("âœ¨ PERFEITO: %s + %s â†’ %s", termo, modelo_moto, p.get("productName","")[:50])
        return max(0, pont)
    except:
        return 0

# âœ… CORRIGIDO: SÃ³ rejeitar se valor for explicitamente BAIXO, NÃƒO se vier vazio
def avaliar_rejeicao(p):
    titulo = str(p.get("productName", "")).strip()
    link = str(p.get("offerLink") or p.get("productLink", "")).strip()
    
    try:
        preco_str = p.get("priceMin", "0") or "0"
        preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
    except:
        preco = 0
    try:
        comissao = float(p.get("commissionRate", "0") or "0") * 100
    except:
        comissao = 0
    
    # âœ… Agora sÃ³ rejeita se o valor FORNECIDO for baixo
    vendas_val = p.get("sales")
    vendas = int(vendas_val) if vendas_val is not None and vendas_val != "" else None
    
    nota_val = p.get("ratingStar")
    nota = float(nota_val) if nota_val is not None and nota_val != "" else None
    
    if tem_palavra_proibida(titulo):
        return "PROIBIDO (mousepad)"
    if not titulo:
        return "sem_titulo"
    if not link:
        return "sem_link"
    if tem_bloqueio(titulo):
        return "bloqueado"
    if preco < PRECO_MIN:
        return "preco_baixo"
    if preco > PRECO_MAX:
        return "preco_alto"
    if comissao < COMISSAO_MIN:
        return "comissao_baixa"
    # âœ… SÃ³ exclui se vier valor e for baixo. Se vier vazio â†’ ACEITA!
    if vendas is not None and vendas > 0 and vendas < VENDAS_MIN:
        return "poucas_vendas"
    if nota is not None and nota > 0 and nota < AVALIACAO_MIN:
        return "nota_baixa"
    if link in LINKS_CICLO_ATUAL or link in ULTIMOS_LINKS:
        return "link_repetido"
    return None

def buscar_produtos(termo, nicho):
    termo_busca = sem_acento(termo.strip())
    logging.info("ðŸ” Buscando em %s: %s", nicho, termo_busca)
    ts = int(time.time())
    ordem = random.choice(TIPOS_ORDEM)
    pagina = random.randint(1, MAX_PAGINA_BUSCA)
    logging.info(" â†³ Ordem=%s | Pagina=%s", ordem, pagina)
    q = f'query {{productOfferV2(sortType:{ordem},page:{pagina},limit:50,keyword:{json.dumps(termo_busca,ensure_ascii=False)},isAMSOffer:true){{nodes{{productName,priceMin,priceMax,commissionRate,sales,ratingStar,productLink,offerLink,imageUrl,shopType}}}}}}'
    payload = json.dumps({"query": q}, ensure_ascii=False)
    assinatura = hashlib.sha256(f"{SHOPEE_APP_ID}{ts}{payload}{SHOPEE_PASSWORD}".encode()).hexdigest()
    cab = {"Content-Type": "application/json", "Authorization": f"SHA256 Credential={SHOPEE_APP_ID},Timestamp={ts},Signature={assinatura}", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.post(SHOPEE_GRAPHQL_URL, data=payload.encode("utf-8"), headers=cab, timeout=25)
        r.raise_for_status()
        d = r.json()
        if d.get("errors"):
            logging.error("API Erro: %s", d["errors"])
            return []
        p = (d.get("data", {}).get("productOfferV2", {}).get("nodes") or [])
        logging.info("âœ… %s produtos encontrados", len(p))
        return p
    except Exception as e:
        logging.error("âŒ Falha busca: %s", e)
        return []

def selecionar(nicho, termo, qtd, estado, moto=False, peca=None, modelo_moto=""):
    tcompleto = termo
    res = buscar_produtos(tcompleto, nicho)
    val = []
    motivos = Counter()
    for p in res:
        m = avaliar_rejeicao(p)
        if m:
            motivos[m] += 1
        else:
            val.append(p)
    logging.info("ðŸ“Š %s: %s brutos / %s validos", nicho, len(res), len(val))
    if val:
        com_pont = [(p, pontuar_produto(p, peca if moto else termo, modelo_moto)) for p in val]
        pesos = [max(1, n**1.5) for _, n in com_pont]
        idx = random.choices(range(len(com_pont)), weights=pesos, k=len(com_pont))
        val = [com_pont[i][0] for i in idx]
    esc = []
    familias = Counter()
    for p in val:
        if len(esc) >= qtd:
            break
        titulo = str(p.get("productName", "")).strip()
        link = str(p.get("offerLink") or p.get("productLink", "")).strip()
        ch = chave_titulo(titulo)
        fam = identificar_familia(titulo)
        hid = hashlib.md5(f"{ch}|{link}".encode()).hexdigest()
        if duplicata_forte(titulo):
            continue
        if familias[fam] >= LIMITE_POR_FAMILIA:
            continue
        if enviado_anteriormente(hid):
            continue
        esc.append(p)
        familias[fam] += 1
        LINKS_CICLO_ATUAL.add(link)
        ULTIMOS_LINKS.append(link)
        ULTIMOS_TITULOS.append(titulo)
        registrar_envio(hid)
    del ULTIMOS_LINKS[:-300]
    del ULTIMOS_TITULOS[:-150]
    if motivos:
        logging.info("ðŸ“‹ Excluidos: %s", dict(motivos))
    return esc, estado

# =========================
# ðŸ›µ OFERTAS GARANTIDAS
# =========================
def obter_ofertas_garantidas(estado):
    global LINKS_CICLO_ATUAL, TERMOS_USADOS_CICLO
    LINKS_CICLO_ATUAL.clear()
    TERMOS_USADOS_CICLO.clear()
    sel = []
    lista_nichos = list(PRODUTOS_POR_NICHO.items())
    
    logging.info("ðŸï¸ Iniciando busca de ofertas de moto...")
    peca1, modelo1, peca2, modelo2, estado = proxima_busca_moto(estado)
    
    its1, estado = buscar_com_fallback(peca1, modelo1, estado)
    sel.extend([("Moto", x) for x in its1])
    logging.info("ðŸï¸ Moto 1 (%s): %s selecionados", peca1, len(its1))
    
    its2, estado = buscar_com_fallback(peca2, modelo2, estado)
    sel.extend([("Moto", x) for x in its2])
    logging.info("ðŸï¸ Moto 2 (%s): %s selecionados", peca2, len(its2))
    
    tentativas = 0
    max_tentativas = 50
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
    sel.sort(key=lambda x: pontuar_produto(x[1], x[0]), reverse=True)
    
    if len(sel) >= MIN_OFERTAS:
        sel = sel[:MAX_OFERTAS]
        logging.info("âœ… âœ… GARANTIDO: %s ofertas selecionadas", len(sel))
    else:
        logging.warning("âš ï¸ Apenas %s ofertas apos %s tentativas", len(sel), tentativas)
    return sel

def obter_ofertas_shopee():
    return obter_ofertas_garantidas(carregar_estado())

# =========================
# MENSAGENS E ENVIO
# =========================
ABERTURAS = [
    "ðŸš¨ Isso nao aparece todo dia!", "ðŸ‘€ Olha o que encontreiâ€¦", "ðŸ”¥ Aproveita enquanto da!",
    "ðŸ›‘ Para e olha!", "ðŸ¤¯ Dificil achar barato assim!", "âš ï¸ Pode sumir a qualquer horaâ€¦",
    "ðŸ“‰ Caiu de preco!", "ðŸš€ Ta bombando!"
]
GATILHOS = [
    "Bem abaixo do preco normal", "Avaliacoes excelentes", "Muita gente comprando",
    "Custo-beneficio otimo", "Quem compra recomenda", "Produto confiavel", "Saindo rapido"
]
CHAMADAS = [
    "ðŸ‘‡ Corre antes que acabe!", "âš¡ Clique antes de aumentar!", "ðŸš€ Estoque limitado!",
    "ðŸ’¥ Oportunidade!", "ðŸŽ¯ Compre antes dos outros!", "â° Acaba hoje!",
    "ðŸ’° Economia real!", "ðŸ›’ Nao perca!"
]

def anexar_afiliado(link, afiliado_id=None):
    try:
        u = urlparse(link)
        p = parse_qs(u.query)
        p["af_siteid"] = afiliado_id or AFILIADO_ID
        return urlunparse(u._replace(query=urlencode(p, doseq=True)))
    except:
        return link

def link_whatsai(texto):
    return f"https://wa.me/?text={quote(re.sub(r'<[^>]+>', '', texto))}"

# âœ… CORRIGIDO: Exibir "NÃ£o informado" quando dados nÃ£o vierem
def mensagem_whatsai(nome, preco, vendas, nota, comissao, link):
    vendas_texto = vendas if vendas != "-" else "NÃ£o informado"
    nota_texto = nota if nota != "-" else "NÃ£o informado"
    return (
        f"ðŸ”¥ Produto: *{nome}*\n\n"
        f"ðŸ’° PreÃ§o: *R$ {preco}*\n"
        f"ðŸ“Š Vendas: *{vendas_texto}*\n"
        f"â­ AvaliaÃ§Ã£o: *{nota_texto}*\n\n"
        f"ðŸ›’ Aproveite pelo link:\n{link}"
    )

def montar_tg(nome, preco, vendas, nota, comissao, link, lk_whats, free=False, incluir_link_grupo=False):
    disponiveis_ab = [x for x in ABERTURAS if x not in ABERTURAS_USADAS]
    if not disponiveis_ab:
        ABERTURAS_USADAS.clear()
        disponiveis_ab = ABERTURAS
    ab = random.choice(disponiveis_ab)
    ABERTURAS_USADAS.add(ab)
    
    disponiveis_gt = [x for x in GATILHOS if x not in GATILHOS_USADAS]
    if not disponiveis_gt:
        GATILHOS_USADAS.clear()
        disponiveis_gt = GATILHOS
    gt = random.choice(disponiveis_gt)
    GATILHOS_USADAS.add(gt)
    
    ch = random.choice(CHAMADAS)
    etiqueta = "ðŸŽ OFERTA DESTAQUE DA SEMANA!" if free else ""
    
    vendas_texto = f"ðŸ“Š Vendas: {vendas}" if vendas != "-" else "ðŸ“Š Vendas: NÃ£o informado"
    nota_texto = f"â­ Avaliacao: {nota}" if nota != "-" else "â­ Avaliacao: NÃ£o informado"
    
    partes = []
    if etiqueta:
        partes.append(f"<b>{html.escape(etiqueta)}</b>")
    partes.extend([
        f"{html.escape(ab)}", "",
        f"ðŸ”¥ <b>Produto:</b> {html.escape(nome)}",
        f"ðŸ’° <b>Preco:</b> R$ {preco}",
        vendas_texto,
        nota_texto,
        f"ðŸ’¼ <b>Comissao:</b> {comissao}%", "",
        f"ðŸ’¡ {html.escape(gt)}",
        f"ðŸ‘‰ {html.escape(ch)}", "",
        f'<a href="{html.escape(link)}">ðŸ›’ COMPRAR AGORA</a>\n\n'
        f'<a href="{lk_whats}">ðŸ“² Compartilhar no WhatsApp</a>'
    ])
    if free or incluir_link_grupo:
        partes.append(f'<a href="{html.escape(LINK_GRUPO_OFERTAS)}">ðŸ‘¥ Entrar no grupo de ofertas</a>')
    return "\n".join(partes)

async def enviar_msg(ctx, txt, img, cid):
    if not txt or not txt.strip():
        logging.warning("âš ï¸ Texto vazio â€” nao enviado")
        return False
    try:
        if img and img.strip():
            await ctx.bot.send_photo(cid, photo=img.strip(), caption=txt, parse_mode="HTML")
            logging.info("ðŸ“¸ Foto+texto enviados")
        else:
            await ctx.bot.send_message(cid, text=txt, parse_mode="HTML")
            logging.info("ðŸ“ Apenas texto enviado")
        return True
    except Exception as e:
        logging.warning("âš ï¸ Erro envio: %s", e)
        try:
            await ctx.bot.send_message(cid, text=txt, parse_mode="HTML")
            return True
        except Exception as e2:
            logging.error("âŒ Falha total envio: %s", e2)
            return False


# =========================
# ðŸ”— WEBHOOK CAKTO â€” TESTE
# =========================
CAKTO_WEBHOOK_SECRET = os.getenv("CAKTO_WEBHOOK_SECRET", "").strip()
WEBHOOK_PORT = int(os.getenv("PORT", "8080"))

async def webhook_cakto(reader, writer):
    try:
        request = await asyncio.wait_for(reader.read(1024 * 1024), timeout=10)
        texto = request.decode("utf-8", errors="replace")
        cabecalho, _, corpo = texto.partition("\r\n\r\n")
        if not corpo:
            cabecalho, _, corpo = texto.partition("\n\n")

        linha = cabecalho.splitlines()[0] if cabecalho else ""
        metodo = linha.split(" ")[0] if linha else ""

        if metodo != "POST":
            resposta = "HTTP/1.1 405 Method Not Allowed\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"ok\":false,\"error\":\"method_not_allowed\"}"
            writer.write(resposta.encode())
            await writer.drain()
            return

        try:
            dados = json.loads(corpo)
        except Exception:
            logging.warning("âš ï¸ Webhook Cakto recebeu JSON invalido")
            resposta = "HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nConnection: close\r\n\r\n{\"ok\":false,\"error\":\"invalid_json\"}"
            writer.write(resposta.encode())
            await writer.drain()
            return

        # Nunca gravamos CPF, cartao ou outros dados sensiveis no log.
        evento = dados.get("event")
        itens = dados.get("data") or []
        if isinstance(itens, dict):
            itens = [itens]

        logging.info("ðŸ“© Cakto recebido | evento=%s | itens=%s", evento, len(itens))
        clientes_cakto = carregar_clientes_cakto()
        for item in itens:
            cliente = item.get("customer") or {}
            produto = item.get("product") or {}
            oferta = item.get("offer") or {}
            email = email_normalizado(cliente.get("email", ""))
            oferta_nome = oferta.get("name", "")
            oferta_preco = oferta.get("price", item.get("price", ""))
            periodo = item.get("subscription_period", "") or (item.get("subscription") or {}).get("recurrence_period", "")
            status = item.get("status", "")
            ativo = status_ativo_cakto(evento, status)
            if email and item.get("offer_type", "main") == "main":
                registro = clientes_cakto.get(email, {})
                registro.update({
                    "email": email,
                    "nome": cliente.get("name", ""),
                    "telefone": cliente.get("phone", ""),
                    "produto": produto.get("name", ""),
                    "produto_id": produto.get("id", ""),
                    "oferta": oferta_nome,
                    "oferta_id": oferta.get("id", ""),
                    "oferta_preco": oferta_preco,
                    "plano": classificar_plano(oferta_nome, oferta_preco, periodo),
                    "status": status,
                    "evento": evento,
                    "offer_type": item.get("offer_type", "main"),
                    "subscription": item.get("subscription"),
                    "subscription_period": item.get("subscription_period", ""),
                    "atualizado_em": datetime.now(FUSO_BR).isoformat()
                })
                if ativo is not None:
                    registro["ativo"] = ativo
                else:
                    registro["ativo"] = registro.get("ativo", False)
                clientes_cakto[email] = registro

            logging.info(
                "ðŸ§¾ Cakto | email=%s | produto=%s | oferta=%s | status=%s | ativo=%s",
                email, produto.get("name", ""), oferta_nome, status, ativo
            )
        salvar_clientes_cakto(clientes_cakto)

        resposta_body = json.dumps({"ok": True, "received": True}, ensure_ascii=False)
        resposta = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json; charset=utf-8\r\n"
            "Connection: close\r\n"
            f"Content-Length: {len(resposta_body.encode('utf-8'))}\r\n\r\n"
            f"{resposta_body}"
        )
        writer.write(resposta.encode("utf-8"))
        await writer.drain()
    except Exception as e:
        logging.error("âŒ Erro webhook Cakto: %s", e, exc_info=True)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass

async def iniciar_webhook():
    servidor = await asyncio.start_server(webhook_cakto, "0.0.0.0", WEBHOOK_PORT)
    enderecos = ", ".join(str(s.getsockname()) for s in (servidor.sockets or []))
    logging.info("ðŸŒ Webhook Cakto ativo na porta %s | %s", WEBHOOK_PORT, enderecos)
    async with servidor:
        await servidor.serve_forever()

# =========================
# ðŸŽ CICLO PRINCIPAL
# =========================
async def ciclo(ctx):
    try:
        logging.info("========== ðŸ”„ INICIO ==========")
        if not horario_valido():
            logging.info("â¹ï¸ Fora do horario")
            return
        
        ABERTURAS_USADAS.clear()
        GATILHOS_USADAS.clear()
        
        ofertas = obter_ofertas_shopee()
        if len(ofertas) < MIN_OFERTAS:
            logging.warning("âš ï¸ Apenas %s ofertas validas. Minimo de %s exigido. Ciclo pulado.", len(ofertas), MIN_OFERTAS)
            return
        
        logging.info("âœ… Total: %s | Enviando %s para VIP", len(ofertas), len(ofertas))
        
        ofertas_vip = ofertas.copy()
        
        idx_free = random.randint(0, len(ofertas)-1)
        oferta_free = ofertas[idx_free]
        nicho_free, produto_free = oferta_free
        logging.info("ðŸŽ Sorteado para FREE: %s | %s", produto_free.get("productName","")[:50], nicho_free)
        
        await ctx.bot.send_message(CHAT_ID_DESTINO, text="ðŸš¨ <b>OFERTAS NOVAS CHEGARAM!</b>", parse_mode="HTML")
        await asyncio.sleep(5)
        
        enviados = []
        for nicho, p in ofertas_vip:
            try:
                titulo = str(p.get("productName", "")).strip()
                lb = str(p.get("offerLink") or p.get("productLink", "")).strip()
                if not titulo or not lb:
                    continue
                link = anexar_afiliado(lb)
                try:
                    preco_str = p.get("priceMin", "0") or "0"
                    preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
                except:
                    preco = 0
                
                # âœ… Tratar valores nulos da API
                vendas_val = p.get("sales")
                vendas = int(vendas_val) if vendas_val is not None and vendas_val != "" else None
                
                nota_val = p.get("ratingStar")
                nota = float(nota_val) if nota_val is not None and nota_val != "" else None
                
                comissao = round(float(p.get("commissionRate", 0) or 0) * 100, 2)
                img = str(p.get("imageUrl", "")).strip()
                prc = f"{preco:.2f}".replace(".", ",")
                
                # âœ… Formatar para exibiÃ§Ã£o
                vnd = f"{vendas:,}".replace(",", ".") if vendas is not None else "-"
                nt = f"{nota:.1f}".replace(".", ",") if nota is not None else "-"
                
                txt_whats = mensagem_whatsai(titulo, prc, vnd, nt, comissao, link)
                lk_whats = link_whatsai(txt_whats)
                txt_tg = montar_tg(titulo, prc, vnd, nt, comissao, link, lk_whats, free=False, incluir_link_grupo=True)
                hid = hashlib.md5(f"{chave_titulo(titulo)}|{lb}".encode()).hexdigest()
                enviados.append({"txt": txt_tg, "img": img, "hid": hid, "nicho": nicho})
            except Exception as e:
                logging.error("âŒ Montagem: %s", e)
        
        if len(enviados) < MIN_OFERTAS:
            return
        
        for item in enviados:
            logging.info("ðŸ“¤ Enviando VIP: %s", item["nicho"])
            ok = await enviar_msg(ctx, item["txt"], item["img"], CHAT_ID_DESTINO)
            if ok:
                registrar_envio(item["hid"])
            await asyncio.sleep(40)

        # Envia as mesmas ofertas aos grupos dos clientes ativos, usando o ID de afiliado de cada cliente.
        try:
            await enviar_ofertas_clientes(ctx, ofertas_vip)
        except Exception as e:
            logging.error("âŒ Erro geral no envio para clientes: %s", e, exc_info=True)
        
        logging.info("ðŸŽ Enviando oferta destaque para grupo FREE")
        try:
            titulo = str(produto_free.get("productName", "")).strip()
            lb = str(produto_free.get("offerLink") or produto_free.get("productLink", "")).strip()
            link = anexar_afiliado(lb)
            try:
                preco_str = produto_free.get("priceMin", "0") or "0"
                preco = float(preco_str) / 1000 if isinstance(preco_str, (int, float)) else float(preco_str or "0")
            except:
                preco = 0
            
            vendas_val = produto_free.get("sales")
            vendas = int(vendas_val) if vendas_val is not None and vendas_val != "" else None
            
            nota_val = produto_free.get("ratingStar")
            nota = float(nota_val) if nota_val is not None and nota_val != "" else None
            
            comissao = round(float(produto_free.get("commissionRate", 0) or 0) * 100, 2)
            img = str(produto_free.get("imageUrl", "")).strip()
            prc = f"{preco:.2f}".replace(".", ",")
            vnd = f"{vendas:,}".replace(",", ".") if vendas is not None else "-"
            nt = f"{nota:.1f}".replace(".", ",") if nota is not None else "-"
            
            txt_whats = mensagem_whatsai(titulo, prc, vnd, nt, comissao, link)
            lk_whats = link_whatsai(txt_whats)
            txt_tg = montar_tg(titulo, prc, vnd, nt, comissao, link, lk_whats, free=True)
            hid = hashlib.md5(f"{chave_titulo(titulo)}|{lb}".encode()).hexdigest()
            ok = await enviar_msg(ctx, txt_tg, img, CHAT_ID_FREE)
            if ok:
                registrar_envio(hid)
                logging.info("âœ… Oferta FREE enviada!")
        except Exception as e:
            logging.error("âŒ Erro envio FREE: %s", e, exc_info=True)
        
        logging.info("========== âœ… CONCLUIDO ==========")
    except Exception as e:
        logging.error("âŒ ERRO: %s", e, exc_info=True)

async def loop(app):
    ult = 0
    while True:
        agora = time.time()
        if agora - ult >= CHECK_INTERVAL:
            logging.info("ðŸ”„ Iniciando ciclo de buscas...")
            await ciclo(type("Ctx", (), {"bot": app.bot})())
            ult = agora
        await asyncio.sleep(60)

async def manter_vivo():
    while True:
        logging.info("ðŸ’“ Ativo | %s", datetime.now(FUSO_BR).strftime("%d/%m as %H:%M"))
        await asyncio.sleep(300)

async def erro_telegram(update, context):
    erro = getattr(context, "error", None)
    logging.error("âŒ Erro no processamento Telegram | tipo_update=%s | erro=%s", type(update).__name__, erro, exc_info=erro)


async def principal():
    logging.info("ðŸ¤– Iniciando bot...")
    if not TELEGRAM_TOKEN or not SHOPEE_PASSWORD:
        raise RuntimeError("Configure TELEGRAM_TOKEN e SHOPEE_PASSWORD")
    inicializar_banco_persistente()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(CommandHandler("configurar", comando_configurar))

    # Fallback explÃ­cito: mensagens normais, grupos e CHANNEL_POSTS.
    # Em canais, o Telegram entrega o post como update.channel_post.
    app.add_handler(
        MessageHandler(
            filters.Regex(r"^/configurar(?:@[A-Za-z0-9_]+)?(?:\s.*)?$"),
            comando_configurar
        )
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receber_dados_onboarding))
    app.add_error_handler(erro_telegram)
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    logging.info("âœ… Bot pronto e recebendo comandos Telegram!")
    asyncio.create_task(manter_vivo())
    asyncio.create_task(iniciar_webhook())
    try:
        await loop(app)
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

def iniciar():
    try:
        asyncio.run(principal())
    except Exception as e:
        logging.error("ðŸ”„ Reiniciando em 15s: %s", e)
        time.sleep(15)
        iniciar()

if __name__ == "__main__":
    iniciar()
            
        
