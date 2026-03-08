# SKILL.md — Canadian Economic Data Parsing

## When to Use
Activate when working on any code that pulls, parses, stores, or displays data from Statistics Canada, Bank of Canada, or Yahoo Finance. Also activate when working on indicator_history, backfill, trend analysis, or the Data Explorer.

## StatsCan Web Data Service
- Base URL: https://www150.statcan.gc.ca/t1/wds/rest/
- getAllCubesListLite — returns all ~6000 tables with metadata
- getDataFromVectorByRange — returns time series for a V-code
- getSeriesInfoFromCubePidCoord — returns vector metadata for a table
- Response format: JSON with status, object containing vectorId, coordinate, value, refPer
- V-codes: unique identifier starting with "V" followed by up to 10 digits
- Table numbers: format XX-XX-XXXX-XX (e.g., 14-10-0287-01)
- Table URL: https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid={table_no_dashes}
- API processes max 300 coordinates per request — batch if more needed

## Bank of Canada Valet API
- Base URL: https://www.bankofcanada.ca/valet/
- /observations/{series}/json?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
- Response: { observations: [{ d: "YYYY-MM-DD", SERIES_NAME: { v: "value" } }] }
- Key series: V39079 (policy rate), FXCADUSD (exchange rate), V41690973 (CPI), V122530 (prime rate), V122543 (10Y bond), V122521 (5Y mortgage)

## Yahoo Finance (via yfinance)
- No API key required
- Key tickers: CL=F (WTI), NG=F (gas), GC=F (gold), HG=F (copper), LBS=F (lumber), ^GSPTSE (TSX), CADUSD=X
- Returns daily OHLCV data via yf.download()

## Firestore Schema: indicator_history
- Collection: indicator_history
- Document ID: {indicator}_{province}_{YYYY-MM-DD}
- Fields: indicator (string), province (string, "national" or province code), date (string YYYY-MM-DD), value (number), unit (string), source (string), frequency (string), description (string), backfilled (boolean)
- Queried by: indicator + province + date range

## Province Codes
ON, QC, AB, BC, SK, MB, NS, NB, NL, PE, YT, NT, NU
Use "national" for Canada-wide indicators.

## Rules
- Always write to indicator_history collection using the standard schema above
- Always include statcan_table_url when displaying StatsCan data
- Never use Gemini grounded search for data fetching — use the APIs directly
- V-codes do not change even when table numbers are updated
