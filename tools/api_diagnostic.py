"""
API Connection Diagnostic — tests all free data sources used by the pipeline.
Run: python tools/api_diagnostic.py
"""
import asyncio, aiohttp, json, os, sys, time

TIMEOUT = aiohttp.ClientTimeout(total=15)
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CanMacroDashboard/1.0)"}
results = []

def ok(name, detail=""):
    results.append(("PASS", name, detail))
    print(f"  PASS  {name}  {detail}")

def fail(name, detail=""):
    results.append(("FAIL", name, detail))
    print(f"  FAIL  {name}  {detail}")

def skip(name, detail=""):
    results.append(("SKIP", name, detail))
    print(f"  SKIP  {name}  {detail}")

async def test_json(session, name, url, validate=None):
    try:
        async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as r:
            if r.status != 200:
                fail(name, f"HTTP {r.status}")
                return
            data = await r.json(content_type=None)
            if validate:
                msg = validate(data)
                if msg:
                    fail(name, msg)
                    return
            ok(name, f"HTTP 200, got {type(data).__name__}")
    except Exception as e:
        fail(name, str(e)[:120])

async def test_text(session, name, url, check=None):
    try:
        async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as r:
            if r.status != 200:
                fail(name, f"HTTP {r.status}")
                return
            text = await r.text()
            if check and not check(text):
                fail(name, f"Response validation failed (len={len(text)})")
                return
            ok(name, f"HTTP 200, {len(text)} bytes")
    except Exception as e:
        fail(name, str(e)[:120])

async def test_rss(session, name, url):
    try:
        async with session.get(url, headers=HEADERS, timeout=TIMEOUT) as r:
            if r.status != 200:
                fail(name, f"HTTP {r.status}")
                return
            text = await r.text()
            if "<item" in text or "<entry" in text or "<rss" in text or "<feed" in text:
                items = text.count("<item") + text.count("<entry")
                ok(name, f"HTTP 200, ~{items} items")
            else:
                fail(name, f"No RSS/Atom content detected (len={len(text)})")
    except Exception as e:
        fail(name, str(e)[:120])


async def run_all():
    conn = aiohttp.TCPConnector(limit=10, ssl=False)
    async with aiohttp.ClientSession(connector=conn) as s:

        print("\n--- 1. STATISTICS CANADA ---")
        # (StatCan WDS CSV endpoint removed - not used by pipeline)
        # Actually test the real WDS vectors endpoint
        wds_payload = [{"vectorId": 41690973, "latestN": 1}]  # Unemployment rate
        try:
            async with s.post(
                "https://www150.statcan.gc.ca/t1/wds/rest/getDataFromVectorsAndLatestNPeriods",
                json=wds_payload, headers=HEADERS, timeout=TIMEOUT
            ) as r:
                if r.status == 200:
                    data = await r.json(content_type=None)
                    if isinstance(data, list) and len(data) > 0:
                        ok("StatCan WDS Vectors", f"Got {len(data)} result(s)")
                    else:
                        fail("StatCan WDS Vectors", f"Unexpected response: {str(data)[:100]}")
                else:
                    fail("StatCan WDS Vectors", f"HTTP {r.status}")
        except Exception as e:
            fail("StatCan WDS Vectors", str(e)[:120])

        # StatCan JSON daily indicators
        await test_json(s, "StatCan Daily Indicators",
            "https://www150.statcan.gc.ca/n1/dai-quo/ssi/homepage/ind-econ.json",
            validate=lambda d: None if isinstance(d, (list, dict)) else "Not a list/dict"
        )

        print("\n--- 2. BANK OF CANADA ---")
        await test_json(s, "BoC Valet API (Policy Rate)",
            "https://www.bankofcanada.ca/valet/observations/V39079/json?recent=5",
            validate=lambda d: None if "observations" in d else "No 'observations' key"
        )

        print("\n--- 3. YAHOO FINANCE (yfinance) ---")
        try:
            import yfinance as yf
            ticker = yf.Ticker("CL=F")
            hist = ticker.history(period="5d")
            if len(hist) > 0:
                last = hist["Close"].iloc[-1]
                ok("yfinance — WTI Crude (CL=F)", f"Last close: ${last:.2f}")
            else:
                fail("yfinance — WTI Crude (CL=F)", "No data returned")
        except ImportError:
            skip("yfinance", "yfinance not installed")
        except Exception as e:
            fail("yfinance — WTI Crude (CL=F)", str(e)[:120])

        try:
            import yfinance as yf
            ticker = yf.Ticker("CADUSD=X")
            hist = ticker.history(period="5d")
            if len(hist) > 0:
                last = hist["Close"].iloc[-1]
                ok("yfinance — CAD/USD", f"Last: {last:.4f}")
            else:
                fail("yfinance — CAD/USD", "No data returned")
        except ImportError:
            pass
        except Exception as e:
            fail("yfinance — CAD/USD", str(e)[:120])

        try:
            import yfinance as yf
            ticker = yf.Ticker("GC=F")
            hist = ticker.history(period="5d")
            if len(hist) > 0:
                ok("yfinance — Gold (GC=F)", f"Last: ${hist['Close'].iloc[-1]:.2f}")
            else:
                fail("yfinance — Gold (GC=F)", "No data returned")
        except ImportError:
            pass
        except Exception as e:
            fail("yfinance — Gold (GC=F)", str(e)[:120])

        print("\n--- 4. FRED (US Economic Data) ---")
        try:
            async with s.get("https://fred.stlouisfed.org/graph/fredgraph.csv?id=UNRATE&cosd=2025-01-01", headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30), ssl=False) as r:
                if r.status == 200:
                    text = await r.text()
                    if "observation_date" in text or len(text) > 50:
                        ok("FRED -- US Unemployment (CSV)", f"HTTP 200, {len(text)} bytes")
                    else:
                        fail("FRED -- US Unemployment (CSV)", f"Unexpected content (len={len(text)})")
                else:
                    fail("FRED -- US Unemployment (CSV)", f"HTTP {r.status}")
        except Exception as e:
            import traceback; traceback.print_exc()
            fail("FRED -- US Unemployment (CSV)", repr(e)[:120])

        print("\n--- 5. ECB DATA API ---")
        await test_text(s, "ECB — Euro Area GDP",
            "https://data-api.ecb.europa.eu/service/data/MNA/Q.Y.I8.W2.S1.S1.B.B1GQ._Z._Z._Z.EUR.LR.GY?lastNObservations=2&format=csvdata",
            check=lambda t: len(t) > 50
        )

        print("\n--- 6. BANK OF ENGLAND ---")
        await test_text(s, "BoE — Base Rate",
            "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp",
            check=lambda t: "Bank Rate" in t or "rate" in t.lower()
        )

        print("\n--- 7. GOVERNMENT REGISTRIES ---")
        await test_text(s, "IAAC Registry",
            "https://iaac-aeic.gc.ca/050/evaluations/exploration?culture=en-CA",
            check=lambda t: len(t) > 1000
        )

        await test_json(s, "BC EAO Projects API",
            "https://projects.eao.gov.bc.ca/api/public/search?dataset=Project&pageNum=0&pageSize=2&sortBy=-dateUpdated",
        )

        await test_json(s, "Infrastructure Canada Open Data",
            "https://infrastructure.gc.ca/alt-format/opendata/project-list-liste-de-projets-bil.json",
            validate=lambda d: None if (isinstance(d, dict) and "data" in d) or (isinstance(d, list) and len(d) > 0) else "Unexpected format"
        )

        await test_text(s, "CER Applications Page",
            "https://www.cer-rec.gc.ca/en/applications-hearings/view-applications-projects/",
            check=lambda t: len(t) > 1000
        )

        print("\n--- 8. RSS FEEDS (sample) ---")
        rss_tests = [
            ("StatCan Daily RSS (Atom)", "https://www150.statcan.gc.ca/n1/rss/dai-quo/0-eng.atom"),
            ("BoC Press Releases", "https://www.bankofcanada.ca/content_type/press-releases/feed/"),
            ("Google News RSS (Canada economy)", "https://news.google.com/rss/search?q=%22Canada%22+%22economy%22&hl=en-CA&gl=CA&ceid=CA:en"),
            ("CBC Business RSS", "https://www.cbc.ca/webfeed/rss/rss-business"),
            ("Globe and Mail Business", "https://www.theglobeandmail.com/arc/outboundfeeds/rss/category/business/"),
        ]
        for name, url in rss_tests:
            await test_rss(s, name, url)

        print("\n--- 9. MUNICIPAL OPEN DATA ---")
        await test_json(s, "Calgary Open Data (Socrata)",
            "https://data.calgary.ca/resource/6933-unw5.json?$limit=2",
        )
        await test_json(s, "Edmonton Open Data (Socrata)",
            "https://data.edmonton.ca/resource/24uj-dj8v.json?$limit=2",
        )
        await test_json(s, "Vancouver Open Data",
            "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/issued-building-permits/records?limit=2",
        )

        print("\n--- 10. AI/LLM APIs (key-dependent) ---")
        # Tavily
        tavily_key = os.environ.get("TAVILY_API_KEY", "")
        if tavily_key:
            try:
                async with s.post("https://api.tavily.com/search",
                    json={"api_key": tavily_key, "query": "Canada infrastructure projects 2026", "max_results": 1},
                    timeout=TIMEOUT
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        ok("Tavily Search API", f"Got {len(data.get('results',[]))} result(s)")
                    else:
                        fail("Tavily Search API", f"HTTP {r.status}")
            except Exception as e:
                fail("Tavily Search API", str(e)[:120])
        else:
            skip("Tavily Search API", "TAVILY_API_KEY not set")

        # Groq
        groq_key = os.environ.get("GROQ_API_KEY", "")
        if groq_key:
            try:
                async with s.post("https://api.groq.com/openai/v1/chat/completions",
                    json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "Reply with OK"}], "max_tokens": 5},
                    headers={**HEADERS, "Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                    timeout=TIMEOUT
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        ok("Groq LLaMA 3.3 70B", f"Response: {reply[:30]}")
                    else:
                        body = await r.text()
                        fail("Groq LLaMA 3.3 70B", f"HTTP {r.status}: {body[:100]}")
            except Exception as e:
                fail("Groq LLaMA 3.3 70B", str(e)[:120])
        else:
            skip("Groq LLaMA 3.3 70B", "GROQ_API_KEY not set")

        # NVIDIA NIM
        nim_key = os.environ.get("NVIDIA_API_KEY", os.environ.get("NIM_API_KEY", ""))
        if nim_key:
            try:
                async with s.post("https://integrate.api.nvidia.com/v1/chat/completions",
                    json={"model": "nvidia/llama-3.3-nemotron-super-49b-v1", "messages": [{"role": "user", "content": "Reply OK"}], "max_tokens": 5},
                    headers={**HEADERS, "Authorization": f"Bearer {nim_key}", "Content-Type": "application/json"},
                    timeout=TIMEOUT
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        ok("NVIDIA NIM (Nemotron Super)", f"Response: {reply[:30]}")
                    else:
                        body = await r.text()
                        fail("NVIDIA NIM (Nemotron Super)", f"HTTP {r.status}: {body[:100]}")
            except Exception as e:
                fail("NVIDIA NIM (Nemotron Super)", str(e)[:120])
        else:
            skip("NVIDIA NIM", "NVIDIA_API_KEY / NIM_API_KEY not set")

        # (Ollama removed — replaced by NIM Nemotron)


    # Summary
    print("\n" + "-" * 60)
    passes = sum(1 for r in results if r[0] == "PASS")
    fails = sum(1 for r in results if r[0] == "FAIL")
    skips = sum(1 for r in results if r[0] == "SKIP")
    total = len(results)
    print(f"  TOTAL: {total}  |  PASS: {passes}  |  FAIL: {fails}  |  SKIP: {skips}")
    if fails:
        print("\n  Failed connections:")
        for r in results:
            if r[0] == "FAIL":
                print(f"    - {r[1]}: {r[2]}")
    print()


if __name__ == "__main__":
    asyncio.run(run_all())
