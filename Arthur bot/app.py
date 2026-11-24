
import os
import re
import json
import requests

from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, urljoin, parse_qs
from threading import Lock

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv


# ==========================================
# CONFIGURAÇÕES
# ==========================================

app = Flask(__name__)

PASTA_PROJETO = Path(__file__).resolve().parent
PASTA_DATABASE = PASTA_PROJETO / "database"
ARQUIVO_BANCO = PASTA_DATABASE / "banco_dados.json"
ARQUIVO_ENV = PASTA_PROJETO / ".env"

PASTA_DATABASE.mkdir(exist_ok=True)

load_dotenv(dotenv_path=ARQUIVO_ENV, override=True)

ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "").strip()

API_BASE = "https://api.mercadolibre.com"

CABECALHOS = {
    "User-Agent": "ArthurBot/1.0"
}

if ACCESS_TOKEN:
    CABECALHOS["Authorization"] = f"Bearer {ACCESS_TOKEN}"

bloqueio_banco = Lock()


# ==========================================
# BANCO DE DADOS JSON
# ==========================================

BANCO_INICIAL = {
    "produtos_analisados": [],
    "lojas_confiaveis": [
        "mercadolivre.com.br",
        "amazon.com.br"
    ],
    "lojas_suspeitas": [],
    "vendedores": [],
    "historico": []
}


def carregar_banco():

    if not ARQUIVO_BANCO.exists():
        salvar_banco(BANCO_INICIAL)

    try:
        with open(ARQUIVO_BANCO, "r", encoding="utf-8") as arquivo:
            dados = json.load(arquivo)

        for chave, valor in BANCO_INICIAL.items():
            dados.setdefault(chave, valor.copy())

        return dados

    except (json.JSONDecodeError, OSError):
        raise RuntimeError(
            "Não foi possível ler o banco de dados JSON."
        )


def salvar_banco(dados):

    arquivo_temporario = ARQUIVO_BANCO.with_suffix(".tmp")

    with open(arquivo_temporario, "w", encoding="utf-8") as arquivo:
        json.dump(
            dados,
            arquivo,
            indent=4,
            ensure_ascii=False
        )

    arquivo_temporario.replace(ARQUIVO_BANCO)


def registrar_analise(produto):

    with bloqueio_banco:

        banco = carregar_banco()

        banco["produtos_analisados"].append(produto)

        banco["historico"].append({
            "titulo": produto.get("titulo"),
            "link": produto.get("link"),
            "data": produto.get("data")
        })

        vendedor = produto.get("vendedor")

        if vendedor:
            banco["vendedores"].append(vendedor)

        salvar_banco(banco)


# ==========================================
# COMUNICAÇÃO COM MERCADO LIVRE
# ==========================================

class ArthurBotError(Exception):
    pass


def consultar_api(endpoint):

    if not ACCESS_TOKEN:
        raise ArthurBotError(
            "Token não encontrado. Confira o arquivo .env."
        )

    url = f"{API_BASE}{endpoint}"

    try:
        resposta = requests.get(
            url,
            headers=CABECALHOS,
            timeout=20
        )

        if resposta.status_code == 401:
            raise ArthurBotError(
                "Token inválido ou expirado."
            )

        if resposta.status_code == 403:
            raise ArthurBotError(
                "Acesso negado pela API do Mercado Livre."
            )

        if resposta.status_code == 404:
            raise ArthurBotError(
                "Informação não encontrada no Mercado Livre."
            )

        resposta.raise_for_status()

        return resposta.json()

    except requests.RequestException as erro:
        raise ArthurBotError(
            f"Erro de comunicação com o Mercado Livre: {erro}"
        )


# ==========================================
# VALIDAÇÃO E IDENTIFICAÇÃO DE LINKS
# ==========================================

DOMINIOS_ML = (
    "mercadolivre.com.br",
    "mercadolivre.com",
    "mercadolibre.com"
)


def dominio_valido(host):

    host = host.lower().split(":")[0]

    return any(
        host == dominio or host.endswith("." + dominio)
        for dominio in DOMINIOS_ML
    ) or host == "meli.la"


def resolver_link(link):

    if not link.startswith(("http://", "https://")):
        link = "https://" + link

    atual = link

    for tentativa in range(6):

        partes = urlparse(atual)

        if partes.scheme not in ("http", "https"):
            raise ArthurBotError("Protocolo de link inválido.")

        if not dominio_valido(partes.hostname or ""):
            raise ArthurBotError(
                "O link não pertence ao Mercado Livre."
            )

        try:
            resposta = requests.get(
                atual,
                headers={"User-Agent": "ArthurBot/1.0"},
                allow_redirects=False,
                timeout=15
            )

        except requests.RequestException as erro:
            raise ArthurBotError(
                f"Não foi possível acessar o link: {erro}"
            )

        if resposta.status_code in (301, 302, 303, 307, 308):

            destino = resposta.headers.get("Location")

            if not destino:
                raise ArthurBotError(
                    "Redirecionamento sem endereço de destino."
                )

            atual = urljoin(atual, destino)
            continue

        return atual

    raise ArthurBotError(
        "O link possui muitos redirecionamentos."
    )



def extrair_ids(link):

    url = resolver_link(link)

    print("\n========== DIAGNÓSTICO ARTHUR BOT ==========")
    print("Link recebido:", link)
    print("Link resolvido:", url)
    print("Caminho:", urlparse(url).path)
    print("Parâmetros:", parse_qs(urlparse(url).query))
    print("============================================\n")
    
    partes = urlparse(url)

    caminho = partes.path.upper()
    parametros = parse_qs(partes.query)

    item_id = None
    product_id = None

    # 1. Procura o ID nos parâmetros da URL
    for chave in ("item_id", "wid"):

        valores = parametros.get(chave, [])

        for valor in valores:
            encontrado = re.search(
                r"MLB-?\d{6,}",
                valor.upper()
            )

            if encontrado:
                item_id = encontrado.group()
                break

        if item_id:
            break

    # 2. Procura o ID dentro de pdp_filters
    filtros = parametros.get("pdp_filters", [])

    for filtro in filtros:

        encontrado = re.search(
            r"ITEM_ID\s*:\s*(MLB-?\d{6,})",
            filtro.upper()
        )

        if encontrado:
            item_id = encontrado.group(1)
            break

    # 3. Procura produtos de catálogo (/p/MLB...)
    if not item_id:

        encontrado = re.search(
            r"/P/(MLB-?\d{6,})",
            caminho
        )

        if encontrado:
            product_id = encontrado.group(1)

    # 4. Procura IDs de anúncios no restante do caminho
    if not item_id and not product_id:

        encontrado = re.search(
            r"(MLB-?\d{6,})",
            caminho
        )

        if encontrado:
            item_id = encontrado.group(1)

    if not item_id and not product_id:

        print("URL recebida:", link)
        print("URL após redirecionamento:", url)

        raise ArthurBotError(
            "Não foi possível identificar o código MLB do produto. "
            "Verifique se o link abre diretamente o anúncio."
        )

    print("Produto identificado:", item_id or product_id)

    return {
        "item_id": item_id,
        "product_id": product_id,
        "url": url
    }



# ==========================================
# BUSCAR DADOS DO PRODUTO
# ==========================================

def obter_dados_produto(ids):

    if ids["item_id"]:

        item = consultar_api(
            f"/items/{ids['item_id']}"
        )

    else:

        catalogo = consultar_api(
            f"/products/{ids['product_id']}"
        )

        vencedor = catalogo.get("buy_box_winner") or {}

        item_id = vencedor.get("item_id")

        if not item_id:
            raise ArthurBotError(
                "Não foi encontrado um anúncio disponível para esse produto."
            )

        item = consultar_api(
            f"/items/{item_id}"
        )

        if not item.get("title"):
            item["title"] = catalogo.get("name", "Produto sem título")

    return item


# ==========================================
# BUSCAR AVALIAÇÕES E VENDEDOR
# ==========================================

def obter_avaliacoes(item_id):

    dados = consultar_api(
        f"/reviews/item/{item_id}"
    )

    return {
        "media": dados.get("rating_average"),
        "quantidade": dados.get("paging", {}).get("total", 0)
    }


def obter_vendedor(seller_id):

    dados = consultar_api(
        f"/users/{seller_id}"
    )

    reputacao = dados.get("seller_reputation") or {}

    transacoes = reputacao.get("transactions") or {}

    avaliacoes = transacoes.get("ratings") or {}

    return {
        "id": seller_id,
        "apelido": dados.get("nickname", "Não informado"),
        "nivel": reputacao.get("level_id"),
        "positivas": avaliacoes.get("positive"),
        "negativas": avaliacoes.get("negative"),
        "neutras": avaliacoes.get("neutral"),
        "status": dados.get("status", {}).get("site_status")
    }


# ==========================================
# ANÁLISE DE REPUTAÇÃO
# ==========================================

def analisar_reputacao(avaliacoes, vendedor):

    media = avaliacoes.get("media")

    quantidade = avaliacoes.get("quantidade", 0)

    positivas = vendedor.get("positivas")

    if media is None or positivas is None:
        return {
            "pontuacao": None,
            "classificacao": "Dados insuficientes",
            "mensagem": "Não foi possível obter todos os dados."
        }

    # Indicador criado para o projeto.
    # Não representa uma nota oficial do Mercado Livre.

    pontuacao_produto = (float(media) / 5) * 50

    pontuacao_vendedor = float(positivas) * 50

    pontuacao = round(
        pontuacao_produto + pontuacao_vendedor,
        2
    )

    if quantidade < 5:
        classificacao = "Poucas avaliações"

    elif pontuacao >= 90:
        classificacao = "Boa reputação"

    elif pontuacao >= 70:
        classificacao = "Reputação intermediária"

    else:
        classificacao = "Requer atenção"

    return {
        "pontuacao": pontuacao,
        "classificacao": classificacao,
        "mensagem": (
            "Indicador informativo baseado nos dados disponíveis. "
            "Não garante a segurança da compra."
        )
    }


# ==========================================
# ANALISAR PRODUTO COMPLETO
# ==========================================

def analisar_produto(link):

    if not ACCESS_TOKEN:
        raise ArthurBotError(
            "Token não encontrado. Verifique o arquivo .env."
        )

    ids = extrair_ids(link)

    item = obter_dados_produto(ids)

    if item.get("status") != "active":
        raise ArthurBotError(
            "Esse anúncio não está ativo."
        )

    seller_id = item.get("seller_id")

    if not seller_id:
        raise ArthurBotError(
            "Não foi possível identificar o vendedor."
        )

    avaliacoes = obter_avaliacoes(item["id"])

    vendedor = obter_vendedor(seller_id)

    analise = analisar_reputacao(
        avaliacoes,
        vendedor
    )

    produto = {
        "titulo": item.get("title"),
        "preco": item.get("price"),
        "moeda": item.get("currency_id"),
        "imagem": item.get("thumbnail"),
        "link": item.get("permalink"),
        "condicao": item.get("condition"),
        "avaliacoes": avaliacoes,
        "vendedor": vendedor,
        "analise": analise,
        "data": datetime.now().isoformat(timespec="seconds")
    }

    registrar_analise(produto)

    return produto


# ==========================================
# ROTAS DO FLASK
# ==========================================

@app.route("/")
def inicio():

    return render_template("index.html")


@app.route("/api/status")
def status():

    return jsonify({
        "servidor": "online",
        "arquivo_env": ARQUIVO_ENV.exists(),
        "token_carregado": bool(ACCESS_TOKEN),
        "banco_json": ARQUIVO_BANCO.exists()
    })

@app.route("/api/testar-link", methods=["POST"])
def testar_link():

    dados = request.get_json(silent=True) or {}
    link = dados.get("link", "").strip()

    try:
        url = resolver_link(link)

        partes = urlparse(url)

        return jsonify({
            "sucesso": True,
            "url_original": link,
            "url_final": url,
            "dominio": partes.hostname,
            "caminho": partes.path,
            "parametros": parse_qs(partes.query)
        })

    except Exception as erro:
        app.logger.exception("Erro ao resolver link")

        return jsonify({
            "sucesso": False,
            "erro": str(erro)
        }), 400

@app.route("/api/analisar", methods=["POST"])
def analisar():

    if not ACCESS_TOKEN:
        return jsonify({
            "sucesso": False,
            "erro": "Token não encontrado. Confira o arquivo .env."
        }), 500

    dados = request.get_json(silent=True) or {}

    link = dados.get("link", "").strip()

    if not link:
        return jsonify({
            "sucesso": False,
            "erro": "Informe o link do produto."
        }), 400

    try:

        produto = analisar_produto(link)

        return jsonify({
            "sucesso": True,
            "produto": produto
        })

    except ArthurBotError as erro:

        return jsonify({
            "sucesso": False,
            "erro": str(erro)
        }), 400

    except Exception as erro:

        app.logger.exception(
            "Erro inesperado durante a análise."
        )

        return jsonify({
            "sucesso": False,
            "erro": "Ocorreu um erro interno ao analisar o produto."
        }), 500


@app.route("/api/historico")
def historico():

    try:
        banco = carregar_banco()

        return jsonify({
            "sucesso": True,
            "historico": banco["historico"]
        })

    except Exception:
        app.logger.exception("Erro ao carregar histórico.")

        return jsonify({
            "sucesso": False,
            "erro": "Não foi possível carregar o histórico."
        }), 500


# ==========================================
# INICIAR SERVIDOR
# ==========================================

if __name__ == "__main__":

    print("--------------------------------")
    print("ARTHUR BOT")
    print("--------------------------------")

    print("Servidor: iniciando")
    print("Arquivo .env:", ARQUIVO_ENV.exists())
    print("Token carregado:", bool(ACCESS_TOKEN))
    print("Banco JSON:", ARQUIVO_BANCO.exists())

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )
