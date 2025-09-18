from flask import Flask, render_template_string
import requests
import csv
import os
from datetime import datetime

app = Flask(__name__)
CSV_FILE = "cotacao_historico.csv"
API_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"

def fetch_cotacao():
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data["USDBRL"]["bid"]  # string
    except Exception as e:
        # Fallback: se a API falhar, retorna "N/D" para não quebrar a página
        app.logger.error(f"Erro buscando cotação: {e}")
        return "N/D"

def save_cotacao(cotacao: str):
    # Salva 1 vez por dia
    today = datetime.today().strftime("%Y-%m-%d")
    # cria header se não existir
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Data", "Cotacao"])
    # evita duplicar no dia
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        if any(today in line for line in f.readlines()):
            return
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([today, cotacao])

@app.route("/")
def index():
    cotacao = fetch_cotacao()
    if cotacao != "N/D":
        save_cotacao(cotacao)
    return f"""
    <h3>Cotação atual do dólar: R$ {cotacao}</h3>
    <a href="/historico">Ver histórico</a>
    """

@app.route("/historico")
def historico():
    historico_data = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader, None)  # pular header
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

# Health check leve (o Render usa 2xx/3xx como "saudável")
@app.route("/health")
def health():
    return "ok", 200

if __name__ == "__main__":
    # Execução local (Render usará gunicorn, ver abaixo)
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)
