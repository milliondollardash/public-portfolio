from dotenv import load_dotenv
import os
import requests
import pandas as pd
from datetime import datetime
from pathlib import Path
import logging

# --- Config ---
API_BASE = "https://api.public.com"
OUTPUT_FILE = "index.html"

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

load_dotenv()

# --- Load secret ---
PUBLIC_SECRET = os.getenv("PUBLIC_SECRET")
PORTFOLIO_ID = os.getenv("PORTFOLIO_ID")
if not PUBLIC_SECRET:
    raise ValueError("❌ No secret key found in environment variables!")




# --- API Functions ---
def get_access_token(validity_minutes: int = 120) -> str:
    """Request a temporary access token."""
    url = f"{API_BASE}/userapiauthservice/personal/access-tokens"
    payload = {"validityInMinutes": validity_minutes, "secret": PUBLIC_SECRET}
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status()
        return response.json()["accessToken"]
    except requests.RequestException as e:
        logging.error(f"Failed to get access token: {e}")
        raise


def get_portfolio(access_token: str) -> dict:
    """Fetch the user's portfolio from Public API."""
    url = f"{API_BASE}/userapigateway/trading/{PORTFOLIO_ID}/portfolio/v2"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        logging.error(f"Failed to fetch portfolio: {e}")
        raise


# --- Data Processing ---
def portfolio_to_df(portfolio_data: dict) -> pd.DataFrame:
    """Convert portfolio JSON into a DataFrame."""
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
            "profit": gain_perc,
            "day bought": datetime.fromisoformat(p["openedAt"].replace('Z', '+00:00')).date()
        })

    return pd.DataFrame(rows).sort_values(by="value", ascending=False).reset_index(drop=True)


# --- HTML Building ---
def build_style() -> str:
    return """<style>
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
            animation: flicker 1s ease-in-out;
        }

        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% {
                opacity: 1;
                text-shadow: 0 0 8px #4CAF50;  /* only green glow */
            }
            20%, 22%, 24%, 55% {
                opacity: 0.6;
                text-shadow: 0 0 4px #4CAF50;  /* smaller green glow */
            }
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
            background-color: #1E1E1E;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
            display: flex;
            flex-direction: column;
            gap: 8px;
            transition: background-color 0.3s ease, box-shadow 0.3s ease, transform 0.3s ease;

            opacity: 0;
            transform: translateY(40px) scale(0.95);
            animation: slideFadeScale 0.6s forwards;
            animation-delay: var(--delay, 0s);
            animation-timing-function: cubic-bezier(0.25, 1.2, 0.35, 1);
        }

        @keyframes slideFadeScale {
            0% {
                opacity: 0;
                transform: translateY(40px) scale(0.95);
            }
            60% {
                opacity: 1;
                transform: translateY(-10px) scale(1.03);
            }
            100% {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }

        .row-card:hover {
            transform: translateY(-5px) scale(1.02);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.6);
        }

        .row-card.positive { background-color: rgba(76, 175, 80, 0.15); }
        .row-card.negative { background-color: rgba(244, 67, 54, 0.15); }

        .row-content { display: flex; flex-direction: column; gap: 6px; }
        .symbol-row { display: flex; align-items: center; gap: 8px; }
        .symbol { font-size: clamp(26px, 8vw, 100px); font-weight: 700; color: #F5F5F5; text-transform: uppercase; }
        .arrow { display: inline-block; font-size: 3em; }
        .gain-positive { color: #4CAF50; }
        .gain-negative { color: #F44336; }
        .neutral-square { width: 16px; height: 16px; background-color: #9E9E9E; border-radius: 2px; }
        .value { font-size: clamp(32px, 10vw, 50px); font-weight: 600; color: #4CAF50; }
        .profit { font-size: clamp(16px, 4vw, 40px); }
        .day { font-size: clamp(14px, 3vw, 30px); color: #A0A0A0; text-align: right; }

        @media (min-width: 600px) {
            .row-card { max-width: 90%; padding: 25px; margin: 15px auto; }
        }
        </style>
        <link rel="shortcut icon" type="image/x-icon" href="mdd.PNG">

        <script>
        document.addEventListener("DOMContentLoaded", () => {
            const cards = document.querySelectorAll('.row-card');
            cards.forEach((card, index) => {
                card.style.setProperty('--delay', `${index * 0.08}s`);
            });
        });
        </script>
    """


def build_header(total_value: str) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"<h1 class='portfolio-value'>${total_value}</h1>\n" \
           f"<div class='timestamp'>last updated: {timestamp}</div>"


def build_rows(df: pd.DataFrame) -> str:
    """Generate HTML rows for each position."""
    rows = []
    for _, row in df.iterrows():
        profit_val = row['profit']

        if profit_val > 0:
            indicator_html = '<div class="arrow gain-positive">▲</div>'
            profit_cell = f'<div class="profit gain-positive">{profit_val:+.2f}%</div>'
            card_class = "row-card positive"
        elif profit_val < 0:
            indicator_html = '<div class="arrow gain-negative">▼</div>'
            profit_cell = f'<div class="profit gain-negative">{profit_val:+.2f}%</div>'
            card_class = "row-card negative"
        else:
            indicator_html = '<div class="arrow neutral-square"></div>'
            profit_cell = f'<div class="profit">{profit_val:+.2f}%</div>'
            card_class = "row-card"

        rows.append(f"""
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
        """)
    return "".join(rows)


def df_to_html(df: pd.DataFrame, total_value: str, filename: str = OUTPUT_FILE) -> None:
    """Convert DataFrame into styled HTML and write to file."""
    if df.empty:
        html_content = "<h2>No positions found</h2>"
    else:
        html_content = build_style() + build_header(total_value) + build_rows(df)

    Path(filename).write_text(html_content, encoding="utf-8")
    logging.info(f"✅ Portfolio exported as HTML: {filename}")


# --- Main workflow ---
def main() -> None:
    token = get_access_token()
    portfolio_data = get_portfolio(token)

    try:
        total_port_value = next(item['value'] for item in portfolio_data['equity'] if item['type'] == 'STOCK')
    except StopIteration:
        total_port_value = "0.00"

    df = portfolio_to_df(portfolio_data)
    df_to_html(df, total_port_value)


if __name__ == "__main__":
    main()