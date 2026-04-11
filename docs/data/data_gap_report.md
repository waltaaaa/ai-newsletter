# Data Gap Report - 2026-04-11

Agent 0.5 (tldr-data-gap) audit. Runs between Agent 0 (data refresh) and Phase 1 (research).

## Coverage Summary
- Provinces with core CPI+Unemployment: 9/13
- Daily commodities current (<=14d): 10/15
- Market commodities complete (13 required): 12/13
- Yield curve tenors in briefing: 3/7
- Yield curve detail: 3/7 current | 3/3 year-ago
- Timeseries keys: 111 checked, 69 stale
- Projects monitored (lastSeen <=30d): 7427/7427
- Policy weeks / newest: 6 / 2026-04-11
- Weekly delta coverage: 95%
- Monthly delta coverage: 91%
- Yearly delta coverage: 79%
- Cross-tab consistency: PASS

**Overall Data Freshness Grade: B**
- A: all critical sources current
- B: 1-3 critical gaps or heavy warning load
- C: 4-7 critical gaps
- D: 8+ critical gaps, significant data quality issues

---

## Critical Gaps
- PE: missing CPI (PE_cpi)
- PE: missing Unemployment Rate (PE_unemployment)

---

## Warnings
- ON CPI: period 2026-02-01 (69d old, limit 60d)
- ON Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- QC CPI: period 2026-02-01 (69d old, limit 60d)
- QC Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- AB CPI: period 2026-02-01 (69d old, limit 60d)
- AB Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- BC CPI: period 2026-02-01 (69d old, limit 60d)
- BC Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- SK CPI: period 2026-02-01 (69d old, limit 60d)
- SK Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- MB CPI: period 2026-02-01 (69d old, limit 60d)
- MB Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- NS CPI: period 2026-02-01 (69d old, limit 60d)
- NS Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- NB CPI: period 2026-02-01 (69d old, limit 60d)
- NB Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- NL CPI: period 2026-02-01 (69d old, limit 60d)
- NL Unemployment Rate: period 2026-02-01 (69d old, limit 60d)
- commodity lumber: last 2023-05-12 (1065d old)
- commodity potash_nutrien: last 2026-03-18 (24d old)
- commodity sprott_uranium: last 2026-03-18 (24d old)
- commodity canola: no data in timeseries
- commodity cameco_uranium: last 2026-03-18 (24d old)
- timeseries comm_wti: 2026-03-31 (11d old, window 10d)
- timeseries comm_brent: 2026-03-31 (11d old, window 10d)
- timeseries comm_natgas: 2026-03-31 (11d old, window 10d)
- timeseries comm_gold: 2026-03-31 (11d old, window 10d)
- timeseries comm_silver: 2026-03-31 (11d old, window 10d)
- timeseries comm_platinum: 2026-03-31 (11d old, window 10d)
- timeseries comm_palladium: 2026-03-31 (11d old, window 10d)
- timeseries comm_copper: 2026-03-31 (11d old, window 10d)
- timeseries comm_aluminum: 2026-03-31 (11d old, window 10d)
- timeseries comm_wheat: 2026-03-31 (11d old, window 10d)
- timeseries comm_corn: 2026-03-31 (11d old, window 10d)
- timeseries comm_rice: 2026-03-31 (11d old, window 10d)
- timeseries comm_soybeans: 2026-03-31 (11d old, window 10d)
- timeseries comm_coffee: 2026-03-31 (11d old, window 10d)
- timeseries comm_cocoa: 2026-03-31 (11d old, window 10d)
- timeseries comm_sugar: 2026-03-31 (11d old, window 10d)
- timeseries comm_cotton: 2026-03-31 (11d old, window 10d)
- timeseries comm_soyoil: 2026-03-31 (11d old, window 10d)
- timeseries comm_soymeal: 2026-03-31 (11d old, window 10d)
- timeseries comm_coal: 2026-03-31 (11d old, window 10d)
- timeseries idx_nasdaq: 2026-03-25 (17d old, window 10d)
- timeseries idx_dax: 2026-03-31 (11d old, window 10d)
- timeseries idx_nikkei: 2026-03-15 (27d old, window 10d)
- timeseries nasdaq: 2026-03-27 (15d old, window 10d)
- timeseries dax: 2026-03-31 (11d old, window 10d)
- timeseries nikkei225: 2026-03-24 (18d old, window 10d)
- timeseries eurusd: 2026-03-25 (17d old, window 10d)
- timeseries gold: 2026-03-31 (11d old, window 10d)
- timeseries lumber: 2023-05-12 (1065d old, window 10d)
- timeseries potash_nutrien: 2026-03-18 (24d old, window 10d)
- timeseries cameco_uranium: 2026-03-18 (24d old, window 10d)
- timeseries sprott_uranium: 2026-03-18 (24d old, window 10d)
- timeseries AB_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries AB_cpi: 2026-02-01 (69d old, window 60d)
- timeseries BC_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries BC_cpi: 2026-02-01 (69d old, window 60d)
- timeseries MB_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries MB_cpi: 2026-02-01 (69d old, window 60d)
- timeseries NB_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries NB_cpi: 2026-02-01 (69d old, window 60d)
- timeseries NL_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries NL_cpi: 2026-02-01 (69d old, window 60d)
- timeseries NS_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries NS_cpi: 2026-02-01 (69d old, window 60d)
- timeseries ON_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries ON_cpi: 2026-02-01 (69d old, window 60d)
- timeseries QC_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries QC_cpi: 2026-02-01 (69d old, window 60d)
- timeseries SK_unemployment: 2026-02-01 (69d old, window 60d)
- timeseries SK_cpi: 2026-02-01 (69d old, window 60d)
- timeseries ON_on_exports: 2025-07-01 (284d old, window 30d)
- timeseries ON_on_imports: 2025-07-01 (284d old, window 30d)
- timeseries ON_on_real_capital_investment: 2025-07-01 (284d old, window 120d)
- timeseries ON_on_gdp_goods: 2025-07-01 (284d old, window 120d)
- timeseries ON_on_real_consumption: 2025-07-01 (284d old, window 30d)
- timeseries ON_on_real_household: 2025-07-01 (284d old, window 30d)
- timeseries QC_qc_exports: 2025-07-01 (284d old, window 30d)
- ...and 23 additional warnings

---

## Filled This Run
None. Automation mode: this run reports gaps only; targeted WebSearch remediation was skipped to keep the audit deterministic and non-blocking.

---

## Info Notes (expected limitations, low-impact)
- YT: missing CPI (YT_cpi) - territory
- YT: missing Unemployment Rate (YT_unemployment) - territory
- NT: missing CPI (NT_cpi) - territory
- NT: missing Unemployment Rate (NT_unemployment) - territory
- NU: missing CPI (NU_cpi) - territory
- NU: missing Unemployment Rate (NU_unemployment) - territory

---

## Pipeline Stop Conditions (advisory)
**Automation mode: pipeline will PROCEED regardless of stop conditions.**

No stop conditions triggered.

---

## Technical Notes
- Report generated: 2026-04-11T05:38:43.742228+00:00
- Agent: tldr-data-gap (Phase 0.5)
- Audit scope: 13 provinces, 15 tracked commodities, 111 timeseries keys, 7427 projects
- Critical gaps: 2
- Warnings: 103
- Info notes: 6
- Gaps filled: 0
