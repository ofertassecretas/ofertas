import requests
import random
import logging
import json
import html
import asyncio
import time
from bs4 import BeautifulSoup
from telegram.ext import ApplicationBuilder, ContextTypes

# Configurações de log
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# =========================
# CONFIGURAÇÕES
# =========================
TELEGRAM_TOKEN = "SEU_TOKEN_AQUI"
CHAT_ID_DESTINO = "SEU_CHAT_ID_AQUI"
CHECK_INTERVAL = 5400 # 1h30 em segundos

# URLs de departamentos do Magazine Luiza (Magazine Você)
MAGALU_URLS = [
    "https://www.magazinevoce.com.br/magazineshopandreonline/selecao/ofertasdodia/",
    "https://www.magazinevoce.com.br/magazineshopandreonline/celulares-e-smartphones/l/te/",
    "https://www.magazinevoce.com.br/magazineshopandreonline/tv-e-video/l/et/"
]

usadas_abertura = set()

# =========================
# FUNÇÕES AUXILIARES
# =========================
def dentro_do_horario():
    # Implemente sua lógica de horário aqui
    return True

def aplicar_id_afiliado(link):
    # Implemente sua lógica de afiliado Shopee aqui
    return link

def gerar_copy(nome, preco, vendas, rating, comissao, link):
    # Implemente sua lógica de copy aqui
    return f"🔥 {nome}\n💰 Por apenas R$ {preco}\n⭐ {rating} ({vendas} vendas)\n🛒 Compre aqui: {link}"

def gerar_link_whatsapp_from_html(msg, link):
    # Implemente sua lógica de link do WhatsApp aqui
    return link

# =========================
# SHOPEE (Mock para o exemplo)
# =========================
def get_shopee_offers():
    return []

# =========================
# MERCADO LIVRE (Mock para o exemplo)
# =========================
def get_ml_offers():
    return []

# =========================
# MAGAZINE LUIZA (MELHORADO)
# =========================
def get_magalu_offers():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    produtos_extraidos = []

    try:
        url = random.choice(MAGALU_URLS)
        logging.info(f"Buscando ofertas Magalu em: {url}")

        r = requests.get(url, headers=headers, timeout=20)
        logging.info(f"Status Magalu: {r.status_code}")

        if r.status_code != 200:
            logging.error("Falha ao acessar a página do Magalu.")
            return []

        # Extrair o JSON __NEXT_DATA__ usando BeautifulSoup
        soup = BeautifulSoup(r.text, 'html.parser')
        script_tag = soup.find('script', id='__NEXT_DATA__')

        if not script_tag:
            logging.warning("Tag __NEXT_DATA__ não encontrada no HTML.")
            return []

        data = json.loads(script_tag.string)

        # Função recursiva para encontrar a lista de produtos no JSON complexo
        def find_products(d):
            if isinstance(d, dict):
                if 'products' in d and isinstance(d['products'], list):
                    return d['products']
                for k, v in d.items():
                    res = find_products(v)
                    if res: return res
            elif isinstance(d, list):
                for item in d:
                    res = find_products(item)
                    if res: return res
            return None

        products_list = find_products(data)

        if not products_list:
            logging.warning("Lista de produtos não encontrada dentro do JSON.")
            return []

        logging.info(f"Magalu OK: {len(products_list)} produtos encontrados no JSON.")

        # Processar os produtos encontrados
        for item in products_list[:10]: # Pegar os 10 primeiros para ter opções
            try:
                # Extrair dados relevantes
                titulo = item.get("title", "Produto sem título")
                
                # Preço
                preco_dict = item.get("price", {})
                preco_atual = preco_dict.get("bestPrice") or preco_dict.get("price")
                
                if not preco_atual:
                    continue # Pula se não tiver preço
                
                # Imagem (substituindo os placeholders de tamanho se existirem)
                img_url = item.get("image", "")
                if "{w}" in img_url and "{h}" in img_url:
                    img_url = img_url.replace("{w}", "500").replace("{h}", "500")
                
                # Link
                link_path = item.get("url", "")
                if not link_path.startswith("http"):
                    # Ajustar o domínio base conforme necessário
                    link_completo = f"https://www.magazinevoce.com.br{link_path}"
                else:
                    link_completo = link_path

                # Avaliação
                rating_dict = item.get("rating", {})
                avaliacao = rating_dict.get("score", 4.5)
                vendas = rating_dict.get("count", random.randint(10, 500))

                produtos_extraidos.append({
                    "nome": titulo,
                    "preco": preco_atual,
                    "link": link_completo,
                    "img": img_url,
                    "vendas": vendas,
                    "avaliacao": avaliacao,
                    "origem": "magalu"
                })

            except Exception as e:
                logging.error(f"Erro ao processar item individual do Magalu: {e}")

    except Exception as e:
        logging.error(f"ERRO MAGALU: {e}")

    return produtos_extraidos

# =========================
# ENVIO
# =========================
async def send_ofertas(context: ContextTypes.DEFAULT_TYPE):
    try:
        logging.info("Loop de ofertas iniciado")

        if not dentro_do_horario():
            logging.info("Fora do horario")
            return

        usadas_abertura.clear()

        shopee_ofertas = get_shopee_offers()
        ml_ofertas = get_ml_offers()
        magalu_ofertas = get_magalu_offers() # Chamada para a nova função

        selecionadas = []

        # ... (Lógica da Shopee e ML omitida para brevidade, mantenha a sua) ...

        # =========================
        # MAGALU (2)
        # =========================
        for item in magalu_ofertas[:2]:
            try:
                link = item["link"]
                nome = html.escape(item["nome"])
                preco = float(item["preco"])
                img = item["img"]
                rating = item["avaliacao"]
                vendas = item["vendas"]
                comissao = 10 # Exemplo

                vendas_f = f"{vendas:,}".replace(",", ".")

                msg = gerar_copy(
                    nome,
                    f"{preco:.2f}",
                    vendas_f,
                    rating,
                    comissao,
                    link
                )

                zap = gerar_link_whatsapp_from_html(msg, link)

                msg += f'\n📲 <a href="{zap}">Compartilhar no WhatsApp</a>'
                msg += "\n━━━━━━━━━━━━━━━\n📢 <b>Ofertas Secretas</b>"

                selecionadas.append({
                    "msg": msg,
                    "img": img
                })

            except Exception as e:
                logging.error(f"Erro Magalu item: {e}")

        logging.info(f"Selecionadas no total: {len(selecionadas)}")

        if len(selecionadas) == 0:
            logging.warning("Nenhuma oferta encontrada")
            return

        await context.bot.send_message(
            chat_id=CHAT_ID_DESTINO,
            text="🚨 OFERTAS NOVAS CHEGANDO..."
        )

        await asyncio.sleep(5)

        for item in selecionadas:
            try:
                logging.info("Enviando produto")
                await context.bot.send_photo(
                    chat_id=CHAT_ID_DESTINO,
                    photo=item["img"],
                    caption=item["msg"],
                    parse_mode="HTML"
                )
                await asyncio.sleep(40)
            except Exception as e:
                logging.error(f"Erro Telegram: {e}")

        logging.info("Loop finalizado")

    except Exception as e:
        logging.error(f"ERRO CRITICO: {e}")

# =========================
# KEEP ALIVE
# =========================
async def keep_alive():
    while True:
        logging.info("BOT VIVO")
        await asyncio.sleep(300)

# =========================
# START
# =========================
async def post_init(app):
    app.job_queue.run_repeating(
        send_ofertas,
        interval=CHECK_INTERVAL,
        first=10
    )
    asyncio.create_task(keep_alive())
    logging.info("🤖 BOT RODANDO ESTAVEL")

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

        


