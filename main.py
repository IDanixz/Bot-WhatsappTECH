"""
Bot Shopee -> WhatsApp + Supabase (versão TECH / SETUP)
--------------------------------------------------------
- Busca produtos por uma grande lista de palavras-chave de tecnologia
  (monitor, teclado, mouse, headset, cadeira gamer, mesa gamer, SSD,
  placa de vídeo, power bank, smartwatch, etc.) em vez de busca geral.
  O nicho é garantido pelas próprias keywords de busca.
- Filtra: >= 1000 vendas e >= 4.5 estrelas.
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
            "monitor gamer", "monitor ultrawide", "monitor 4k", "monitor 144hz",
            "monitor 165hz", "monitor 180hz", "monitor 240hz", "monitor 360hz",
            "monitor portátil", "monitor curvo", "teclado mecânico",
            "teclado magnético", "teclado hall effect", "teclado gamer",
            "mouse gamer", "mouse sem fio", "mouse ultraleve", "mousepad gamer",
            "mousepad grande", "headset gamer", "headset sem fio", "fone bluetooth",
            "fone tws", "microfone gamer", "microfone usb", "microfone sem fio",
            "webcam", "webcam 2k", "webcam 4k", "controle gamer", "controle sem fio",
            "controle hall effect", "controle xbox", "controle ps4", "controle ps5",
            "controle pc", "volante gamer", "placa de vídeo", "placa de vídeo rtx",
            "placa de vídeo rx", "placa mãe", "placa mãe am4", "placa mãe am5",
            "processador amd", "processador intel", "ryzen 5", "ryzen 7", "ryzen 9",
            "core i5", "core i7", "core i9", "memória ram", "memória ram ddr4",
            "memória ram ddr5", "memória ram rgb", "ssd nvme", "ssd nvme gen3",
            "ssd nvme gen4", "ssd nvme gen5", "ssd sata", "ssd externo", "hd externo",
            "pendrive", "cartão de memória", "gabinete gamer", "gabinete aquário",
            "gabinete mesh", "gabinete mini tower", "fonte pc", "fonte modular",
            "fonte 80 plus", "water cooler", "water cooler 240mm", "water cooler 360mm",
            "air cooler", "cooler processador", "fan rgb", "kit fans rgb",
            "pasta térmica", "suporte de monitor", "suporte de notebook",
            "suporte de headset", "suporte de controle", "mesa gamer", "escrivaninha",
            "cadeira gamer", "cadeira escritório", "filtro de linha", "nobreak",
            "estabilizador", "hub usb", "hub usb c", "adaptador usb",
            "adaptador bluetooth", "adaptador wifi", "cabo hdmi", "cabo displayport",
            "cabo usb c", "cabo ethernet", "carregador", "carregador turbo",
            "carregador wireless", "power bank", "tomada inteligente", "roteador wifi",
            "roteador gamer", "roteador mesh", "repetidor wifi", "switch de rede",
            "placa wifi", "placa bluetooth", "smart tv", "smart tv 4k", "tv box",
            "fire tv stick", "chromecast", "projetor", "mini projetor", "soundbar",
            "caixa de som bluetooth", "caixa de som portátil", "smart speaker",
            "console de videogame", "playstation 5", "xbox series", "nintendo switch",
            "console portátil", "mini console", "acessórios para ps5",
            "acessórios para xbox", "acessórios para nintendo switch", "celular",
            "smartphone", "celular samsung", "celular xiaomi", "celular motorola",
            "celular poco", "celular redmi", "tablet", "tablet samsung",
            "tablet xiaomi", "tablet android", "notebook", "notebook gamer",
            "notebook ryzen", "notebook intel", "notebook ultrafino", "mini pc",
            "pc gamer", "computador desktop", "all in one", "impressora",
            "impressora multifuncional", "impressora térmica", "impressora 3d",
            "scanner", "mesa digitalizadora", "smartwatch", "smartband",
            "câmera de segurança", "câmera wifi", "câmera ip",
            "campainha inteligente", "fechadura inteligente", "lâmpada inteligente",
            "fita led", "luminária led", "luminária rgb", "ring light", "tripé",
            "suporte celular", "óculos vr", "action cam", "câmera esportiva",
            "drone", "acessórios para celular", "capinha de celular",
            "película celular", "carregador veicular", "suporte celular veicular",
            "mochila para notebook", "mouse gamer sem fio", "teclado gamer sem fio",
            "kit teclado e mouse", "kit upgrade pc", "kit ryzen", "kit xeon",
            "kit memória ram", "kit ssd", "kit pc gamer", "placa de captura",
            "capturadora de vídeo", "stream deck", "braço para microfone",
            "braço para monitor", "organizador de cabos", "extensão elétrica",
        ])
    ).split(",")
    if termo.strip()
]

SHOPEE_PRODUCT_LIMIT = int(os.getenv("SHOPEE_PRODUCT_LIMIT", "5"))
POST_INTERVAL_SEGUNDOS = int(os.getenv("POST_INTERVAL_SEGUNDOS", "30"))

SHOPEE_VENDAS_MINIMAS = int(os.getenv("SHOPEE_VENDAS_MINIMAS", "1000"))
SHOPEE_AVALIACAO_MINIMA = float(os.getenv("SHOPEE_AVALIACAO_MINIMA", "4.5"))

SHOPEE_BUSCA_BRUTA = int(os.getenv("SHOPEE_BUSCA_BRUTA", "50"))
SHOPEE_INTERVALO_PAGINAS = float(
    os.getenv("SHOPEE_INTERVALO_PAGINAS", "0.3")
)
SHOPEE_INTERVALO_KEYWORDS = float(
    os.getenv("SHOPEE_INTERVALO_KEYWORDS", "0.5")
)
# Limite de páginas por keyword nesta rodada (evita ficar preso numa
# keyword só, gastando todas as requisições nela). Ajustável via .env.
SHOPEE_MAX_PAGINAS_POR_KEYWORD = int(os.getenv("SHOPEE_MAX_PAGINAS_POR_KEYWORD", "3"))

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

    print(f"[DEBUG] Configuração OK. Keywords carregadas: {len(SHOPEE_SEARCH_KEYWORDS)}", flush=True)
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


def produto_passou_filtro(produto: dict) -> bool:
    # Sem whitelist de nome: o filtro de nicho já é feito pelas próprias
    # keywords de busca (SHOPEE_SEARCH_KEYWORDS). Aqui só checa vendas/nota.
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

            if pagina == 1 and produtos:
                print("[DEBUG] Amostra dos 3 primeiros produtos (nome | sales | ratingStar):", flush=True)
                for p in produtos[:3]:
                    print(
                        f"[DEBUG]   - {p.get('productName')!r} | sales={p.get('sales')!r} | ratingStar={p.get('ratingStar')!r}",
                        flush=True,
                    )

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

            print(f"[DEBUG] keyword='{keyword}' pagina={pagina}: {passaram_filtro} passaram no filtro (vendas/nota), {ja_postados} já tinham sido postados antes", flush=True)

            if not page_info.get("hasNextPage"):
                break

            if pagina >= SHOPEE_MAX_PAGINAS_POR_KEYWORD:
                print(f"[DEBUG] Atingiu o limite de {SHOPEE_MAX_PAGINAS_POR_KEYWORD} páginas para essa keyword, pulando pra próxima.", flush=True)
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
        print("[DEBUG] Rodando em modo --loop (contínuo).", flush=True)
        rodar_continuamente()
    else:
        print("[DEBUG] Rodando UMA VEZ (sem --loop). Confira o start.sh se quiser loop.", flush=True)
        rodar_uma_vez()
        print("[DEBUG] Execução única finalizada.", flush=True)
