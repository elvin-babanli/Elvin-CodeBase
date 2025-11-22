# main/stock_predictor.py
import os, io, sys, time, requests
from dotenv import load_dotenv
from openai import OpenAI
from django.shortcuts import render

load_dotenv()

class Stock_Market:
    api_key = os.getenv("MARKETSTACK_API_KEY")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    def __init__(self, daily_data=None, stock_name=""):
        self.daily_data = daily_data or []
        self.stock_name = stock_name
    def get_data(self, stock_name=""):
        self.stock_name = (stock_name or "").strip().upper()
        url = "https://api.marketstack.com/v1/eod"
        params = {"access_key": self.api_key, "symbols": self.stock_name, "limit": 365}
        resp = requests.get(url, params=params, timeout=10)
        data = resp.json()
        self.daily_data = data.get("data", [])
        return self.daily_data
    def write_data(self, daily_data=None):
        daily_data = daily_data or self.daily_data
        with open("prediction.txt", "w", encoding="utf-8") as f:
            f.write("You are a financial prediction assistant.\n")
            f.write(f"Using ONLY the {self.stock_name} EOD data below, predict the expected closing price at the end of the next 5 trading days.\n")
            f.write("Return EXACTLY one number with two decimals (e.g., 251.20). No words, symbols, ranges or explanations.\n")
            f.write("If unsure, output your best single-point estimate. Do not say 'NA'.\n")
            f.write(f"Name of Stock: {self.stock_name}\n\n")
            for day in (daily_data or [])[:365]:
                d = day.get("date") or day.get("datetime") or ""
                o = day.get("adj_open") or day.get("open") or 0
                h = day.get("adj_high") or day.get("high") or 0
                l = day.get("adj_low")  or day.get("low")  or 0
                c = day.get("adj_close")or day.get("close") or 0
                v = day.get("adj_volume")or day.get("volume") or 0
                f.write(f"{d}  Open:{float(o):.2f} High:{float(h):.2f} Low:{float(l):.2f} Close:{float(c):.2f} Vol:{int(float(v))}\n")
    def predict_data(self):
        with open("prediction.txt", "r", encoding="utf-8") as f:
            content = f.read()
        # Burada sənin orijinal OpenAI çağırışın qalır
        resp = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": content},
            ],
        )
        print("Prediction:         ", "$", resp.choices[0].message.content)

def stock_predictor_view(request):
    symbol = (request.GET.get("symbol") or "").strip().upper()
    prediction = error = None
    rows = []
    if symbol:
        try:
            app = Stock_Market()
            daily = app.get_data(symbol)
            for d in (daily or [])[:10]:
                rows.append({
                    "date": d.get("date") or d.get("datetime") or "",
                    "open": d.get("adj_open") or d.get("open") or 0,
                    "high": d.get("adj_high") or d.get("high") or 0,
                    "low":  d.get("adj_low")  or d.get("low")  or 0,
                    "close":d.get("adj_close")or d.get("close") or 0,
                    "volume": int(float(d.get("adj_volume") or d.get("volume") or 0)),
                })
            # stdout capture (çünki predict_data print edir)
            old = sys.stdout
            sys.stdout = io.StringIO()
            try:
                app.write_data(daily)
                app.predict_data()
                printed = sys.stdout.getvalue()
            finally:
                sys.stdout = old
            for line in printed.splitlines():
                if "Prediction:" in line:
                    prediction = line.split("Prediction:",1)[1].strip()
                    break
            if not prediction:
                prediction = printed.strip() or "No output"
        except Exception as e:
            error = f"Error: {e}"
    return render(request, "stock_predictor.html", {
        "symbol": symbol, "prediction": prediction, "error": error, "rows": rows,
        "model_name": "gpt-4o-mini", "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

# CLI üçün istəsən:
if __name__ == "__main__":
    # buraya istəyinə görə while True qoyarsan, web-ə təsir etmir
    pass
