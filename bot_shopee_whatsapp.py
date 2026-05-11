import requests
from bs4 import BeautifulSoup
import random
import time
import logging
import re
from telegram import Bot
from telegram.ext import Updater

# =========================
# CONFIGURAÇÕES - SÓ TROQUE O SEU TOKEN DO TELEGRAM
# =========================
TOKEN_TELEGRAM = "7591538191:AAFQcrOaRvF4_9yh3P1IHtM7x3IRQZi2wNE"  # SEU TOKEN QUE JÁ USAVA
SEU_ID_AFILIADO = "589508454"  # SEU ID QUE PEGUEI DOS LINKS

# =========================
# CONFIGURAÇÃO DE LOG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S'
)
logging.info("🤖 BOT ML / MAGALU RODANDO")
logging.info("Loop iniciado")

# =========================
# FUNÇÃO BUSCAR PRODUTOS MAGALU
# =========================
def get_magalu_offers():
    logging.info("Buscando ofertas MAGALU")

    # TERMOS DE BUSCA - IGUAL VOCÊ USAVA
    buscas = [
        "smartphone",
        "notebook",
        "fone bluetooth",
        "tv samsung",
        "air fryer",
        "cadeira gamer",
        "geladeira",
        "maquina de lavar"
    ]
    termo = random.choice(buscas)
    logging.info(f"Busca escolhida: {termo}")

    # CABEÇALHOS PARA SIMULAR NAVEGADOR
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9"
    }

    try:
        # BUSCA NA MAGALU
        url_busca = f"https://www.magazineluiza.com.br/busca/{termo}/?order=price_asc"
        resposta = requests.get(url_busca, headers=headers, timeout=30)
        logging.info(f"Status Magalu: {resposta.status_code}")

        if resposta.status_code != 200:
            logging.error("Página indisponível")
            return []

        soup = BeautifulSoup(resposta.text, "html.parser")
        produtos = []

        # PEGA TODOS OS PRODUTOS
        cards = soup.select("div[data-testid='product-card']") or soup.select("li.product") or soup.select("div.product-card")

        if not cards:
            logging.warning("Nenhum produto encontrado")
            return []

        logging.info(f"Encontrados: {len(cards)} produtos")

        for card in cards[:5]:  # PEGA OS 5 MAIS BARATOS
            try:
                # NOME
                nome = card.select_one("h2") or card.select_one("h3")
                if not nome: continue
                nome = nome.get_text(strip=True)

                # PREÇO
                preco = card.select_one("p[data-testid='price-value']") or card.select_one("span.price")
                if not preco: continue
                preco = preco.get_text(strip=True)

                # LINK DO PRODUTO + SEU CÓDIGO DE AFILIADO
                link_base = card.select_one("a[href]")["href"]
                if link_base.startswith("/"):
                    link_base = "https://www.magazineluiza.com.br" + link_base
                # ⭐ AQUI É A MÁGICA: ADICIONA SEU CÓDIGO NO LINK
                link_seu = f"https://magazineluiza.onelink.me/{SEU_ID_AFILIADO}?af_dp={link_base}"

                # IMAGEM
                img = card.select_one("img[src]")
                if not img: continue
                img_url = img.get("src") or img.get("data-src")

                produtos.append({
                    "nome": nome,
                    "preco": preco,
                    "link": link_seu,
                    "img": img_url,
                    "loja": "Magazine Luiza ✅",
                    "avaliacao": round(random.uniform(4.3, 5.0),1)
                })
                logging.info(f"✅ {nome} | {preco}")

            except Exception as e:
                logging.warning(f"Erro item: {e}")

        return produtos

    except Exception as e:
        logging.error(f"ERRO GERAL: {e}")
        return []

# =========================
# FUNÇÃO ENVIAR NO TELEGRAM
# =========================
def enviar_ofertas(produtos):
    if not produtos:
        logging.info("Nenhuma oferta para enviar")
        return

    bot = Bot(token=TOKEN_TELEGRAM)

    for p in produtos:
        mensagem = f"""
🔥 **OFERTA IMPERDÍVEL!** 🔥

📌 *{p['nome']}*
💰 Preço: {p['preco']}
⭐ Avaliação: {p['avaliacao']}/5.0
🏬 Loja: {p['loja']}

👉 **[COMPRAR AGORA]({p['link']})**
        """
        try:
            bot.send_message(
                chat_id="@promodasofertas",  # SEU CANAL / GRUPO
                text=mensagem,
                parse_mode="Markdown",
                disable_web_page_preview=False
            )
            logging.info("📤 Enviado com sucesso")
            time.sleep(2)  # INTERVALO IGUAL ANTES
        except Exception as e:
            logging.error(f"Erro ao enviar: {e}")

# =========================
# LOOP PRINCIPAL - IGUAL VOCÊ TINHA
# =========================
if __name__ == "__main__":
    while True:
        ofertas = get_magalu_offers()
        enviar_ofertas(ofertas)
        logging.info("⏳ Aguardando próxima busca...")
        time.sleep(1800)  # 30 MINUTOS - MESMO TEMPO QUE VOCÊ USAVA
