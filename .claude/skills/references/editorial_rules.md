# Editorial Rules — The Lagging Indicator

Single source of truth for editorial policy across every tldr-* producer. All briefing output must follow wire-service reporting tone (Reuters / Bloomberg / Canadian Press).

## Cardinal Rules

1. State what happened. State what the data shows. State what is connected to what. Stop.
2. Let the reader draw their own conclusions — never tell them what to think.
3. Every claim cites a source using `<sup>N</sup>` matching `sources[]` IDs.
4. Use specific numbers — not "increased significantly" but "+3.8% month-over-month."
5. Attribution over assertion — "The database tracks 14 projects with breakeven above $70" not "14 projects are threatened."
6. Conditional language for projections — "If rates hold, 23 projects would see..." not "23 projects will benefit."

## Banned Words

Primary list (enforced by `tools/validate_briefing_schema.py` BANNED_WORDS — any match is a hard FAIL):

```
should, must, hopefully, unfortunately, worrying, promising, encouraging, welcome,
bullish, bearish, concerning, headwind, tailwind, thrilled, feared, hoped
```

Extended editorial list (producer self-check should reject these too — they leak editorial tone even if the validator does not yet fail them):

```
good news, bad news, optimistic, pessimistic, troubling, reassuring,
positive (as judgment), negative (as judgment), robust, significant, notably, healthy,
strong (as judgment), weak (as judgment), rally (as noun — use "advance" or "gain"),
plunge (use "decline" or "drop")
```

Callout-tier subset (validator `CALLOUT_BANNED_WORDS`, enforced on every insightCharts callout):

```
welcome, concerning, worrying, promising, encouraging, unfortunately, hopefully, bullish, bearish
```

## HTML Formatting

- **Lead-in + em-dash paragraph structure (mandatory for EVERY narrative paragraph, all writers):** each `<p>` opens with a lead-in sentence wrapped in `<span class="lead-sentence">...</span>`, followed by ` — ` (space, em-dash, space) and the rest of the paragraph:

  ```html
  <p><span class="lead-sentence">Lead-in sentence stating the paragraph's single core fact</span> — supporting detail, context, and cross-references with citations.<sup>1</sup></p>
  ```

- The lead-in is the ONLY bold text. Bolding comes from the frontend CSS rule `.lead-sentence{font-weight:600}` — writers must NEVER emit `<strong>` or `<b>` tags anywhere in prose. Numbers stay specific but unbolded.
- The lead-in span carries no terminal period; the em-dash after the closing `</span>` is the delimiter, and the continuation starts lowercase unless it begins with a proper noun.
- `<sup>N</sup>` for every sourced claim, matching `sources[].id`
- `<p>` tags for paragraphs; no bullet points in executive summary — use flowing prose
- Third person; present tense for current data, past tense for events
- Paragraphs 3–5 sentences; direct and concrete, no subordinate-clause chains

## Wire-Service Example

**WRONG (disconnected facts):**

> "Unemployment rose to 6.5%. Housing starts were 230,000. The BoC held rates."

**WRONG (editorial opinion):**

> "The rate hold is encouraging news for the struggling housing sector."

**RIGHT (wire-service reporting):**

> <span class="lead-sentence">Unemployment rose to 6.5% in March as the economy shed 8,000 positions</span> — Statistics Canada's Labour Force Survey recorded the rate up 0.3 percentage points from February<sup>1</sup>, with losses concentrated in retail trade and accommodation services. The project database tracks 412 retail and hospitality projects ($2.1B)<sup>2</sup> in proposed or planning stages.

The difference: reporting **connects** facts to context (WHERE the data came from, WHAT IT MEANS for real economic actors), without saying whether that is good or bad.

## Examples (extended)

### Commodity price move — editorializing vs reporting

**WRONG:**
> "Oil prices declined sharply this week, which is concerning for the energy sector. WTI fell significantly as global demand weakened. This is bad news for Alberta's economy."

**RIGHT:**
> <span class="lead-sentence">WTI crude oil fell $4.80 (6.7%) to settle at US$67.20/bbl on Friday, the lowest close since February</span> — IEA reporting indicated weaker-than-expected global demand and OPEC+ prepared to increase production by 400,000 barrels per day effective May 1<sup>1</sup><sup>2</sup>. The project database contains 312 energy and mining projects ($87.4B), of which 23 have estimated breakeven costs above the current WTI price<sup>3</sup>.

### Policy decision — editorial vs reporting

**WRONG:**
> "The Bank of Canada maintained its policy rate at 2.25%, providing continued support to borrowers. The rate hold is encouraging news for the residential market."

**RIGHT:**
> <span class="lead-sentence">The Bank of Canada's Governing Council held the policy rate at 2.25% on March 26</span> — the decision maintained its stance as real GDP contracted at an annualized -0.6%<sup>1</sup><sup>2</sup> in the fourth quarter. The project database tracks $23.4 billion in residential projects across Canada, of which 847 are in proposed or planning stages<sup>3</sup>; these projects would be rate-sensitive should the central bank shift its policy direction.

### Labour and sectors — disconnected vs connected

**WRONG:**
> "Manufacturing employment rose 2.1% year-over-year. Construction employment was flat. Retail employment fell 1.3% year-over-year. Construction weakness is troubling given the housing shortage."

**RIGHT:**
> <span class="lead-sentence">Employment trends diverged across industries in March</span> — labour force data by industry<sup>1</sup> recorded manufacturing employment up 2.1% year-over-year, propelled by automotive and machinery-producing firms; construction employment flat at prior-month levels; and retail trade employment down 1.3% year-over-year. The project database tracks 418 manufacturing projects ($31.2B), 312 construction projects ($54.1B), and 142 retail and hospitality projects ($2.8B)<sup>2</sup> across all statuses.
