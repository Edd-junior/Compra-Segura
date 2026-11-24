
async function analisarProduto() {

    const campo = document.getElementById("linkProduto");
    const resultado = document.getElementById("resultado");
    const botao = document.getElementById("botaoAnalisar");

    const link = campo.value.trim();

    if (!link) {
        resultado.innerHTML = `
            <div class="alert alert-warning">
                Informe o link de um produto.
            </div>
        `;
        return;
    }

    botao.disabled = true;
    botao.textContent = "Analisando...";

    resultado.innerHTML = `
        <p>Consultando informações do produto...</p>
    `;

    try {

        fetch("/api/testar-link", {
    method: "POST",
    headers: {
        "Content-Type": "application/json"
    },
    body: JSON.stringify({
        link: "https://meli.la/2XR6N1Z"
    })
})
.then(r => r.json())
.then(d => console.log(d));

        const resposta = await fetch("/api/analisar", {
            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                link: link
            })
        });

        const dados = await resposta.json();

        if (!resposta.ok || !dados.sucesso) {
            throw new Error(
                dados.erro || "Não foi possível analisar o produto."
            );
        }

        const produto = dados.produto;
        const analise = produto.analise;
        const vendedor = produto.vendedor;
        const avaliacoes = produto.avaliacoes;

        resultado.innerHTML = `
            <div class="card p-3">

                <h4>${produto.titulo || "Produto"}</h4>

                ${
                    produto.imagem
                    ? `<img src="${produto.imagem}"
                            alt="Imagem do produto"
                            style="max-width:180px">`
                    : ""
                }

                <p>
                    <strong>Preço:</strong>
                    ${produto.moeda || ""} ${produto.preco ?? "Não informado"}
                </p>

                <p>
                    <strong>Média de avaliações:</strong>
                    ${avaliacoes.media ?? "Não disponível"}
                </p>

                <p>
                    <strong>Total de avaliações:</strong>
                    ${avaliacoes.quantidade ?? "Não disponível"}
                </p>

                <hr>

                <h5>Vendedor</h5>

                <p>
                    <strong>Nome:</strong>
                    ${vendedor.apelido}
                </p>

                <p>
                    <strong>Reputação:</strong>
                    ${vendedor.positivas ?? "Não disponível"}
                </p>

                <hr>

                <h5>Resultado da análise</h5>

                <p>
                    <strong>Classificação:</strong>
                    ${analise.classificacao}
                </p>

                <p>
                    <strong>Indicador:</strong>
                    ${analise.pontuacao ?? "Indisponível"}
                </p>

                <p>${analise.mensagem}</p>

                <a href="${produto.link}"
                   target="_blank"
                   rel="noopener noreferrer">
                   Abrir anúncio original
                </a>

            </div>
        `;

    } catch (erro) {

        resultado.innerHTML = `
            <div class="alert alert-danger">
                ${erro.message}
            </div>
        `;

    } finally {

        botao.disabled = false;
        botao.textContent = "Analisar produto";
    }
}


async function carregarHistorico() {

    const area = document.getElementById("historico");

    area.innerHTML = "Carregando histórico...";

    try {

        const resposta = await fetch("/api/historico");

        const dados = await resposta.json();

        if (!resposta.ok || !dados.sucesso) {
            throw new Error("Não foi possível consultar o histórico.");
        }

        if (dados.historico.length === 0) {
            area.innerHTML = "Nenhum produto analisado ainda.";
            return;
        }

        area.innerHTML = dados.historico.map(item => `
            <div class="border rounded p-3 mb-2">
                <strong>${item.titulo || "Produto"}</strong>
                <p class="mb-1">${item.data || ""}</p>
                <a href="${item.link || "#"}"
                   target="_blank"
                   rel="noopener noreferrer">
                    Ver anúncio
                </a>
            </div>
        `).join("");

    } catch (erro) {

        area.innerHTML = `
            <div class="alert alert-danger">
                ${erro.message}
            </div>
        `;
    }
}
