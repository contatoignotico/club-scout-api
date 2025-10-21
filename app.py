import os, uuid, time
from flask import Flask, request, jsonify, send_from_directory
import pandas as pd

app = Flask(__name__)

# Pasta temporária para exportar arquivos (existe em Render e é apagada no reboot)
EXPORT_DIR = "/tmp/exports"
os.makedirs(EXPORT_DIR, exist_ok=True)

@app.route("/")
def home():
    return "Club Scout API is running!"

@app.route("/coletar", methods=["POST"])
def coletar():
    data = request.get_json(force=True) if request.data else {}
    league_name = data.get("league_name", "Liga Desconhecida")
    league_url  = data.get("league_url", "N/A")

    # TODO: aqui entra a coleta real; por enquanto, dados de exemplo
    time.sleep(1)
    clubes = [
        {"club_name": "Clube A", "country": "Brasil", "official_website": "https://exemplo-a.com", "emails_found": "contato@exemplo-a.com", "instagram": "https://instagram.com/exemploa"},
        {"club_name": "Clube B", "country": "Brasil", "official_website": "https://exemplo-b.com", "emails_found": "comercial@exemplo-b.com", "instagram": "https://instagram.com/exemplob"},
        {"club_name": "Clube C", "country": "Brasil", "official_website": "https://exemplo-c.com", "emails_found": None, "instagram": None},
    ]
    df = pd.DataFrame(clubes).fillna("N/A")

    # Gera arquivo único
    token = uuid.uuid4().hex[:10]
    safe_league = league_name.replace(" ", "_").lower()
    filename = f"leads_{safe_league}_{token}.xlsx"
    filepath = os.path.join(EXPORT_DIR, filename)
    df.to_excel(filepath, index=False)

    # Monta URL de download no seu próprio domínio Render
    # ex.: https://club-scout-api.onrender.com/download/leads_xxx.xlsx
    base = request.url_root.rstrip("/")  # inclui https://.../
    download_url = f"{base}/download/{filename}"

    summary = f"Foram processados {len(df)} clubes para a liga {league_name}."
    return jsonify({"summary": summary, "download_url": download_url})

@app.route("/download/<path:fname>", methods=["GET"])
def download(fname):
    # Serve o arquivo gerado como anexo
    return send_from_directory(EXPORT_DIR, fname, as_attachment=True)

if __name__ == "__main__":
    # Render injeta PORT, mas como estamos usando o start command `python app.py`,
    # manter porta fixa não é necessário (Render faz proxy). Ainda assim, OK:
    app.run(host="0.0.0.0", port=10000)
