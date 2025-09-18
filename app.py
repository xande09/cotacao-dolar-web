from flask import Flask, render_template_string
import requests
import csv
import os
from datetime import datetime

app = Flask(__name__)

# Caminho do CSV (pode ajustar via variável de ambiente se quiser)
CSV_FILE = os.getenv("CSV_FILE", "cotacao_historico.csv")
API_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"


def fetch_cotacao() -> str:
    """Busca a cotação USD-BRL atual. Retorna string com o 'bid' ou 'N/D' em caso de erro."""
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data["USDBRL"]["bid"]  # vem como string
    except Exception as e:
        app.logger.error(f"Erro buscando cotação: {e}")
        return "N/D"


def ensure_csv_header(path: str):
    """Garante que o CSV exista com cabeçalho."""
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Data", "Cotacao"])


def save_cotacao(cotacao: str):
    """Salva a cotação 1x por dia (YYYY-MM-DD)."""
    if cotacao == "N/D":
        return
    today = datetime.today().strftime("%Y-%m-%d")
    ensure_csv_header(CSV_FILE)

    # evita duplicar o registro do dia
    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            if any(today in line for line in f.readlines()):
                return
    except FileNotFoundError:
        pass

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([today, cotacao])


@app.route("/")
def index():
    cotacao = fetch_cotacao()
    save_cotacao(cotacao)
    return f"""
    <h3>Cotação atual do dólar: R$ {cotacao}</h3>
    <p><a href="/historico">Ver histórico</a></p>
    """
@app.route("/historico")
def historico():
    historico_data = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # pula header, se existir
            historico_data = list(reader)

    html = """
    <h3>Histórico de Cotações</h3>
    <table border="1" cellpadding="6">
      <tr><th>Data</th><th>Cotação</th></tr>
      {% for row in data %}
        <tr><td>{{ row[0] }}</td><td>{{ row[1] }}</td></tr>
      {% endfor %}
    </table>
    <p><a href="/">Voltar</a></p>
    """
    return render_template_string(html, data=historico_data)


# Endpoint de health check para o Render (deve responder 2xx rapidamente)
@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    # Execução local. No Render usaremos gunicorn (ver comando de start).
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)
