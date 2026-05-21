import requests
import csv
from datetime import datetime
import re
import os

# =============================
# TUOTTEET
# =============================
PRODUCTS = [
    {"code": "HLBY", "name": "HLBY"},
    {"code": "HLBQ", "name": "HLBQ"},
    {"code": "HLBM", "name": "HLBM"},
    {"code": "NSBY", "name": "NSBY"},
    {"code": "NSBQ", "name": "NSBQ"},
    {"code": "NSBM", "name": "NSBM"},
]

BASE_URL = "https://live.euronext.com/en/ajax/getPricesFutures/commodities-futures/{code}/DAMS"

HEADERS = {"User-Agent": "Mozilla/5.0"}


# =============================
# CLEAN HTML
# =============================
def clean_html(text):
    return re.sub("<.*?>", "", text).strip()


# =============================
# PRODUCT CODE
# =============================
def build_product_code(product, delivery):
    if not delivery:
        return None

    d = delivery.strip()

    if d.lower() == "total":
        return None

    parts = d.split()

    # Vuosi
    if len(parts) == 1:
        return f"{product}-{d[-2:]}"

    year = parts[-1]
    yy = year[-2:]
    first = parts[0].upper()

    # Quarter
    if first.startswith("Q"):
        return f"{product}{first[1]}-{yy}"

    # Month
    month = first[:3]

    return f"{product}{month}-{yy}"


# =============================
# SCRAPER
# =============================
def scrape_api():
    all_rows = []
    headers = []
    header_written = False

    today = datetime.utcnow().strftime("%Y-%m-%d")

    for product in PRODUCTS:
        url = BASE_URL.format(code=product["code"])
        name = product["name"]

        print(f"\n🔎 Hakee: {url}")

        response = requests.get(url, headers=HEADERS)

        html = response.text

        # HEADER
        if not header_written:
            header_match = re.findall(r"<th.*?>(.*?)</th>", html)
            headers = [clean_html(h) for h in header_match]
            headers.extend(["Product", "ProductCode", "Date"])
            header_written = True

        # ROWS
        rows = re.findall(r"<tr.*?>(.*?)</tr>", html, re.DOTALL)

        for row in rows:
            cols = re.findall(r"<td.*?>(.*?)</td>", row, re.DOTALL)
            cols = [clean_html(c) for c in cols]

            if len(cols) < 5:
                continue

            delivery = cols[0]

            if (
                delivery == ""
                or delivery.lower() == "total"
                or "/" in delivery
            ):
                continue

            product_code = build_product_code(name, delivery)

            full_row = cols + [name, product_code, today]
            all_rows.append(full_row)

    return headers, all_rows


# =============================
# WRITE FILES
# =============================
def write_files(headers, all_rows):

    # ✅ 1. latest (overwrite)
    with open("latest_settlement.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(all_rows)

    print("✅ latest_settlement.csv päivitetty")

    # ✅ 2. historical (append)
    file_exists = os.path.isfile("historical_settlement.csv")

    with open("historical_settlement.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(headers)

        writer.writerows(all_rows)

    print("✅ historical_settlement.csv päivitetty")


# =============================
# REPORTS
# =============================
def generate_reports():
    import pandas as pd

    try:
        df = pd.read_csv("historical_settlement.csv")
    except:
        print("❌ Ei dataa raportointiin")
        return

    df["Settl."] = df["Settl."].str.replace(",", "")
    df["Settl."] = pd.to_numeric(df["Settl."], errors="coerce")

    df["Date"] = pd.to_datetime(df["Date"])

    today = df["Date"].max()
    yesterday = today - pd.Timedelta(days=1)

    # DAILY
    today_df = df[df["Date"] == today]
    yest_df = df[df["Date"] == yesterday]

    merged = pd.merge(
        today_df,
        yest_df,
        on="ProductCode",
        suffixes=("_today", "_yesterday"),
        how="left"
    )

    merged["Change"] = merged["Settl._today"] - merged["Settl._yesterday"]

    daily_report = merged.sort_values("Change", ascending=False).head(10)

    # WEEKLY
    week_df = df[df["Date"] >= today - pd.Timedelta(days=7)]

    weekly_avg = week_df.groupby("ProductCode")["Settl."].mean().reset_index()
    weekly_latest = today_df[["ProductCode", "Settl."]]

    weekly = pd.merge(weekly_latest, weekly_avg, on="ProductCode")
    weekly["Trend"] = weekly["Settl."] - weekly["Settl._y"]

    weekly_report = weekly.sort_values("Trend", ascending=False).head(10)

    # WRITE
    with open("daily_report.txt", "w") as f:
        f.write(daily_report.to_string(index=False))

    with open("weekly_report.txt", "w") as f:
        f.write(weekly_report.to_string(index=False))

    print("✅ Raportit luotu")


# =============================
# RUN
# =============================
if __name__ == "__main__":
    headers, rows = scrape_api()
    write_files(headers, rows)
    generate_reports()
