"""
Patch briefing_latest.json to add insightCharts[] to every industry.

Fixes the critical data gap identified in docs/_tmp_data_gap_audit.md:
all 20 industries render "No insight chart available" in the Industries tab.

Each chart uses a single real series from docs/data/timeseries.json, matching
the sector's most material price/rate driver (wheat for agri, WTI for mining,
BoC rate for retail, etc.). Schema matches what _loadChartSpecSeries and
renderIndInsightChart consume.
"""
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
BRIEFING = ROOT / "docs/data/briefing_latest.json"

# Each entry: (dataKey, dataSource, chartTitle, chartSubtitle, reasoning)
# dataSource="timeseries" reads docs/data/timeseries.json (daily market data).
# dataSource="indicators" reads docs/data/indicators.json history (monthly).
# Rule of thumb: use indicators when timeseries.json coverage is thin or stale
# (boc_rate/tsx_composite have only 2 points in timeseries; lumber ends 2023).
INDUSTRY_CHARTS = {
    "11": (
        "wheat", "timeseries",
        "Wheat futures \u2014 12-month trajectory",
        "CBOT continuous contract \u00b7 USD per bushel",
        "Wheat futures track the price cycle facing Canadian grain producers. The 12-month line shows the benchmark against which acreage decisions and crop insurance receipts reconcile.",
    ),
    "21": (
        "wti", "timeseries",
        "West Texas Intermediate crude \u2014 12-month trajectory",
        "NYMEX continuous contract \u00b7 USD per barrel",
        "WTI is the reference benchmark that Canadian oil sands operators reconcile against breakeven costs. WCS discounts off WTI, so the 12-month WTI path drives drilling and capex decisions.",
    ),
    "22": (
        "natural_gas", "timeseries",
        "Natural gas \u2014 12-month trajectory",
        "NYMEX Henry Hub \u00b7 USD per MMBtu",
        "Natural gas is the marginal generation fuel outside Quebec, BC, and Manitoba hydro systems. Henry Hub drives residential heating costs, industrial fuel bills, and gas-fired electricity pricing.",
    ),
    "23": (
        "goc_10y_yield", "timeseries",
        "Government of Canada 10-year bond yield \u2014 12-month trajectory",
        "Bank of Canada benchmark \u00b7 percent",
        "The 10-year GoC yield sets the benchmark for fixed mortgage pricing, which drives residential construction demand. Non-residential project financing references the same tenor.",
    ),
    "31-33": (
        "cadusd", "timeseries",
        "Canadian dollar vs US dollar \u2014 12-month trajectory",
        "Bank of Canada midday rate \u00b7 CAD per USD",
        "CAD/USD is the single largest determinant of Canadian manufacturing export competitiveness. A weaker loonie raises USD-denominated revenue; a stronger loonie compresses exporter margins.",
    ),
    "41": (
        "cadusd", "timeseries",
        "Canadian dollar vs US dollar \u2014 12-month trajectory",
        "Bank of Canada midday rate \u00b7 CAD per USD",
        "Wholesalers clear product from US and overseas suppliers into Canadian retail channels. CAD/USD moves translate directly into landed costs and margin-pass-through timing.",
    ),
    "44-45": (
        "overnight_rate", "indicators",
        "Bank of Canada overnight rate \u2014 24-month trajectory",
        "Policy rate \u00b7 percent",
        "Retail demand follows household credit conditions. The BoC policy rate sets the cost of consumer borrowing and the ceiling on big-ticket financing offers.",
    ),
    "48-49": (
        "wti", "timeseries",
        "West Texas Intermediate crude \u2014 12-month trajectory",
        "NYMEX continuous contract \u00b7 USD per barrel",
        "Fuel is the largest variable cost for trucking, rail, and airlines. WTI's 12-month path shapes surcharges, rate cards, and operating margins across the transport segment.",
    ),
    "51": (
        "tsx_composite", "indicators",
        "S&P/TSX Composite \u2014 24-month trajectory",
        "TSX close \u00b7 points",
        "Canadian listed telecom and media (BCE, Rogers, Telus, Quebecor) weight the TSX Communications Services subindex. The composite path proxies investor valuation of sector cashflows.",
    ),
    "52": (
        "goc_10y_yield", "timeseries",
        "Government of Canada 10-year bond yield \u2014 12-month trajectory",
        "Bank of Canada benchmark \u00b7 percent",
        "Bank net interest margins and insurance portfolio returns track the long end of the GoC curve. 10-year yields set the benchmark for mortgage pricing and life insurance reserve discount rates.",
    ),
    "53": (
        "overnight_rate", "indicators",
        "Bank of Canada overnight rate \u2014 24-month trajectory",
        "Policy rate \u00b7 percent",
        "Variable mortgage rates and HELOC pricing move with the BoC policy rate. Real estate transactions, cap rates, and rental absorption follow the policy rate cycle.",
    ),
    "54": (
        "tsx_composite", "indicators",
        "S&P/TSX Composite \u2014 24-month trajectory",
        "TSX close \u00b7 points",
        "Corporate demand for legal, accounting, consulting, and engineering services tracks the equity cycle. TSX levels proxy M&A activity and capital project initiation.",
    ),
    "55": (
        "tsx_composite", "indicators",
        "S&P/TSX Composite \u2014 24-month trajectory",
        "TSX close \u00b7 points",
        "Holding-company NAICS 55 tracks equity portfolio valuations. The TSX Composite path proxies the aggregate valuation of Canadian listed subsidiary interests.",
    ),
    "56": (
        "cadusd", "timeseries",
        "Canadian dollar vs US dollar \u2014 12-month trajectory",
        "Bank of Canada midday rate \u00b7 CAD per USD",
        "Contract staffing, facilities, and waste services demand moves with corporate opex cycles. CAD/USD shapes outsourcing decisions between Canadian and US service providers.",
    ),
    "61": (
        "overnight_rate", "indicators",
        "Bank of Canada overnight rate \u2014 24-month trajectory",
        "Policy rate \u00b7 percent",
        "Public-sector wage settlements and student loan servicing costs track the BoC policy rate. Education spending is bounded by provincial fiscal capacity, which moves with borrowing costs.",
    ),
    "62": (
        "overnight_rate", "indicators",
        "Bank of Canada overnight rate \u2014 24-month trajectory",
        "Policy rate \u00b7 percent",
        "Provincial health transfer capacity is bounded by government borrowing costs. The BoC rate shapes provincial debt service and residual budget for health program expansion.",
    ),
    "71": (
        "cadusd", "timeseries",
        "Canadian dollar vs US dollar \u2014 12-month trajectory",
        "Bank of Canada midday rate \u00b7 CAD per USD",
        "Cross-border tourism to Canada scales inversely with the Canadian dollar. A weaker CAD raises inbound visitor counts and arts/entertainment ticket volume; a stronger dollar compresses it.",
    ),
    "72": (
        "cadusd", "timeseries",
        "Canadian dollar vs US dollar \u2014 12-month trajectory",
        "Bank of Canada midday rate \u00b7 CAD per USD",
        "Hotel occupancy and restaurant spending from inbound tourism move with CAD/USD. A weak loonie draws US visitors; a strong loonie redirects Canadian travelers to US destinations.",
    ),
    "81": (
        "overnight_rate", "indicators",
        "Bank of Canada overnight rate \u2014 24-month trajectory",
        "Policy rate \u00b7 percent",
        "Personal services, repair, and civic organizations draw from household discretionary spending. The BoC rate sets the cost of household credit and the savings rate that competes for that spending.",
    ),
    "91": (
        "goc_10y_yield", "timeseries",
        "Government of Canada 10-year bond yield \u2014 12-month trajectory",
        "Bank of Canada benchmark \u00b7 percent",
        "Federal and provincial borrowing costs determine fiscal room for public administration payrolls and operating budgets. The GoC 10-year yield is the benchmark rate on the largest debt tranche.",
    ),
}


def build_chart(code, name, mm, yy, cfg):
    data_key, data_source, title, subtitle, reasoning = cfg
    window = "24m" if data_source == "indicators" else "12m"
    return {
        "chartType": "line",
        "dataKeys": [data_key],
        "dataSource": data_source,
        "window": window,
        "title": title,
        "subtitle": subtitle,
        "yAxisLabel": "",
        "eyebrow": "Industry \u00b7 " + name,
        "kpis": [
            {"label": "GDP (M/M)", "value": mm or "\u2014", "delta": "Jan 2026 print", "trend": ""},
            {"label": "GDP (Y/Y)", "value": yy or "\u2014", "delta": "Jan 2026 print", "trend": ""},
        ],
        "context": reasoning,
        "reasoning": reasoning,
    }


def main():
    data = json.loads(BRIEFING.read_text(encoding="utf-8"))
    patched = 0
    for bucket in ("goodsIndustries", "servicesIndustries"):
        for ind in data.get(bucket, []):
            code = ind.get("code")
            if code not in INDUSTRY_CHARTS:
                print(f"  SKIP {bucket} code={code!r} (no mapping)")
                continue
            name = ind.get("name", "")
            mm = ind.get("mm", "")
            yy = ind.get("yy", "")
            ind["insightCharts"] = [build_chart(code, name, mm, yy, INDUSTRY_CHARTS[code])]
            patched += 1
            print(f"  ADD  {bucket} code={code!r} -> {INDUSTRY_CHARTS[code][0]}")

    BRIEFING.write_text(
        json.dumps(data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nPatched {patched} industries. Wrote {BRIEFING}.")


if __name__ == "__main__":
    main()
