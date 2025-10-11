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
    /* --- Base Styles (Mobile-First) --- */
    body {
        font-family: 'Inter', sans-serif;
        background-color: #121212;
        color: #E0E0E0;
        padding: 20px; /* Reduced base padding for mobile */
        margin: 0;
        line-height: 1.5;
        min-height: 100vh; /* Ensures full background on small content pages */
    }

    /* --- Portfolio Header --- */
    h1.portfolio-value {
        text-align: center;
        /* Clamp ensures it scales well across all sizes */
        font-size: clamp(3.5em, 12vw, 6em);
        font-weight: 700;
        color: #4CAF50;
        margin-bottom: 5px;
        letter-spacing: -0.5px;
    }
    .timestamp {
        text-align: center;
        color: #9E9E9E;
        font-size: clamp(14px, 3vw, 16px);
        margin-bottom: 30px;
    }

    /* --- Card Structure (Responsive Table Hack) --- */
    table, thead, tbody, th, td, tr { display: block; }
    thead { display: none; }

    tr {
        /* Flex container for content */
        display: flex;
        flex-direction: column; /* Stack all content vertically on mobile */

        border-radius: 12px;
        padding: 16px; /* Slightly reduced padding for mobile space */
        margin: 12px auto;
        max-width: 90%; /* Occupy most of the screen */
        background-color: #1E1E1E;
        border: 1px solid #282828;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.4);
        cursor: pointer;
        transition: transform 0.2s ease-out, box-shadow 0.2s ease-out, background-color 0.2s;
    }
    tr:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 15px rgba(0, 0, 0, 0.6);
        background-color: #252525;
    }

    td {
        display: block; /* Ensures they act as separate rows inside the flex column */
        text-align: left;
        margin: 0; /* Resetting margin for cleaner flex spacing */
        padding: 4px 0;
    }

    /* --- Primary Info (Symbol and Value) --- */
    /* Target the first two TDs (Symbol and Value) to appear on one line */
    tr > td:nth-child(1),
    tr > td:nth-child(2) {
        display: flex; /* Make the TD contents flex */
        justify-content: space-between; /* Push symbol and value apart */
        align-items: center;
        padding: 8px 0;
        border-bottom: 1px solid #282828; /* Separator line */
    }

    td.symbol {
        font-size: clamp(22px, 6vw, 28px);
        font-weight: 700;
        color: #F5F5F5;
        text-transform: uppercase;
    }

    td.value {
        font-size: clamp(28px, 8vw, 32px);
        font-weight: 600;
        color: #4CAF50;
    }

    /* --- Secondary Info (Profit and Day Bought) --- */
    /* Target the last two TDs (Profit and Day Bought) to appear on one line */
    tr > td:nth-child(3),
    tr > td:nth-child(4) {
        display: flex; /* Make the TD contents flex */
        justify-content: space-between; /* Push label and value apart */
        align-items: center;
        padding: 4px 0;
        font-size: clamp(14px, 3vw, 16px);
        color: #A0A0A0;
    }

    td[data-label] {
        /* Profit Label */
        width: 50%;
        text-align: left;
    }

    td[data-label-time] {
        /* Day Bought Label */
        width: 50%;
        text-align: right;
    }

    /* --- Gain Colors --- */
    .gain-positive {
        color: #4CAF50;
        font-weight: 600;
    }
    .gain-negative {
        color: #F44336;
        font-weight: 600;
    }

    /* =================================================== */
    /* --- Desktop/Tablet Optimization (Media Query) --- */
    /* =================================================== */
    @media (min-width: 600px) {
        tr {
            /* On wider screens, restrict max width and center more cleanly */
            max-width: 550px;
            padding: 25px; /* More generous padding */
            margin: 15px auto;
        }

        /* Symbol and Value (Primary Info) */
        tr > td:nth-child(1),
        tr > td:nth-child(2) {
            padding: 10px 0;
        }
        td.symbol {
            font-size: 28px;
        }
        td.value {
            font-size: 36px;
        }

        /* Secondary Info (Profit and Day Bought) */
        tr > td:nth-child(3),
        tr > td:nth-child(4) {
            font-size: 16px;
            padding: 6px 0;
        }
    }
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
