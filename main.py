from analyzer import extrair_dados, calcular_confianca

url = input("Cole o link do produto da Amazon: ")

rating, reviews = extrair_dados(url)

print("\n--- RESULTADO ---")
print(f"⭐ Avaliação: {rating}")
print(f"📝 Avaliações: {reviews}")

resultado = calcular_confianca(rating, reviews)
print(f"🔎 Classificação: {resultado}")
