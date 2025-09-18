from flask import Flask, render_template_string, request, abort
import requests
import csv
import os
from datetime import datetime
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

app = Flask(__name__)

# =========================
# Configurações / Constantes
# =========================
CSV_FILE = os.getenv("CSV_FILE", "cotacao_historico.csv")
API_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
JOB_TOKEN = os.getenv("JOB_TOKEN", "")

# URL pública do seu app (opcional, usada para link no e-mail)
# Ex.: https://seuapp.onrender.com
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

# SMTP (e-mail)
SMTP_HOST = os.getenv("SMTP_HOST", "")          # ex.: smtp.gmail.com ou smtp.office365.com
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))  # 587 (STARTTLS)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER or "")
SMTP_TO = os.getenv("SMTP_TO", "")              # pode ser múltiplos separados por vírgula


# =========================
# Funções auxiliares
# =========================
def fetch_cotacao() -> str:
    """Busca a cotação USD-BRL atual (string 'bid'). Retorna 'N/D' em caso de erro."""
    try:
        resp = requests.get(API_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data["USDBRL"]["bid"]  # string, ex.: '5.4321'
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
    """Salva a cotação 1x por dia (YYYY-MM-DD). Não duplica o registro do dia."""
    if cotacao == "N/D":
        return
    today = datetime.today().strftime("%Y-%m-%d")
    ensure_csv_header(CSV_FILE)

    try:
        with open(CSV_FILE, "r", encoding="utf-8") as f:
            if any(today in line for line in f.readlines()):
                return  # já salvo hoje
    except FileNotFoundError:
        pass

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([today, cotacao])


def last_two_quotes(path: str = CSV_FILE):
    """Retorna as duas últimas linhas (Data, Cotacao) do CSV ou lista vazia."""
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # pular header
        rows = list(reader)
    return rows[-2:] if len(rows) >= 2 else rows


def send_email(subject: str, html_body: str, text_body: Optional[str] = None) -> bool:
    """Envia e‑mail via SMTP STARTTLS (porta 587). Retorna True se enviado, False se não configurado."""
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS and SMTP_TO):
        app.logger.warning("SMTP não configurado: e-mail NÃO será enviado.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = SMTP_TO
    # versão texto (fallback) e HTML
    text_body = text_body or html_body
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.starttls(context=context)
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)

    return True


# =========================
# Rotas
# =========================
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


@app.route("/health")
def health():
    return "ok", 200


@app.route("/job/salvar-cotacao")
def job_salvar_cotacao():
    """
    Endpoint para o agendador externo (cron) chamar 1x/dia.
    Uso: GET /job/salvar-cotacao?token=SEU_TOKEN
    """
    token = request.args.get("token", "")
    if not JOB_TOKEN or token != JOB_TOKEN:
        abort(401)

    cotacao = fetch_cotacao()
    status = "api_indisponivel"

    if cotacao != "N/D":
        # salva a cotação do dia (não duplica)
        save_cotacao(cotacao)
        status = "ok"

        # calcular variação vs. dia anterior (se houver)
        variacao_txt = ""
        try:
            lt = last_two_quotes()
            # após salvar hoje: se há 2 linhas, a penúltima é o dia anterior
            if len(lt) == 2:
                anterior = float(str(lt[0][1]).replace(",", "."))
                atual = float(str(lt[1][1]).replace(",", "."))
                delta = atual - anterior
                pct = (delta / anterior * 100) if anterior else 0.0
                sinal = "+" if delta >= 0 else "-"
                variacao_txt = f"{sinal}R$ {abs(delta):.4f} ({sinal}{abs(pct):.2f}%) vs. dia anterior"
        except Exception as e:
            app.logger.warning(f"Falha ao calcular variação: {e}")

        # montar e enviar e‑mail
        subject = f"Cotação USD/BRL de hoje: R$ {cotacao}"

        link_hist = f"{PUBLIC_BASE_URL}/historico" if PUBLIC_BASE_URL else ""
        link_html = f'<p><a href="{link_hist}">Ver histórico</a></p>' if link_hist else ""

        html = f"""
        <h3>Cotação USD/BRL</h3>
        <p><b>Hoje:</b> R$ {cotacao}</p>
        <p>{variacao_txt}</p>
        <hr>
        {link_html}
        """

        try:
            send_email(subject, html)
        except Exception as e:
            app.logger.error(f"Erro ao enviar e-mail: {e}")

    return {"status": status, "cotacao": cotacao}, (200 if status == "ok" else 503)


# =========================
# Execução local (Render usa gunicorn)
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)


 
