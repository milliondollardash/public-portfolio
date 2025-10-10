# generate_html.py
from datetime import datetime

with open("index.html", "w") as f:
    f.write(f"""
    <html>
      <head><title>Auto Updated Page</title></head>
      <body>
        <h1>Page updated at: {datetime.now()} UTC</h1>
      </body>
    </html>
    """)