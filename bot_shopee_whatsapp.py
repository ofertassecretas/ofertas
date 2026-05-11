import requests
from bs4 import BeautifulSoup
import random
import time
import logging
import re
from telegram import Bot
from telegram.ext import Updater
from urllib.parse import quote

# =========================
# CONFIGURAÇÕES
# =========================
TOKEN_TELEGRAM = "7591538191:AAFQcrOaRvF4_9yh3P1IHtM7x3IRQZi2wNE"
SEU_ID_AFILIADO = "589508454"  # SEU ID CORRETO

# =========================
# CONFIGURAÇÃO DE LOG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S'
)
logging.info("🤖 BOT MAGALU RODANDO")
logging.info("Loop iniciado")

# =========================
# FUNÇÃO BUSCAR PRODUTOS MAGALU - VERSÃO BLINDADA
# =========================
def get_magalu_offers():
    logging.info("Buscando ofertas MAGALU")

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

    # ✅ SESSÃO + CABEÇALHOS COMPLETOS PARA SIMULAR NAVEGADOR REAL
    sessao = requests.Session()
    sessao.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,es;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com.br/",
        "Sec-Ch-Ua": '"Not.A/Brand";v="8", "Chromium";v="114", "Google Chrome";v="114"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "cross-site",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    })

    try:
        # ✅ ROTA CORRETA E CODIFICADA
        url_busca = f"https://www.magazineluiza.com.br/busca/{quote(termo)}/?order=price_asc"
        
        # Delay para parecer humano
        time.sleep(random.uniform(1.5, 3))

        # Primeiro acessa a página inicial para pegar cookies válidos
        sessao.get("https://www.magazineluiza.com.br/", timeout=30)
        time.sleep(1)

        # Agora sim busca os produtos com sessão pronta
        resposta = sessao.get(url_busca, timeout=30)
        logging.info(f"Status Magalu: {resposta.status_code}")

        if resposta.status_code != 200:
            logging.error("Página indisponível ou bloqueada")
            return []

        soup = BeautifulSoup(resposta.text, "html.parser")
        produtos = []

        # ✅ TODOS OS SELETORES ATUAIS DA MAGALU
        seletores = [
            "div[data-testid='product-card']",
            "li.sc-kdBSHD",
            "div.sc-epAScI",
            "div.product-card",
            "li.product",
            "div[class*='ProductCard']"
        ]

        cards = []
        for sel in seletores:
            cards = soup.select(sel)
            if cards:
                logging.info(f"✅ Estrutura encontrada: {sel} | {len(cards)} itens")
                break

        if not cards:
            logging.warning("Nenhum produto encontrado na página")
            return []

        # ✅ EXTRAÇÃO DOS DADOS
        for idx, card in enumerate(cards[:5]):
            try:
                # Nome
                nome = card.select_one("h2") or card.select_one("h3") or card.select_one("div[title]")
                if not nome: continue
                nome_texto = nome.get_text(strip=True)
                if len(nome_texto) < 5: continue

                # Preço
                preco = card.select_one("p[data-testid='price-value']") or \
                        card.select_one("span[class*='price']") or \
                        card.find(string=re.compile(r'R\$'))
                if not preco: continue
                preco_texto = preco.get_text(strip=True) if hasattr(preco, 'get_text') else str(preco).strip()

                # Link Base
                link_tag = card.select_one("a[href]")
                if not link_tag: continue
                link_base = link_tag["href"]
                if link_base.startswith("/"):
                    link_base = "https://www.magazineluiza.com.br" + link_base

                # ✅ LINK DE AFILIADO SEU (FORMATO CORRETO)
                link_seu = f"https://magazineluiza.onelink.me/{SEU_ID_AFILIADO}?af_dp={quote(link_base)}"

                # Imagem
                img_tag = card.select_one("img[src]")
                if not img_tag: continue
                img_url = img_tag.get("src") or img_tag.get("data-src") or ""
                if img_url.startswith("data:image"): continue

                produtos.append({
                    "nome": nome_texto,
                    "preco": preco_texto,
                    "link": link_seu,
                    "img": img_url,
                    "loja": "Magazine Luiza ✅",
                    "avaliacao": round(random.uniform(4.3, 5.0),1)
                })
                logging.info(f"📦 Produto {idx+1}: {nome_texto} | {preco_texto}")

            except Exception as e:
                logging.warning(f"⚠️ Erro ao processar item {idx+1}: {e}")

        logging.info(f"🏁 Final: {len(produtos)} produtos prontos")
        return produtos

    except Exception as e:
        logging.error(f"💥 ERRO GERAL: {e}")
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
            bot.send_photo(
                chat_id="@promodasofertas",
                photo=p['img'],
                caption=mensagem,
                parse_mode="Markdown"
            )
            logging.info("📤 Enviado com sucesso")
            time.sleep(2)
        except Exception as e:
            logging.error(f"Erro ao enviar: {e}")
            # Se der erro na foto, tenta só texto
            try:
                bot.send_message(chat_id="@promodasofertas", text=mensagem, parse_mode="Markdown")
            except:
                pass

# =========================
# LOOP PRINCIPAL
# =========================
if __name__ == "__main__":
    while True:
        ofertas = get_magalu_offers()
        enviar_ofertas(ofertas)
        logging.info("⏳ Aguardando próxima busca...")
        time.sleep(1800)  # 30 MINUTOS
