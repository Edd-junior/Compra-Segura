import re
from urllib.parse import urlparse
from flask import Flask, request, jsonify, send_from_directory


app = Flask(__name__)

# Lista de lojas conhecidas
LOJAS_CONFIAVEIS = {
    "amazon.com.br", "mercadolivre.com.br", "magazineluiza.com.br", 
    "casasbahia.com.br", "americanas.com.br", "shopee.com.br", 
    "aliexpress.com", "shein.com", "netshoes.com.br"
}

def extrair_dominio(url):
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    dominio = urlparse(url).netloc
    return dominio.replace('www.', '')

def suspeita_ser_loja(url):
    padrao_loja = re.compile(r'(loja|shop|store|ecommerce|produto|item|p\/|dp\/)', re.IGNORECASE)
    return bool(padrao_loja.search(url))

def analisar_mensagem(texto):
    # Extrai o primeiro link encontrado no texto
    urls = re.findall(r'(https?://[^\s]+)', texto)
    if not urls:
        return None # Nenhum link enviado
        
    link = urls[0]
    dominio = extrair_dominio(link)
    
    if dominio in LOJAS_CONFIAVEIS or suspeita_ser_loja(link):
        return f"🛍️ Identifiquei um link de loja online: {dominio}"
    return "🌐 Enviaste um link, mas não parece ser de uma loja cadastrada."

# Rota para abrir o seu arquivo HTML principal
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

# Rota de API que o JavaScript do HTML vai acionar
@app.route('/api/mensagem', methods=['POST'])
def receber_mensagem():
    data = request.json or {}
    texto_usuario = data.get('mensagem', '').strip()
    
    if not texto_usuario:
        return jsonify({"resposta": "Por favor, digite alguma coisa! ✍️"})
        
    # Executa a análise do Python
    resultado_analise = analisar_mensagem(texto_usuario)
    
    # Se não for link, devolve uma resposta padrão
    if not resultado_analise:
        resultado_analise = f"Recebi a sua mensagem! Se quiser testar o analisador, envie um link de e-commerce."
        
    return jsonify({"resposta": resultado_analise})

if __name__ == '__main__':
    app.run(debug=True, port=5000)

