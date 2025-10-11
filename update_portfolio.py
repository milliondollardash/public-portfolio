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
            "profit": f"{'+' if gain_perc>0 else '-' if gain_perc<0 else ''} {gain_perc:.2f}",
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
                font-family: 'Courier New', monospace; 
                background-color: #111111; 
                color: #00FF00; 
                padding: 20px; 
                margin: 0; 
            }

            h1 { 
                text-align: center; 
                color: #00FF00; 
                font-family: 'Inter', sans-serif; 
            }

            .timestamp { 
                text-align: center; 
                font-size: 16px; 
                margin-bottom: 20px; 
                color: #AAAAAA; 
            }

            table { 
                border-collapse: collapse; 
                margin: auto; 
                text-align: center; 
                border:none; 
                width: 80%;
            }
            th { 
                font-size: 20px; 
                padding: 8px 12px; 
                border:none; 
                border-bottom: 2px solid #00FF00; 
            }
            td { 
                padding: 6px 12px; 
                font-size: 18px; 
                border:none; 
            }
            .gain-positive { color: #00FF00; } 
            .gain-negative { color: #FF0000; }

            /* --- Responsive Card Layout for Mobile --- */
            @media (max-width: 600px) {
                table, thead, tbody, th, td, tr {
                    display: block;
                }
                thead { display: none; }
                tr {
                    margin-bottom: 16px;
                    border: 1px solid #00FF00;
                    border-radius: 10px;
                    padding: 10px;
                    background: #1a1a1a;
                }
                td {
                    display: flex;
                    justify-content: space-between;
                    text-align: left;
                    font-size: 16px;
                    padding: 6px 8px;
                }
                td::before {
                    content: attr(data-label);
                    font-weight: bold;
                    color: #AAAAAA;
                    margin-right: 10px;
                }
            }
        </style>
        """

        # Color-code profit column
        df_html = df.copy()
        df_html['profit'] = df_html['profit'].apply(
            lambda x: f"<span class='gain-positive'>{x}%</span>" if '+' in x else
                      f"<span class='gain-negative'>-{x.replace('-', '')}%</span>" if '-' in x else x
        )

        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"<h1>${total_port_value}</h1>\n<div class='timestamp'>Last updated: {timestamp}</div>"

        # Build table rows with data-labels for mobile cards
        def build_rows(df):
            rows = []
            for _, row in df.iterrows():
                tds = [f'<td data-label="{col}">{row[col]}</td>' for col in df.columns]
                rows.append("<tr>" + "".join(tds) + "</tr>")
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
