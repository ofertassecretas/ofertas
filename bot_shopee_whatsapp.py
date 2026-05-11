import random
import time
import logging
import asyncio
from telegram import Bot
from urllib.parse import quote

# =========================
# CONFIGURAÇÕES
# =========================
TOKEN_TELEGRAM = "7591538191:AAFQcrOaRvF4_9yh3P1IHtM7x3IRQZi2wNE"
SEU_ID_AFILIADO = "589508454"  # SEU ID CORRETO
CANAL = "@promodasofertas"  # SEU CANAL

# =========================
# CONFIGURAÇÃO DE LOG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S'
)
logging.info("🤖 BOT MAGALU - CORRIGIDO E FUNCIONAL")

# =========================
# LISTA DE OFERTAS PRONTAS
# =========================
def get_magalu_offers():
    logging.info("Gerando ofertas MAGALU")

    produtos = [
        {
            "nome": "📱 SMARTPHONE - MELHORES PREÇOS",
            "termo_busca": "smartphone",
            "img": "https://i.imgur.com/9ZbX7sY.jpg",
            "destaque": "Até 40% OFF + Frete Grátis"
        },
        {
            "nome": "💻 NOTEBOOK - OFERTAS IMPERDÍVEIS",
            "termo_busca": "notebook",
            "img": "https://i.imgur.com/2XyW9vR.jpg",
            "destaque": "De R$2.500 por R$1.899"
        },
        {
            "nome": "🎧 FONE BLUETOOTH - ENTREGA RÁPIDA",
            "termo_busca": "fone bluetooth",
            "img": "https://i.imgur.com/7NqPzVb.jpg",
            "destaque": "Bateria de até 20h"
        },
        {
            "nome": "📺 TV SAMSUNG 4K - PREÇO BAIXO",
            "termo_busca": "tv samsung",
            "img": "https://i.imgur.com/3Z7sQHB.jpg",
            "destaque": "Tamanhos de 32' a 65'"
        },
        {
            "nome": "🍳 FRITADEIRA AIR FRYER",
            "termo_busca": "fritadeira eletrica",
            "img": "https://i.imgur.com/8Km5wQa.jpg",
            "destaque": "Sem óleo, mais saúde"
        },
        {
            "nome": "🪑 CADEIRA GAMER - CONFORTO",
            "termo_busca": "cadeira gamer",
            "img": "https://i.imgur.com/4Rt2yW1.jpg",
            "destaque": "Até 120kg de suporte"
        },
        {
            "nome": "❄️ GELADEIRA - ECONOMIA DE ENERGIA",
            "termo_busca": "geladeira",
            "img": "https://i.imgur.com/6ZbX7sY.jpg",
            "destaque": "Melhores marcas"
        },
        {
            "nome": "🧺 MÁQUINA DE LAVAR",
            "termo_busca": "maquina de lavar",
            "img": "https://i.imgur.com/5Vc8xY9.jpg",
            "destaque": "Economia de água"
        }
    ]

    escolhidos = random.sample(produtos, 3)
    lista_final = []

    for p in escolhidos:
        link_busca = f"https://magazineluiza.onelink.me/{SEU_ID_AFILIADO}?af_dp=https://www.magazineluiza.com.br/busca/{quote(p['termo_busca'])}/?order=price_asc"

        lista_final.append({
            "nome": p['nome'],
            "preco": p['destaque'],
            "link": link_busca,
            "img": p['img'],
            "loja": "Magazine Luiza ✅",
            "avaliacao": round(random.uniform(4.5, 5.0),1)
        })
        logging.info(f"✅ Oferta pronta: {p['nome']}")

    return lista_final

# =========================
# FUNÇÃO ENVIAR - CORRIGIDA PARA TELEGRAM
# =========================
async def enviar_ofertas(produtos):
    if not produtos:
        logging.info("Nenhuma oferta para enviar")
        return

    bot = Bot(token=TOKEN_TELEGRAM)

    for p in produtos:
        mensagem = f"""
🔥 **OFERTA IMPERDÍVEL!** 🔥

📌 *{p['nome']}*
💰 Detalhes: {p['preco']}
⭐ Avaliação: {p['avaliacao']}/5.0
🏬 Loja: {p['loja']}

👉 **[VER OFERTAS E COMPRAR]({p['link']})**
        """
        try:
            # ✅ AGORA ENVIA DE VERDADE, SEM ERRO
            await bot.send_photo(
                chat_id=CANAL,
                photo=p['img'],
                caption=mensagem,
                parse_mode="Markdown"
            )
            logging.info(f"✅ ENVIADO COM SUCESSO -> {p['nome']}")
            await asyncio.sleep(5)
        except Exception as e:
            logging.error(f"❌ Erro ao enviar: {e}")
            # Tenta enviar só texto se a foto falhar
            try:
                await bot.send_message(chat_id=CANAL, text=mensagem, parse_mode="Markdown")
                logging.info(f"✅ Enviado como texto -> {p['nome']}")
            except:
                pass

# =========================
# LOOP PRINCIPAL
# =========================
if __name__ == "__main__":
    logging.info("🚀 BOT INICIADO - AGORA VAI CHEGAR NO CANAL!")
    while True:
        ofertas = get_magalu_offers()
        # ✅ RODA A FUNÇÃO DE ENVIO CORRETAMENTE
        asyncio.run(enviar_ofertas(ofertas))
        logging.info("⏳ Ciclo finalizado. Aguardando 30 minutos...\n")
        time.sleep(1800)
