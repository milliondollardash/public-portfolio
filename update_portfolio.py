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
                font-size: clamp(28px, 6vw, 48px); 
                font-weight: 600; 
                color: #00FFAA; 
                margin-bottom: 10px;
            }
            .timestamp { 
                text-align: center; 
                color: #AAAAAA; 
                font-size: 14px; 
                margin-bottom: 20px; 
            }

            /* --- Table / Cards --- */
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
                border-bottom: 2px solid #00FFAA; 
            }
            td { 
                padding: 6px 12px; 
                font-size: 18px; 
            }

            /* Row-based coloring */
            .tr-positive { 
                background-color: rgba(0, 255, 170, 0.05);  
            }
            .tr-negative { 
                background-color: rgba(255, 76, 76, 0.1);  
            }

            /* Profit coloring */
            .gain-positive { color: #00FFAA; font-weight: 600; }
            .gain-negative { color: #FF4C4C; font-weight: 600; }

    

            /* --- Mobile Card Layout --- */
            @media (max-width: 768px) {
                table, thead, tbody, th, td, tr {
                    display: block;
                    width: auto;
                }
                thead { display: none; }
                tr {
                    border-radius: 16px;
                    padding: 12px;
                    margin-bottom: 16px;
                    background-color: #1A1A1A;
                }
         
                td {
                    display: flex;
                    justify-content: space-between;
                    text-align: left;
                    font-size: clamp(14px, 4vw, 16px);
                    padding: 6px 8px;
                }
                td::before { 
                    content: attr(data-label); 
                    font-weight: 500; 
                    color: #AAAAAA; 
                    margin-right: 10px;
                }
            }
        </style>
        """

        # Color-code profit column
        df_html = df.copy()
 
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        header = f"<h1 class='portfolio-value'>${total_port_value}</h1>\n<div class='timestamp'>Last updated: {timestamp}</div>"

        # Build table rows with data-labels and row classes
        def build_rows(df):
            rows = []
            for _, row in df.iterrows():
                profit_val = str(row['profit'])
                row_class = "tr-positive" if '+' in profit_val else "tr-negative" if '-' in profit_val else ""

                def format_cell(col, val):
                    if col == "profit":
                        if val.startswith('+'):
                            return f'<td data-label="{col}"><span class="gain-positive">{val}</span></td>'
                        elif val.startswith('-'):
                            return f'<td data-label="{col}"><span class="gain-negative">{val}</span></td>'
                    return f'<td data-label="{col}">{val}</td>'

                tds = [format_cell(col, row[col]) for col in df.columns]
                rows.append(f"<tr class='{row_class}'>" + "".join(tds) + "</tr>")
            return "".join(rows)
        df_html['profit'] = df_html['profit'].apply(lambda x: f"{x:.2f}%" if isinstance(x, (int,float)) else x)
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
