import requests
from bs4 import BeautifulSoup

def extrair_dados(url):
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)

    soup = BeautifulSoup(response.text, "html.parser")

    # Avaliação
    try:
        rating = soup.find("span", {"class": "a-icon-alt"}).text
        rating = float(rating.split(" ")[0].replace(",", "."))
    except:
        rating = None

    # Número de avaliações
    try:
        reviews = soup.find("span", {"id": "acrCustomerReviewText"}).text
        reviews = int(reviews.split(" ")[0].replace(".", ""))
    except:
        reviews = None

    return rating, reviews
