"""
Bot Shopee -> WhatsApp + Supabase (versão TECH / SETUP)
--------------------------------------------------------
- Busca produtos por uma lista de palavras-chave de tecnologia
  (monitor, teclado, mouse, headset, cadeira gamer, mesa gamer,
  SSD, power bank, smartwatch, etc.) em vez de busca geral.
- Filtra: >= 1000 vendas e >= 4.5 estrelas.
- Filtra também por "é produto de tech?" (whitelist), então mesmo
  que a keyword traga lixo, só posta o que bate com termos de
  eletrônicos/gadgets/setup.
- Processa página por página, keyword por keyword: não espera
  terminar toda a busca. Posta assim que encontra um produto válido
  e ainda não enviado.
- Usa Supabase como histórico permanente.
- Mantém servidor HTTP para Render/UptimeRobot (via server.js/Node).
"""

import os
import sys
import json
import time
import hashlib
import re
import unicodedata

import requests
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ===================== CONFIGURAÇÕES =====================

SHOPEE_APP_ID = os.getenv("SHOPEE_APP_ID")
SHOPEE_SECRET = os.getenv("SHOPEE_SECRET")
SHOPEE_AFFILIATE_ID = os.getenv("SHOPEE_AFFILIATE_ID")
SHOPEE_API_URL = os.getenv(
    "SHOPEE_API_URL",
    "https://open-api.affiliate.shopee.com.br/graphql"
)

WHATSAPP_ENABLED = os.getenv("WHATSAPP_ENABLED", "true").lower() == "true"
WHATSAPP_CHANNEL_NAME = os.getenv("WHATSAPP_CHANNEL_NAME", "Divulga Promos Tech")
WHATSAPP_CHANNEL_LINK = os.getenv("WHATSAPP_CHANNEL_LINK", "")
RENDER_PORT = os.getenv("PORT", "3333")
WHATSAPP_SERVICE_URL = os.getenv(
    "WHATSAPP_SERVICE_URL",
    f"http://127.0.0.1:{RENDER_PORT}"
).rstrip("/")
WHATSAPP_GROUP_ID = os.getenv("WHATSAPP_GROUP_ID", "")

# ---- Palavras-chave de busca: tudo relacionado a setup/tech ----
# Pode sobrescrever via .env: SHOPEE_SEARCH_KEYWORDS separadas por vírgula.
SHOPEE_SEARCH_KEYWORDS = [
    termo.strip()
    for termo in os.getenv(
        "SHOPEE_SEARCH_KEYWORDS",
        ",".join([
            "monitor gamer",
            "monitor ultrawide",
            "teclado mecanico",
            "teclado sem fio",
            "mouse gamer",
            "mouse sem fio",
            "mousepad gamer",
            "headset gamer",
            "fone bluetooth",
            "fone de ouvido",
            "caixa de som bluetooth",
            "cadeira gamer",
            "cadeira escritorio",
            "mesa gamer",
            "mesa escritorio",
            "suporte de monitor",
            "suporte notebook",
            "luminaria de mesa led",
            "webcam",
            "microfone",
            "hub usb",
            "adaptador hdmi",
            "cabo usb c",
            "carregador turbo",
            "carregador wireless",
            "power bank",
            "ssd nvme",
            "ssd externo",
            "pendrive",
            "cartao de memoria",
            "placa de video",
            "memoria ram",
            "processador",
            "gabinete gamer",
            "fonte para pc",
            "cooler para pc",
            "roteador wifi",
            "repetidor wifi",
            "smart tv",
            "fire tv stick",
            "chromecast",
            "console de videogame",
            "controle joystick",
            "smartwatch",
            "tablet",
            "notebook gamer",
            "smartphone",
            "impressora",
            "camera de seguranca",
            "drone",
        ])
    ).split(",")
    if termo.strip()
]

SHOPEE_PRODUCT_LIMIT = int(os.getenv("SHOPEE_PRODUCT_LIMIT", "5"))
POST_INTERVAL_SEGUNDOS = int(os.getenv("POST_INTERVAL_SEGUNDOS", "30"))

SHOPEE_VENDAS_MINIMAS = int(os.getenv("SHOPEE_VENDAS_MINIMAS", "1000"))
SHOPEE_AVALIACAO_MINIMA = float(os.getenv("SHOPEE_AVALIACAO_MINIMA", "4.5"))

# ---- Whitelist: só posta se o NOME do produto bater com termo de tech ----
# Isso evita que a keyword de busca traga produto errado (ex: "capa" de outro nicho).
# Pode sobrescrever via .env: TERMOS_TECH_PERMITIDOS separados por vírgula.
TERMOS_TECH_PERMITIDOS = [
    termo.strip()
    for termo in os.getenv(
        "TERMOS_TECH_PERMITIDOS",
        ",".join([
            "gamer", "gaming", "bluetooth", "wireless", "sem fio", "usb",
            "usb-c", "type c", "wifi", "wi-fi", "led", "rgb", "smart",
            "notebook", "laptop", "monitor", "teclado", "mouse", "mousepad",
            "headset", "fone", "headphone", "earbud", "caixa de som",
            "speaker", "cadeira", "mesa", "suporte", "webcam", "microfone",
            "hub", "adaptador", "hdmi", "cabo", "carregador", "power bank",
            "powerbank", "bateria portatil", "ssd", "hd externo", "hd 1tb",
            "pendrive", "cartao de memoria", "placa de video", "placa mae",
            "memoria ram", "processador", "gabinete", "fonte atx", "cooler",
            "roteador", "repetidor", "smart tv", "fire tv", "chromecast",
            "console", "joystick", "controle", "smartwatch", "relogio inteligente",
            "tablet", "smartphone", "celular", "impressora", "camera",
            "drone", "eletronico", "eletronicos", "gadget", "setup",
        ])
    ).split(",")
    if termo.strip()
]

SHOPEE_BUSCA_BRUTA = int(os.getenv("SHOPEE_BUSCA_BRUTA", "50"))
SHOPEE_INTERVALO_PAGINAS = float(
    os.getenv("SHOPEE_INTERVALO_PAGINAS", "0.3")
)
SHOPEE_INTERVALO_KEYWORDS = float(
    os.getenv("SHOPEE_INTERVALO_KEYWORDS", "0.5")
)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client | None = None

# Cache local em memória dos produtos que já foram enviados.
postados_cache = set()


# ===================== CONFIGURAÇÃO =====================

def checar_configuracao():
    obrigatorias = {
        "SHOPEE_APP_ID": SHOPEE_APP_ID,
        "SHOPEE_SECRET": SHOPEE_SECRET,
        "SUPABASE_URL": SUPABASE_URL,
        "SUPABASE_KEY": SUPABASE_KEY,
    }

    faltando = [k for k, v in obrigatorias.items() if not v]

    if faltando:
        print(f"[DEBUG] Variáveis obrigatórias faltando: {faltando}", flush=True)
        sys.exit(1)

    if WHATSAPP_ENABLED and not WHATSAPP_GROUP_ID:
        print("[DEBUG] WHATSAPP_ENABLED=true mas WHATSAPP_GROUP_ID está vazio.", flush=True)
        sys.exit(1)

    print("[DEBUG] Configuração OK. Keywords carregadas:", len(SHOPEE_SEARCH_KEYWORDS), flush=True)
    print("[DEBUG] Termos tech carregados:", len(TERMOS_TECH_PERMITIDOS), flush=True)
    print(f"[DEBUG] SHOPEE_PRODUCT_LIMIT={SHOPEE_PRODUCT_LIMIT} SHOPEE_VENDAS_MINIMAS={SHOPEE_VENDAS_MINIMAS} SHOPEE_AVALIACAO_MINIMA={SHOPEE_AVALIACAO_MINIMA}", flush=True)

    global supabase
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ===================== SUPABASE =====================

def id_do_produto(produto: dict) -> str:
    """ID estável. Primeiro usa itemId da Shopee."""
    if produto.get("itemId") is not None:
        return str(produto["itemId"])

    return str(
        produto.get("offerLink")
        or produto.get("productName", "")
    ).strip()


def carregar_historico_supabase():
    """Carrega os IDs já enviados para a memória (com paginação)."""
    global postados_cache

    if not supabase:
        raise RuntimeError("Supabase não foi inicializado.")

    inicio = 0
    tamanho = 1000

    while True:
        resposta = (
            supabase
            .table("produtos_postados")
            .select("produto_id")
            .range(inicio, inicio + tamanho - 1)
            .execute()
        )

        linhas = resposta.data or []

        for linha in linhas:
            produto_id = linha.get("produto_id")
            if produto_id:
                postados_cache.add(str(produto_id))

        if len(linhas) < tamanho:
            break

        inicio += tamanho

    print(f"[DEBUG] Histórico carregado do Supabase: {len(postados_cache)} produtos já postados.", flush=True)


def salvar_produto_postado(produto: dict):
    """Salva depois que o WhatsApp confirmou o envio."""
    if not supabase:
        raise RuntimeError("Supabase não foi inicializado.")

    produto_id = id_do_produto(produto)
    link = produto.get("offerLink") or ""

    try:
        supabase.table("produtos_postados").insert({
            "produto_id": produto_id,
            "link": link,
        }).execute()

        postados_cache.add(produto_id)

    except Exception as e:
        texto = str(e).lower()

        if (
            "duplicate" in texto
            or "unique" in texto
            or "23505" in texto
        ):
            postados_cache.add(produto_id)
        else:
            raise


# ===================== SHOPEE =====================

def gerar_assinatura(payload: str):
    timestamp = int(time.time())
    base_string = f"{SHOPEE_APP_ID}{timestamp}{payload}{SHOPEE_SECRET}"
    assinatura = hashlib.sha256(
        base_string.encode("utf-8")
    ).hexdigest()

    return assinatura, timestamp


QUERY_PRODUTOS = """
query productOfferV2($keyword: String, $page: Int, $limit: Int, $sortType: Int) {
  productOfferV2(
    keyword: $keyword,
    page: $page,
    limit: $limit,
    sortType: $sortType
  ) {
    nodes {
      itemId
      productName
      priceMin
      priceMax
      priceDiscountRate
      sales
      ratingStar
      offerLink
      imageUrl
    }
    pageInfo {
      page
      limit
      hasNextPage
    }
  }
}
"""


def buscar_pagina(keyword: str, pagina: int):
    """Busca UMA página de UMA keyword específica."""
    limite = min(max(SHOPEE_BUSCA_BRUTA, 1), 500)

    variables = {
        "keyword": keyword or None,
        "page": pagina,
        "limit": limite,
        "sortType": 1,  # relevância
    }

    body = {
        "query": QUERY_PRODUTOS,
        "variables": variables,
    }

    payload = json.dumps(body, separators=(",", ":"))
    assinatura, timestamp = gerar_assinatura(payload)

    headers = {
        "Content-Type": "application/json",
        "Authorization": (
            f"SHA256 Credential={SHOPEE_APP_ID}, "
            f"Timestamp={timestamp}, "
            f"Signature={assinatura}"
        ),
    }

    resposta = requests.post(
        SHOPEE_API_URL,
        headers=headers,
        data=payload,
        timeout=30,
    )

    resposta.raise_for_status()
    dados = resposta.json()

    if dados.get("errors"):
        raise Exception(
            f"Erro retornado pela API da Shopee: {dados['errors']}"
        )

    resultado = dados["data"]["productOfferV2"]

    return (
        resultado.get("nodes") or [],
        resultado.get("pageInfo") or {},
    )


def normalizar_texto(texto) -> str:
    """Minúsculas + sem acentos, para o filtro pegar variações do título."""
    texto = str(texto or "").lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return f" {texto.strip()} "


def produto_e_tech(produto: dict) -> bool:
    """Whitelist: só é aprovado se o nome bater com algum termo de tech/setup."""
    nome = normalizar_texto(produto.get("productName", ""))

    for termo in TERMOS_TECH_PERMITIDOS:
        termo_normalizado = normalizar_texto(termo).strip()
        if termo_normalizado and termo_normalizado in nome:
            return True

    return False


def produto_passou_filtro(produto: dict) -> bool:
    # Só passa se for claramente um produto de tech/setup.
    if not produto_e_tech(produto):
        return False

    try:
        vendas = float(produto.get("sales") or 0)
        avaliacao = float(produto.get("ratingStar") or 0)
    except (TypeError, ValueError):
        return False

    return (
        vendas >= SHOPEE_VENDAS_MINIMAS
        and avaliacao >= SHOPEE_AVALIACAO_MINIMA
    )


# ===================== FORMATAÇÃO =====================

def _para_float(valor, padrao=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def formatar_valor_brl(valor: float) -> str:
    return f"R$ {valor:.2f}".replace(".", ",")


def calcular_precos(produto: dict):
    preco_atual = _para_float(produto.get("priceMin") or produto.get("priceMax") or 0)
    taxa_desconto = _para_float(produto.get("priceDiscountRate"))
    preco_original = None
    percentual = 0

    if 0 < taxa_desconto < 100:
        preco_original = preco_atual / (1 - taxa_desconto / 100)
        percentual = round(taxa_desconto)

    return preco_atual, preco_original, percentual


# ===================== WHATSAPP (via serviço Node.js/Baileys) =====================

def formatar_bloco_preco_texto(produto: dict) -> str:
    preco_atual, preco_original, percentual = calcular_precos(produto)
    preco_atual_fmt = formatar_valor_brl(preco_atual)

    if preco_original and percentual > 0:
        preco_original_fmt = formatar_valor_brl(preco_original)
        return (
            f"~{preco_original_fmt}~ 🏷️ -{percentual}% OFF\n"
            f"💵 *{preco_atual_fmt}*"
        )

    return f"💵 *{preco_atual_fmt}*"


def formatar_mensagem_whatsapp(produto: dict) -> str:
    nome = produto.get("productName", "Produto")
    bloco_preco = formatar_bloco_preco_texto(produto)
    link = produto.get("offerLink", "")

    partes = [
        f"💻 *{nome}*",
        bloco_preco,
        f"🔗 {link}",
    ]

    if WHATSAPP_CHANNEL_NAME:
        partes.append(WHATSAPP_CHANNEL_NAME)
    if WHATSAPP_CHANNEL_LINK:
        partes.append(WHATSAPP_CHANNEL_LINK)

    partes.append("#Tech #Setup #Promo")
    return "\n\n".join(partes)


def enviar_whatsapp(mensagem: str, image_url: str = ""):
    url = f"{WHATSAPP_SERVICE_URL}/send"

    resposta = requests.post(
        url,
        json={
            "group_id": WHATSAPP_GROUP_ID,
            "message": mensagem,
            "image_url": image_url or "",
        },
        timeout=60,
    )
    resposta.raise_for_status()
    return resposta.json()


# ===================== PROCESSAMENTO OTIMIZADO =====================

def processar_produto(produto: dict) -> bool:
    """Tenta enviar UM produto para o WhatsApp."""
    produto_id = id_do_produto(produto)

    if produto_id in postados_cache:
        return False

    if not produto_passou_filtro(produto):
        return False

    try:
        if not WHATSAPP_ENABLED:
            return False

        enviar_whatsapp(
            formatar_mensagem_whatsapp(produto),
            produto.get("imageUrl") or "",
        )

        salvar_produto_postado(produto)
        print(f"[DEBUG] POSTADO: {produto.get('productName')}", flush=True)
        return True

    except Exception as e:
        print(f"[DEBUG] ERRO ao enviar/salvar produto '{produto.get('productName')}': {e}", flush=True)
        return False


def rodar_uma_vez():
    """
    Para cada keyword de tech na lista:
      página -> filtro tech -> posta imediatamente -> próxima página.
    Para ao atingir SHOPEE_PRODUCT_LIMIT (somando todas as keywords).
    """
    limite_posts = max(SHOPEE_PRODUCT_LIMIT, 1)
    postados_nesta_rodada = 0

    if not SHOPEE_SEARCH_KEYWORDS:
        print("[DEBUG] Lista de keywords está vazia!", flush=True)
        return

    for keyword in SHOPEE_SEARCH_KEYWORDS:
        pagina = 1
        print(f"[DEBUG] === Buscando keyword: '{keyword}' ===", flush=True)

        while True:
            try:
                produtos, page_info = buscar_pagina(keyword, pagina)
            except Exception as e:
                print(f"[DEBUG] ERRO na busca (keyword='{keyword}', pagina={pagina}): {e}", flush=True)
                break  # tenta a próxima keyword

            print(f"[DEBUG] keyword='{keyword}' pagina={pagina}: {len(produtos)} produtos retornados pela Shopee", flush=True)

            if not produtos:
                break

            passaram_filtro = 0
            ja_postados = 0

            for produto in produtos:
                if not produto_passou_filtro(produto):
                    continue

                passaram_filtro += 1
                produto_id = id_do_produto(produto)

                if produto_id in postados_cache:
                    ja_postados += 1
                    continue

                if processar_produto(produto):
                    postados_nesta_rodada += 1

                    if postados_nesta_rodada >= limite_posts:
                        print(f"[DEBUG] Limite de {limite_posts} posts atingido nesta rodada.", flush=True)
                        return

                    time.sleep(2)

            print(f"[DEBUG] keyword='{keyword}' pagina={pagina}: {passaram_filtro} passaram no filtro tech, {ja_postados} já tinham sido postados antes", flush=True)

            if not page_info.get("hasNextPage"):
                break

            pagina += 1
            time.sleep(SHOPEE_INTERVALO_PAGINAS)

        # pequena pausa entre uma keyword e outra
        time.sleep(SHOPEE_INTERVALO_KEYWORDS)

    print(f"[DEBUG] Rodada finalizada. Total postado nesta rodada: {postados_nesta_rodada}", flush=True)


def rodar_continuamente():
    while True:
        try:
            rodar_uma_vez()
        except Exception as e:
            print(f"[DEBUG] ERRO inesperado em rodar_uma_vez: {e}", flush=True)

        print(f"[DEBUG] Aguardando {POST_INTERVAL_SEGUNDOS}s até a próxima rodada...", flush=True)
        time.sleep(max(POST_INTERVAL_SEGUNDOS, 1))


# ===================== MAIN =====================

if __name__ == "__main__":
    checar_configuracao()
    carregar_historico_supabase()

    if "--loop" in sys.argv:
        rodar_continuamente()
    else:
        rodar_uma_vez()
