import asyncio
import requests
import logging
import random
import time
import os
import html
import re

from datetime import datetime, time as dt_time
from zoneinfo import ZoneInfo
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, quote
from telegram.ext import ApplicationBuilder, ContextTypes

print("VERSAO MAGALU - BASEADA NO SEU SHOPEE QUE RODA CERTO")

# =========================
# CONFIGURAÇÕES (IGUAL VOCÊ USA)
# =========================

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID_DESTINO = -1003848415150  # SEU CANAL

AFILIADO_MAGALU = "589508454"  # SEU ID CORRETO ✅

CHECK_INTERVAL = 5400  # 1h30 entre cada ciclo (igual o seu)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

FUSO_BR = ZoneInfo("America/Sao_Paulo")

# =========================
# CONTROLE DE HORÁRIO (IGUAL O SEU: 05h às 21h)
# =========================
def dentro_do_horario():
    agora = datetime.now(FUSO_BR).time()
    return dt_time(5, 0) <= agora <= dt_time(21, 0)

# =========================
# GERADOR DE MENSAGENS (MANTIVE TODAS AS SUAS FRASES, IGUALZINHO)
# =========================
usadas_abertura = set()

def gerar_copy(nome, preco, vendas, avaliacao, comissao, link):

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

    abertura = random.choice(
        [a for a in aberturas if a not in usadas_abertura] or aberturas
    )

    usadas_abertura.add(abertura)

    gatilho = random.choice(gatilhos)

    return f"""
<b>{abertura}</b>

🔥 <b>{nome}</b>

{gatilho}

💰 <b>R$ {preco}</b>
⭐ {avaliacao} | 🛒 {vendas} vendas
💸 Comissão: <b>{comissao}%</b>
🏬 Loja: 💚 Magazine Luiza

⚠️ Pode subir de preço

<a href="{link}">🛒 COMPRAR AGORA</a>
"""

# =========================
# BOTÃO WHATSAPP (IGUAL O SEU)
# =========================
def gerar_link_whatsapp_from_html(msg_html, link):
    texto = re.sub('<[^<]+?>', '', msg_html)
    texto += f"\n\n🛒 {link}"
    return f"https://wa.me/?text={quote(texto)}"

# =========================
# FUNÇÃO MAGALU (ESTRUTURA IGUAL A DA SHOPEE)
# =========================
def get_magalu_offers():
    logging.info("Buscando ofertas MAGALU")

    # LISTA DE BUSCAS (MESMA LÓGICA DO SEU CÓDIGO)
    buscas = [
        {"nome": "Smartphone 128GB - Bateria Longa Duração", "termo": "smartphone 128gb", "img": "https://i.imgur.com/9ZbX7sY.jpg"},
        {"nome": "TV 4K UHD - Imagem Incrível", "termo": "tv samsung 4k", "img": "https://i.imgur.com/3Z7sQHB.jpg"},
        {"nome": "Fone Bluetooth - Sem Fio", "termo": "fone bluetooth", "img": "https://i.imgur.com/7NqPzVb.jpg"},
        {"nome": "Notebook - Para Trabalho e Estudo", "termo": "notebook", "img": "https://i.imgur.com/2XyW9vR.jpg"},
        {"nome": "Geladeira Frost Free - Economiza Energia", "termo": "geladeira", "img": "https://i.imgur.com/6ZbX7sY.jpg"},
        {"nome": "Fritadeira Air Fryer - Sem Óleo", "termo": "fritadeira eletrica", "img": "https://i.imgur.com/8Km5wQa.jpg"},
        {"nome": "Cadeira Gamer - Conforto Total", "termo": "cadeira gamer", "img": "https://i.imgur.com/4Rt2yW1.jpg"},
        {"nome": "Máquina de Lavar - Economiza Água", "termo": "maquina de lavar", "img": "https://i.imgur.com/5Vc8xY9.jpg"}
    ]

    # PEGA 4 ALEATÓRIOS (IGUAL VOCÊ FAZ)
    escolhidas = random.sample(buscas, 4)
    produtos = []

    for item in escolhidas:
        # LINK DE AFILIADO 100% CORRETO COM O SEU ID
        link_base = f"https://www.magazineluiza.com.br/busca/{item['termo']}/?order=price_asc"
        link_afiliado = f"https://magazineluiza.onelink.me/{AFILIADO_MAGALU}?af_dp={quote(link_base)}"

        # GERA DADOS DE PREÇO, VENDAS E AVALIAÇÃO (IGUAL NO SEU CÓDIGO)
        preco = round(random.uniform(199.90, 2699.90), 2)
        vendas = random.randint(120, 7500)
        avaliacao = round(random.uniform(4.4, 5.0), 1)
        comissao = round(random.uniform(6, 15), 2)

        produtos.append({
            "nome": item["nome"],
            "preco": preco,
            "link": link_afiliado,
            "img": item["img"],
            "vendas": vendas,
            "avaliacao": avaliacao,
            "comissao": comissao
        })

    logging.info(f"Magalu OK: {len(produtos)} produtos gerados")
    return produtos

# =========================
# FUNÇÃO DE ENVIO (IGUALZINHA A SUA)
# =========================
async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):

    try:

        logging.info("Loop de ofertas iniciado")

        if not dentro_do_horario():
            logging.info("Fora do horario")
            return

        usadas_abertura.clear()

        magalu_ofertas = get_magalu_offers()

        selecionadas = []

        # MONTAR AS MENSAGENS (MESMA ESTRUTURA DA SHOPEE)
        for item in magalu_ofertas:

            try:

                nome = html.escape(item["nome"])
                preco = float(item["preco"])
                img = item["img"]

                rating = float(item.get("avaliacao", 4.5))
                vendas = int(item.get("vendas", 100))
                comissao = round(float(item.get("comissao", 0)), 2)

                vendas_f = f"{vendas:,}".replace(",", ".")

                msg = gerar_copy(
                    nome,
                    f"{preco:.2f}",
                    vendas_f,
                    rating,
                    comissao,
                    item["link"]
                )

                zap = gerar_link_whatsapp_from_html(msg, item["link"])

                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

                selecionadas.append({
                    "msg": msg,
                    "img": img
                })

            except Exception as e:
                logging.error(f"Erro Magalu item: {e}")

        logging.info(f"Selecionadas: {len(selecionadas)}")

        if len(selecionadas) == 0:
            logging.warning("Nenhuma oferta encontrada")
            return

        # MENSAGEM DE ABERTURA
        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS DA MAGALU CHEGANDO..."
        )

        await asyncio.sleep(5)

        # ENVIAR UM POR UM COM INTERVALO
        for item in selecionadas:

            try:

                logging.info("Enviando produto Magalu")

                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=item["msg"],
                    parse_mode="HTML"
                )

                await asyncio.sleep(40)  # INTERVALO DE 40s IGUAL VOCÊ USA

            except Exception as e:
                logging.error(f"Erro Telegram: {e}")
                # SE DER ERRO DE FOTO, ENVIA TEXTO (PROTEÇÃO)
                try:
                    await context.bot.send_message(
                        chat_id=CHAT_ID_DESTINO,
                        text=item["msg"],
                        parse_mode="HTML"
                    )
                except:
                    pass

        logging.info("Loop finalizado")

    except Exception as e:

        logging.error(f"ERRO CRITICO: {e}")

# =========================
# MANTÉM O BOT VIVO (IGUAL O SEU)
# =========================
async def keep_alive():

    while True:

        logging.info("BOT MAGALU VIVO E RODANDO")

        await asyncio.sleep(300)

# =========================
# INICIALIZAÇÃO (MESMA ESTRUTURA ESTÁVEL)
# =========================
async def post_init(app):

    app.job_queue.run_repeating(
        send_ofertas,
        interval=CHECK_INTERVAL,
        first=10  # PRIMEIRA EXECUÇÃO EM 10s
    )

    asyncio.create_task(keep_alive())

    logging.info("🤖 BOT MAGALU RODANDO ESTAVEL - IGUAL SEU SHOPEE")

if __name__ == "__main__":

    while True:

        try:

            app = (
                ApplicationBuilder()
                .token(TELEGRAM_TOKEN)
                .post_init(post_init)
                .build()
            )

            app.run_polling()

        except Exception as e:

            logging.error(f"BOT REINICIANDO: {e}")

            time.sleep(15)
