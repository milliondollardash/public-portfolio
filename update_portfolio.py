from dotenv import load_dotenv
import os
import requests
import pandas as pd
from datetime import datetime
import subprocess

# --- Load secret from environment (GitHub Actions uses Secrets) ---
load_dotenv()

PUBLIC_SECRET = os.getenv("PUBLIC_SECRET")
if not PUBLIC_SECRET:
    raise ValueError("No secret key found in environment variables!")

repo_path = os.getcwd()  # GitHub Actions runs in the repo folder

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
            /* --- Body & Fonts --- */
            body { 
                font-family: 'Inter', sans-serif; 
                background-color: #0D0D0D; 
                color: #FFFFFF; 
                padding: 20px; 
                margin: 0; 
            }

            /* --- Portfolio Header --- */
            h1.portfolio-value { 
                text-align: center; 
                font-size: 10em !important;  
                font-weight: 600; 
                color: #7fff01; 
                margin-bottom: 10px;
            }
            .timestamp { 
                text-align: center; 
                color: #AAAAAA; 
                font-size: 20px; 
                margin-bottom: 20px; 
            }

            /* --- Card-style layout for all screens --- */
            table, thead, tbody, th, td, tr { display: block; }
            thead { display: none; }

            tr {
                border-radius: 16px;
                padding: 16px;
                margin: 16px auto;  /* center cards */
                max-width: 100%;
                background-color: #1A1A1A;
                box-shadow: 0 2px 6px rgba(0,0,0,0.3);
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }

            td {
                display: block;
                text-align: center;
                margin: 4px 0;
            }
            td.symbol {
                font-size: clamp(24px, 6vw, 32px);  /* scales with viewport */
                font-weight: 700;
            }

            td.value {
                font-size: clamp(40px, 5vw, 28px);  
                font-weight: 600;
                margin-bottom: 8px;
            }

            td[data-label] {
                font-size: clamp(16px, 4vw, 25px);
                color: #CCCCCC;
            }
             td[data-label-time] {
                font-size: clamp(6px, 4vw, 15px);
                color: #CCCCCC;
            }

            .gain-positive { color: #00FFAA; font-weight: 600; }
            .gain-negative { color: #FF4C4C; font-weight: 600; }
        </style>
        """

        # Ensure profit column is numeric
        df_html = df.copy()
        df_html['profit'] = df_html['profit'].astype(float)

        # Header
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"<h1 class='portfolio-value'>${total_port_value}</h1>\n<div class='timestamp'>last updated: {timestamp}</div>"

        # Build table rows
        def build_rows(df):
            rows = []
            for _, row in df.iterrows():
                profit_val = row['profit']
                row_class = "tr-positive" if profit_val > 0 else "tr-negative" if profit_val < 0 else ""

                # Symbol and Value cells
                symbol_cell = f'<td class="symbol">{row["symbol"]}</td>'
                value_cell = f'<td class="value">{row["value"]}</td>'

                # Profit and Day Bought
                def format_cell(col, val):
                    if col == "profit":
                        val_str = f"{val:+.2f}%"
                        if val > 0:
                            return f'<td data-label="{col}"><span class="gain-positive">{val_str}</span></td>'
                        elif val < 0:
                            return f'<td data-label="{col}"><span class="gain-negative">{val_str}</span></td>'
                        else:
                            return f'<td data-label="{col}">{val_str}</td>'
                    if col == "day bought":
                        return f'<td data-label-time="{col}">bought: {val}</td>'
                    return ""

                profit_cell = format_cell("profit", profit_val)
                day_cell = format_cell("day bought", row["day bought"])

                tds = symbol_cell + value_cell + profit_cell + day_cell
                rows.append(f"<tr class='{row_class}'>{tds}</tr>")
            return "".join(rows)

        table_body = build_rows(df_html)
        table_headers = "".join([f"<th>{col}</th>" for col in df_html.columns])
        html_table = f"<table><thead><tr>{table_headers}</tr></thead><tbody>{table_body}</tbody></table>"

        html_content = style + header + html_table

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
