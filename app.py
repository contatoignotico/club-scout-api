from flask import Flask, request, jsonify
import pandas as pd
import random
import time

app = Flask(__name__)

@app.route('/')
def home():
    return "Club Scout API is running!"

@app.route('/coletar', methods=['POST'])
def coletar():
    data = request.get_json(force=True)
    league_name = data.get("league_name", "Liga Desconhecida")
    league_url = data.get("league_url", "N/A")

    # Simula a coleta (a parte real do scraping seria implementada aqui)
    time.sleep(3)
    clubes = [
        {"club_name": "Clube A", "country": "Brasil", "email": "contato@clubea.com"},
        {"club_name": "Clube B", "country": "Brasil", "email": "comercial@clubeb.com"},
        {"club_name": "Clube C", "country": "Brasil", "email": None},
    ]

    df = pd.DataFrame(clubes)
    file_name = f"leads_{league_name.replace(' ', '_').lower()}.xlsx"
    df.to_excel(file_name, index=False)

    # Como o Render não mantém arquivos, simulamos um link de download
    fake_link = f"https://example.com/{file_name}"

    return jsonify({
        "summary": f"Foram processados {len(clubes)} clubes para a liga {league_name}.",
        "download_url": fake_link
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
