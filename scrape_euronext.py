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
        
    # ✅ pakota stringiksi ensin
    df["Settl."] = df["Settl."].astype(str)

    # ✅ siivoa
    df["Settl."] = df["Settl."].str.replace(",", "", regex=False)
    df["Settl."] = df["Settl."].replace("-", None)

    # ✅ numeroksi
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

    weekly = pd.merge(weekly_latest, weekly_avg, on="ProductCode",suffixes=("_latest", "_avg"))
    weekly["Trend"] = weekly["Settl._latest"] - weekly["Settl._avg"]

    weekly_report = weekly.sort_values("Trend", ascending=False).head(10)

    # WRITE
    with open("daily_report.txt", "w") as f:
        f.write(daily_report.to_string(index=False))

    with open("weekly_report.txt", "w") as f:
        f.write(weekly_report.to_string(index=False))

    print("✅ Raportit luotu")
def generate_summary():
    import pandas as pd

    try:
        df = pd.read_csv("historical_settlement.csv")
    except:
        print("❌ Ei dataa summaryyn")
        return

    df["Settl."] = df["Settl."].astype(str)
    df["Settl."] = df["Settl."].str.replace(",", "", regex=False)
    df["Settl."] = df["Settl."].replace("-", None)
    df["Settl."] = pd.to_numeric(df["Settl."], errors="coerce")

    df = df.dropna(subset=["Settl."])
    df["Date"] = pd.to_datetime(df["Date"])

    today = df["Date"].max()
    yesterday = today - pd.Timedelta(days=1)

    today_df = df[df["Date"] == today]
    yest_df = df[df["Date"] == yesterday]

    # merge daily change
    merged = pd.merge(
        today_df,
        yest_df,
        on="ProductCode",
        suffixes=("_today", "_yesterday"),
        how="left"
    )

    merged["Change"] = merged["Settl._today"] - merged["Settl._yesterday"]

    # isoimmat liikkeet
    biggest_up = merged.sort_values("Change", ascending=False).head(3)
    biggest_down = merged.sort_values("Change").head(3)

    # valitaan yksi esimerkkituote (front)
    main = merged.dropna().head(1)

    # =============================
    # TEKSTI
    # =============================
    text = []
    text.append("Päivittäinen markkinakatsaus:\n")
    text.append("Pohjoismaiset sähköfutuurit liikkuivat tänään vaihtelevasti.\n")

    # front month
    if not main.empty:
        row = main.iloc[0]
        text.append(
            f"Lähituote {row['ProductCode']} "
            f"{row['Settl._today']:.2f} EUR/MWh "
            f"({row['Change']:+.2f}).\n"
        )

    # nousijat
    text.append("\nSuurimmat nousijat:\n")
    for _, r in biggest_up.iterrows():
        if pd.notna(r["Change"]):
            text.append(f"- {r['ProductCode']}: {r['Change']:+.2f}\n")

    # laskijat
    text.append("\nSuurimmat laskijat:\n")
    for _, r in biggest_down.iterrows():
        if pd.notna(r["Change"]):
            text.append(f"- {r['ProductCode']}: {r['Change']:+.2f}\n")

    # viikon trendi
    week_df = df[df["Date"] >= today - pd.Timedelta(days=7)]
    avg = week_df.groupby("ProductCode")["Settl."].mean().reset_index()
    latest = today_df[["ProductCode", "Settl."]]

    weekly = pd.merge(
        latest,
        avg,
        on="ProductCode",
        suffixes=("_latest", "_avg")
    )

    weekly["Trend"] = weekly["Settl._latest"] - weekly["Settl._avg"]

    trend_mean = weekly["Trend"].mean()

    text.append("\nViikkotrendi: ")
    if trend_mean > 0:
        text.append("markkina on keskimäärin nousutrendissä.\n")
    elif trend_mean < 0:
        text.append("markkina on keskimäärin laskutrendissä.\n")
    else:
        text.append("markkina on sivuttaisliikkeessä.\n")

    # write file
    with open("market_summary.txt", "w") as f:
        f.write("".join(text))

    print("✅ Copilot summary luotu!")
def calculate_spark_spread():

    import pandas as pd

    try:
        power = pd.read_csv("latest_settlement.csv")
        fuels = pd.read_csv("latest_fuels.csv")
    except:
        print("❌ Ei dataa spreadiin")
        return

    # =============================
    # ✅ CLEAN POWER
    # =============================
    power["Settl."] = power["Settl."].astype(str)
    power["Settl."] = power["Settl."].str.replace(",", "", regex=False)
    power["Settl."] = power["Settl."].replace("-", None)
    power["Settl."] = pd.to_numeric(power["Settl."], errors="coerce")

    power = power.dropna(subset=["Settl.", "ProductCode"])

    # =============================
    # ✅ HAE GAS
    # =============================
    fuels["Last"] = pd.to_numeric(fuels["Last"], errors="coerce")

    gas_row = fuels[fuels["Product"] == "NATGAS"]

    if gas_row.empty or pd.isna(gas_row["Last"].iloc[0]):
        print("⚠️ Gas price puuttuu")
        return

    gas_price = gas_row["Last"].iloc[0]

    print(f"✅ Gas price käytössä: {gas_price}")

    # =============================
    # ✅ SPARK
    # =============================
    power["SparkSpread"] = power["Settl."] - gas_price

    top = power.sort_values("SparkSpread", ascending=False).head(10)

    # =============================
    # ✅ WRITE
    # =============================
    with open("spark_spread.txt", "w") as f:
        f.write("Spark Spread (Power - Gas)\n\n")
        f.write(f"Gas price: {gas_price}\n\n")
        f.write(top[["ProductCode", "Settl.", "SparkSpread"]].to_string(index=False))

    print("✅ Spark spread laskettu")
def calculate_dark_spread():

    import pandas as pd

    try:
        power = pd.read_csv("latest_settlement.csv")
        fuels = pd.read_csv("latest_fuels.csv")
    except:
        print("❌ Ei dataa dark spreadiin")
        return

    # =============================
    # ✅ CLEAN POWER
    # =============================
    power["Settl."] = power["Settl."].astype(str)
    power["Settl."] = power["Settl."].str.replace(",", "", regex=False)
    power["Settl."] = power["Settl."].replace("-", None)
    power["Settl."] = pd.to_numeric(power["Settl."], errors="coerce")

    power = power.dropna(subset=["Settl.", "ProductCode"])

    # =============================
    # ✅ HAE COAL + CO2
    # =============================
    fuels["Last"] = pd.to_numeric(fuels["Last"], errors="coerce")

    coal_row = fuels[fuels["Product"] == "COAL"]
    co2_row = fuels[fuels["Product"] == "CO2"]

    if coal_row.empty or co2_row.empty:
        print("⚠️ Coal tai CO2 puuttuu")
        return

    coal_price = coal_row["Last"].iloc[0]
    co2_price = co2_row["Last"].iloc[0]

    if pd.isna(coal_price) or pd.isna(co2_price):
        print("⚠️ Coal/CO2 arvo puuttuu")
        return

    print(f"✅ Coal price: {coal_price}")
    print(f"✅ CO2 price: {co2_price}")

    # =============================
    # ✅ DARK SPREAD
    # =============================
    power["DarkSpread"] = power["Settl."] - (coal_price + co2_price)

    top = power.sort_values("DarkSpread", ascending=False).head(10)

    # =============================
    # ✅ WRITE
    # =============================
    with open("dark_spread.txt", "w") as f:
        f.write("Dark Spread (Power - Coal - CO2)\n\n")
        f.write(f"Coal price: {coal_price}\n")
        f.write(f"CO2 price: {co2_price}\n\n")
        f.write(top[["ProductCode", "Settl.", "DarkSpread"]].to_string(index=False))

    print("✅ Dark spread laskettu")

# POLTTOAINETESTI

def scrape_fuels():

    import requests

    today = datetime.utcnow().strftime("%Y-%m-%d")
    rows = []

    SYMBOLS = {
        "WTI_OIL": "cl.f",
        "BRENT_OIL": "cb.f",
        "NATGAS": "tg.f",
        "CO2": "ev.f",
        "COAL": "lu.f"
    }

    for name, symbol in SYMBOLS.items():

        print(f"🔎 Hakee {name} (Stooq)")

        try:
            
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/csv"
            }

            # =============================
            # ✅ LAST (intraday)
            # =============================
            url_last = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
            r_last = requests.get(url_last, headers=headers)

            last_price = None

            lines = r_last.text.splitlines()
            if len(lines) >= 2:
                data = lines[1].split(",")
                if len(data) > 6:
                    last_price = data[6] or None

            # =============================
            # ✅ CLOSE + PREVIOUS CLOSE
            # =============================
            url_hist = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
            r_hist = requests.get(url_hist, headers=headers)
            print(f"{name} HIST RAW:\n{r_hist.text[:200]}")

            close_price = None
            prev_close = None

            lines = [line for line in r_hist.text.splitlines() if line.strip()]

            
            if len(lines) >= 2:
                last_row = lines[-1].split(",")

                close_price = last_row[4] if len(last_row) > 4 else None

                if len(lines) >= 3:
                    prev_row = lines[-2].split(",")
                    prev_close = prev_row[4] if len(prev_row) > 4 else None


            # =============================
            # ✅ CONVERSIONS
            # =============================
            def to_float(x):
                try:
                    return float(x)
                except:
                    return None

            last_f = to_float(last_price)
            close_f = to_float(close_price)
            prev_f = to_float(prev_close)

            intraday_change = None
            daily_change = None

            if last_f is not None and close_f is not None:
                intraday_change = last_f - close_f

            if close_f is not None and prev_f is not None:
                daily_change = close_f - prev_f

            rows.append([
                name,
                symbol,
                last_price,
                close_price,
                prev_close,
                intraday_change,
                daily_change,
                today
            ])

        except Exception as e:
            print(f"⚠️ {name} fail: {e}")

    # =============================
    # ✅ FALLBACK (jos kaikki failaa)
    # =============================
    if not rows:
        print("❌ fuels ei saatu – fallback")

        rows = [
            ["WTI_OIL", "cl.f", None, None, None, None, None, today],
            ["BRENT_OIL", "cb.f", None, None, None, None, None, today],
            ["NATGAS", "tg.f", None, None, None, None, None, today],
            ["CO2", "ev.f", None, None, None, None, None, today],
            ["COAL", "lu.f", None, None, None, None, None, today],
        ]

    # =============================
    # ✅ WRITE CSV
    # =============================
    with open("latest_fuels.csv", "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "Product",
            "Symbol",
            "Last",
            "Close",
            "PrevClose",
            "IntradayChange",
            "DailyChange",
            "Date"
        ])

        writer.writerows(rows)

    file_exists = os.path.isfile("historical_fuels.csv")

    with open("historical_fuels.csv", "a", newline="") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "Product",
                "Symbol",
                "Last",
                "Close",
                "PrevClose",
                "IntradayChange",
                "DailyChange",
                "Date"
            ])

        writer.writerows(rows)

    print("✅ fuels (last + close + trends) päivitetty")
def generate_market_analysis():

    # =============================
    # ✅ lue tiedostot
    # =============================
    try:
        with open("market_summary.txt", "r") as f:
            summary = f.read()
    except:
        summary = "Ei summary dataa.\n"

    try:
        with open("spark_spread.txt", "r") as f:
            spark = f.read()
    except:
        spark = "Ei spark spread dataa.\n"

    try:
        with open("dark_spread.txt", "r") as f:
            dark = f.read()
    except:
        dark = "Ei dark spread dataa.\n"

    # =============================
    # ✅ yhdistä raportti
    # =============================
    report = []

    report.append("MARKET ANALYSIS\n")
    report.append("=" * 50 + "\n\n")

    report.append("Power Market Summary\n")
    report.append("-" * 30 + "\n")
    report.append(summary + "\n\n")

    report.append("Spark Spread (Gas-based)\n")
    report.append("-" * 30 + "\n")
    report.append(spark + "\n\n")

    report.append("Dark Spread (Coal-based)\n")
    report.append("-" * 30 + "\n")
    report.append(dark + "\n")

    # =============================
    # ✅ write file
    # =============================
    with open("market_analysis.txt", "w") as f:
        f.write("".join(report))

    print("✅ Yhdistetty market report luotu!")
# =============================
# RUN
# =============================
if __name__ == "__main__":
    headers, rows = scrape_api()
    write_files(headers, rows)
    

    try:
        scrape_fuels()
    except Exception as e:
        print(f"⚠️ fuels epäonnistui mutta jatketaan: {e}")

    generate_reports()
    generate_summary()
    calculate_spark_spread()
    calculate_dark_spread()
    generate_market_analysis()
