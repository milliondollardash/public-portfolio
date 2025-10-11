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
                padding: 10px; 
                margin: 0; 
            }

            h1 { 
                text-align: center; 
                color: #00FF00; 
                font-family: 'Inter', sans-serif; 
                font-size: clamp(24px, 6vw, 48px);
                margin-bottom: 10px;
            }

            .timestamp { 
                text-align: center; 
                font-size: clamp(12px, 3vw, 16px); 
                margin-bottom: 20px; 
                color: #AAAAAA; 
            }

            .table-container {
                display: flex;
                justify-content: center;   /* keeps table centered */
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                margin: auto;
                max-width: 100%;
            }

            .portfolio-table { 
                display: table; 
                border-collapse: collapse; 
                width: auto;   /* shrink to fit content */
                min-width: 480px; /* keeps readability */
                margin: 0 auto;
            }
            .portfolio-row { display: table-row; }
            .portfolio-header { 
                display: table-row; 
                font-weight: bold; 
                border-bottom: 2px solid #00FF00;
            }
            .portfolio-cell, .portfolio-header-cell { 
                display: table-cell; 
                padding: 8px 10px; 
                text-align: center; 
                font-size: clamp(14px, 3.5vw, 20px);
            }
            .portfolio-header-cell { color: #00FF00; }

            .gain-positive { color: #00FF00; } 
            .gain-negative { color: #FF0000; } 
        </style>
        """

        # Format profit with colored spans
        df_html = df.copy()
        df_html['profit'] = df_html['profit'].apply(
            lambda x: f"<span class='gain-positive'>{x}%</span>" if '+' in x else
                      f"<span class='gain-negative'>-{x.replace('-', '')}%</span>" if '-' in x else x
        )

        # Timestamp + header
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"<h1>${total_port_value}</h1>\n<div class='timestamp'>Last updated: {timestamp}</div>"

        # Build table HTML
        columns = df_html.columns.tolist()
        html_rows = []

        # header row
        header_row = "<div class='portfolio-header'>" + "".join(
            f"<div class='portfolio-header-cell'>{col}</div>" for col in columns
        ) + "</div>"
        html_rows.append(header_row)

        # data rows
        for _, row in df_html.iterrows():
            row_html = "<div class='portfolio-row'>" + "".join(
                f"<div class='portfolio-cell'>{row[col]}</div>" for col in columns
            ) + "</div>"
            html_rows.append(row_html)

        html_table = "<div class='table-container'><div class='portfolio-table'>" + "".join(html_rows) + "</div></div>"

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
