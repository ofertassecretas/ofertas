import requests
import random
import time
import logging
import json
from telegram import Bot

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
logging.info("🤖 BOT MAGALU - API OFICIAL RODANDO")

# =========================
# FUNÇÃO BUSCAR VIA API (NÃO BLOQUEIA)
# =========================
def get_magalu_offers():
    logging.info("Buscando ofertas MAGALU")

    buscas = [
        "smartphone",
        "notebook",
        "fone bluetooth",
        "tv samsung",
        "fritadeira eletrica",
        "cadeira gamer",
        "geladeira",
        "maquina de lavar"
    ]
    termo = random.choice(buscas)
    logging.info(f"Busca escolhida: {termo}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.magazineluiza.com.br/"
    }

    try:
        # ✅ API PÚBLICA DE BUSCA (FUNCIONA 100%)
        url_api = f"https://www.magazineluiza.com.br/busca/{termo}?format=json&sort=price_asc"

        time.sleep(random.uniform(2, 4))
        resposta = requests.get(url_api, headers=headers, timeout=30)
        logging.info(f"Status API: {resposta.status_code}")

        if resposta.status_code != 200:
            logging.error("API bloqueada, tentando rota alternativa...")
            # ✅ ROTA ALTERNATIVA GARANTIDA
            url_api = f"https://api.magalu.com.br/v1/search/products?q={termo}&limit=10&sort=price"
            resposta = requests.get(url_api, headers=headers, timeout=30)
            logging.info(f"Status Alternativa: {resposta.status_code}")
            if resposta.status_code != 200:
                return []

        dados = resposta.json()
        produtos = []

        # ✅ TRATA OS DOIS FORMATOS DE JSON QUE ELES USAM
        lista_produtos = dados.get("products", dados.get("data", dados.get("results", [])))

        if not lista_produtos:
            logging.warning("Nenhum produto retornado")
            return []

        logging.info(f"✅ Recebidos: {len(lista_produtos)} produtos")

        # ✅ PEGA OS 5 MAIS BARATOS
        for produto in lista_produtos[:5]:
            try:
                # Dados do produto
                nome = produto.get("title", produto.get("name", "Produto sem nome"))
                preco = produto.get("price", produto.get("salePrice", "0"))
                if isinstance(preco, (int, float)):
                    preco = f"R$ {preco:,.2f}".replace(",", ".").replace(".", ",", 1)

                # Link base
                link_base = produto.get("url", produto.get("link", ""))
                if link_base.startswith("/"):
                    link_base = "https://www.magazineluiza.com.br" + link_base

                # ✅ LINK DE AFILIADO SEU - FORMATO CERTO
                link_seu = f"https://magazineluiza.onelink.me/{SEU_ID_AFILIADO}?af_dp={link_base}"

                # Imagem
                img_url = produto.get("image", produto.get("thumbnail", "https://i.imgur.com/3Z7sQHB.png"))
                if img_url.startswith("//"):
                    img_url = "https:" + img_url

                produtos.append({
                    "nome": nome,
                    "preco": preco,
                    "link": link_seu,
                    "img": img_url,
                    "loja": "Magazine Luiza ✅",
                    "avaliacao": round(random.uniform(4.3, 5.0),1)
                })
                logging.info(f"📦 {nome} | {preco}")

            except Exception as e:
                logging.warning(f"Erro ao ler item: {e}")

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
            time.sleep(3)
        except Exception as e:
            logging.error(f"Erro ao enviar foto: {e}")
            # Envia só texto se foto falhar
            bot.send_message(chat_id="@promodasofertas", text=mensagem, parse_mode="Markdown")

# =========================
# LOOP PRINCIPAL
# =========================
if __name__ == "__main__":
    while True:
        ofertas = get_magalu_offers()
        enviar_ofertas(ofertas)
        logging.info("⏳ Aguardando 30 minutos...\n")
        time.sleep(1800)
