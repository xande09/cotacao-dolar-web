from flask import Flask, render_template_string
import requests

app = Flask(__name__)

@app.route("/")
def index():
    try:
        url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
        response = requests.get(url)
        data = response.json()
        cotacao = data['USDBRL']['bid']
        return render_template_string("""
            <html>
                <head>
                    <title>Cotação do Dólar</title>
                    <style>
                        body { font-family: Arial; text-align: center; margin-top: 50px; }
                        .cotacao { font-size: 24px; color: #2E8B57; }
                    </style>
                </head>
                <body>
                    <h1>Cotação Atual do Dólar</h1>
                    <p class="cotacao">R$ {{ cotacao }}</p>
                </body>
            </html>
        """, cotacao=cotacao)
    except Exception as e:
        return f"Erro ao buscar cotação: {e}"

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
