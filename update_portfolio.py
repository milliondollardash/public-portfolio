from dotenv import load_dotenv
import os
import requests
import pandas as pd
from datetime import datetime
import subprocess
import random

# --- Load secret from environment (GitHub Actions uses Secrets) ---
load_dotenv()

PUBLIC_SECRET = os.getenv("PUBLIC_SECRET")
if not PUBLIC_SECRET:
    raise ValueError("No secret key found in environment variables!")

repo_path = os.getcwd()  # GitHub Actions runs in the repo folder



def make_sparkline(data, width=100, height=30, stroke="#4CAF50"):
    if not data or len(data) < 2:
        return ""  # not enough data

    step_x = width / (len(data) - 1)

    min_y, max_y = min(data), max(data)
    if min_y == max_y:
        points = [(i * step_x, height / 2) for i in range(len(data))]
    else:
        scale = height / (max_y - min_y)
        points = [(i * step_x, height - (val - min_y) * scale) for i, val in enumerate(data)]

    points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    svg = f"""
    <svg width="{width}" height="{height}" viewBox="0 0 {width} {height}"
         xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
        <polyline fill="none" stroke="{stroke}" stroke-width="2"
                  points="{points_str}" />
    </svg>
    """
    return svg



# --- API Functions ---
def get_access_token(validity_minutes=123):
    url = "https://api.public.com/userapiauthservice/personal/access-tokens"
    headers = {"Content-Type": "application/json"}
    payload = {"validityInMinutes": validity_minutes, "secret": PUBLIC_SECRET}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()["accessToken"]

def get_portfolio(access_token):
    url = "https://api.public.com/userapigateway/trading/5LF69378/portfolio/v2"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()

# --- Build DataFrame with trophy and gains ---
def portfolio_to_df(portfolio_data):

    positions = portfolio_data.get("positions", [])
    if not positions:
        return pd.DataFrame()

    rows = []
    for p in positions:
        gain_perc = float(p["costBasis"]["gainPercentage"])
        symbol = p["instrument"]["symbol"]
        rows.append({
            "symbol": symbol,
            "value": f"${float(p['currentValue']):,.2f}",
            "profit": gain_perc,   # store as float
            "day bought": datetime.fromisoformat(p["openedAt"].replace('Z', '+00:00')).date()
        })

    
    df = pd.DataFrame(rows)
    df = df.sort_values(by="value", ascending=False).reset_index(drop=True)
    return df


def df_to_html(df, total_port_value, filename="index.html"):
    if df.empty:
        html_content = "<h2>No positions found</h2>"
    else:
        style = """
        <style>
        body {
            font-family: 'Inter', sans-serif;
            background-color: #121212;
            color: #E0E0E0;
            padding: 8px;
            margin: 0;
            line-height: 1.5;
            min-height: 100vh;
        }

        h1.portfolio-value {
            text-align: center;
            font-size: clamp(9em, 12vw, 12em);
            font-weight: 700;
            color: #4CAF50;
            margin-bottom: 5px;
            letter-spacing: -0.5px;
        }

        .timestamp {
            text-align: center;
            color: #9E9E9E;
            font-size: clamp(32px, 4vw, 36px);
            margin-bottom: 25px;
            font-family: monospace;
        }

        .row-card {
            border-radius: 12px;
            padding: 20px;
            margin: 8px auto;
            max-width: 98%;
            background-color: #1E1E1E;  /* default */
            # border: 1px solid #282828;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
            display: flex;
            flex-direction: column;
            gap: 8px;
            transition: background-color 0.3s ease, box-shadow 0.3s ease;
        }

        .row-card.positive {
            background-color: rgba(76, 175, 80, 0.15);  /* subtle green tint */
            # box-shadow: 0 4px 15px rgba(76, 175, 80, 0.3);
        }

        .row-card.negative {
            background-color: rgba(244, 67, 54, 0.15);  /* subtle red tint */
            # box-shadow: 0 4px 15px rgba(244, 67, 54, 0.3);
        }

        .row-content {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .symbol-row {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .symbol {
            font-size: clamp(26px, 8vw, 100px);
            font-weight: 700;
            color: #F5F5F5;
            text-transform: uppercase;
        }

        .arrow {
            display: inline-block;
            font-size: 3em;
        }

        .gain-positive {
            color: #4CAF50;
        }
        .gain-negative {
            color: #F44336;
        }
        .neutral-square {
            width: 16px;
            height: 16px;
            background-color: #9E9E9E;
            border-radius: 2px;
        }

        .value {
            font-size: clamp(32px, 10vw, 50px);
            font-weight: 600;
            color: #4CAF50;
        }

        .profit {
            font-size: clamp(16px, 4vw, 40px);
        }

        .day {
            font-size: clamp(14px, 3vw, 30px);
            color: #A0A0A0;
            text-align: right;
        }

        @media (min-width: 600px) {
            .row-card { max-width: 90%; padding: 25px; margin: 15px auto; }
        }
        </style>
        <link rel="shortcut icon" type="image/x-icon" href="mdd.PNG">
        """

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"<h1 class='portfolio-value'>${total_port_value}</h1>\n<div class='timestamp'>last updated: {timestamp}</div>"

        # Build card rows
        def build_rows(df):
            rows = []
            for _, row in df.iterrows():
                profit_val = row['profit']

                # Indicator after symbol
                if profit_val > 0:
                    indicator_html = '<div class="arrow gain-positive">▲</div>'
                elif profit_val < 0:
                    indicator_html = '<div class="arrow gain-negative">▼</div>'
                else:
                    indicator_html = '<div class="arrow neutral-square"></div>'

                # Profit formatting
                if profit_val > 0:
                    profit_cell = f'<div class="profit gain-positive">{profit_val:+.2f}%</div>'
                elif profit_val < 0:
                    profit_cell = f'<div class="profit gain-negative">{profit_val:+.2f}%</div>'
                else:
                    profit_cell = f'<div class="profit">{profit_val:+.2f}%</div>'

                # Determine card class based on profit
                if profit_val > 0:
                    card_class = "row-card positive"
                elif profit_val < 0:
                    card_class = "row-card negative"
                else:
                    card_class = "row-card"

                row_html = f"""
                <div class="{card_class}">
                    <div class="row-content">
                        <div class="symbol-row">
                            <div class="symbol">{row["symbol"]}</div>
                            {indicator_html}
                        </div>
                        <div class="value">{row["value"]}</div>
                        {profit_cell}
                        <div class="day">bought: {row["day bought"]}</div>
                    </div>
                </div>
                """

                rows.append(row_html)
            return "".join(rows)

        table_body = build_rows(df)
        html_content = style + header + table_body

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ Portfolio exported as HTML: {filename}")



# --- Main workflow ---
def main():
    token = get_access_token()
    portfolio_data = get_portfolio(token)
    total_port_value = next(item['value'] for item in portfolio_data['equity'] if item['type'] == 'STOCK')
    df = portfolio_to_df(portfolio_data)
    df_to_html(df, total_port_value)

if __name__ == "__main__":
    main()
