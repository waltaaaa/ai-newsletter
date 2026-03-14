"""
Job posting monitor — detects hiring spikes as leading indicators for project activity.

Sources:
1. Government of Canada Job Bank RSS (free, structured, reliable)
2. Indeed RSS feeds by location + sector keywords (free, broader coverage)

Outputs:
- Hiring spike alerts linked to projects by employer name + location
- Aggregate hiring volume by CMA and sector for trend reporting

Does NOT track individual postings — aggregates by employer + geography.
"""
import feedparser
import json
import logging
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

# Job Bank RSS base URL — supports location and keyword filtering
JOB_BANK_RSS = "https://www.jobbank.gc.ca/jobsearch/jobsearch?sort=D&frid={region_id}&fkw={keyword}&rss=1"

# Indeed RSS base URL — supports location and query filtering
INDEED_RSS = "https://ca.indeed.com/rss?q={query}&l={location}&sort=date"

# Sector-specific search terms mapped to NAICS keys
SECTOR_SEARCH_TERMS = {
    "oil_gas": ["pipeline construction", "oilfield", "drilling", "refinery operator", "LNG plant"],
    "mining": ["mine construction", "mining engineer", "mill operator", "exploration geologist"],
    "infrastructure": ["civil engineer construction", "highway construction", "bridge construction",
                       "water treatment plant", "transit construction"],
    "power_energy": ["solar installation", "wind turbine technician", "nuclear operator",
                     "electrical substation", "power plant construction"],
    "residential": ["residential construction", "condo construction", "housing development",
                    "framing carpenter", "residential project manager"],
    "commercial_mixed": ["commercial construction", "office tower construction",
                         "retail construction", "mixed-use development"],
    "manufacturing": ["manufacturing plant setup", "factory construction", "assembly line"],
    "healthcare": ["hospital construction", "healthcare facility", "long-term care construction"],
    "defence": ["military construction", "DND contract", "shipyard"],
}

# Major CMAs to monitor — maps to CMA names and Job Bank region IDs
CMA_REGIONS = {
    "Toronto": {"province": "ON", "indeed_location": "Toronto, ON", "job_bank_region": "5535"},
    "Montreal": {"province": "QC", "indeed_location": "Montréal, QC", "job_bank_region": "24462"},
    "Vancouver": {"province": "BC", "indeed_location": "Vancouver, BC", "job_bank_region": "59933"},
    "Calgary": {"province": "AB", "indeed_location": "Calgary, AB", "job_bank_region": "48825"},
    "Edmonton": {"province": "AB", "indeed_location": "Edmonton, AB", "job_bank_region": "48835"},
    "Ottawa": {"province": "ON", "indeed_location": "Ottawa, ON", "job_bank_region": "35505"},
    "Winnipeg": {"province": "MB", "indeed_location": "Winnipeg, MB", "job_bank_region": "46602"},
    "Halifax": {"province": "NS", "indeed_location": "Halifax, NS", "job_bank_region": "12205"},
    "Saskatoon": {"province": "SK", "indeed_location": "Saskatoon, SK", "job_bank_region": "47725"},
    "Regina": {"province": "SK", "indeed_location": "Regina, SK", "job_bank_region": "47730"},
    "St. John's": {"province": "NL", "indeed_location": "St. John's, NL", "job_bank_region": "10010"},
    "Fort McMurray": {"province": "AB", "indeed_location": "Fort McMurray, AB", "job_bank_region": "48832"},
    "Kitimat": {"province": "BC", "indeed_location": "Kitimat, BC", "job_bank_region": "59"},
    "Saint John": {"province": "NB", "indeed_location": "Saint John, NB", "job_bank_region": "13310"},
    "Sudbury": {"province": "ON", "indeed_location": "Sudbury, ON", "job_bank_region": "35580"},
}

# Anomaly threshold — flag when a single employer's postings exceed this multiplier
# of their average over the past 4 weeks
SPIKE_THRESHOLD = 3.0


def fetch_job_postings(sector_key, cma_name, source="indeed"):
    """
    Fetch recent job postings for a sector + CMA combination.
    Returns list of dicts with employer, title, location, date.
    """
    cma = CMA_REGIONS.get(cma_name)
    if not cma:
        return []

    terms = SECTOR_SEARCH_TERMS.get(sector_key, [])
    all_postings = []

    for term in terms[:3]:  # Limit to 3 terms per sector to control fetch volume
        try:
            if source == "indeed":
                url = INDEED_RSS.format(
                    query=term.replace(" ", "+"),
                    location=cma["indeed_location"].replace(" ", "+")
                )
            else:
                url = JOB_BANK_RSS.format(
                    region_id=cma["job_bank_region"],
                    keyword=term.replace(" ", "+")
                )

            feed = feedparser.parse(url)
            for entry in feed.entries[:20]:
                posting = {
                    "title": entry.get("title", ""),
                    "employer": _extract_employer(entry),
                    "location": cma_name,
                    "province": cma["province"],
                    "sector": sector_key,
                    "date": entry.get("published", ""),
                    "url": entry.get("link", ""),
                }
                all_postings.append(posting)

        except Exception as e:
            logger.debug(f"[JOBS] Failed to fetch {source} for {term} in {cma_name}: {e}")

    return all_postings


def _extract_employer(entry):
    """Extract employer name from a job posting RSS entry."""
    # Indeed puts employer in the title as "Job Title - Employer"
    title = entry.get("title", "")
    if " - " in title:
        return title.rsplit(" - ", 1)[-1].strip()
    # Job Bank uses author field
    author = entry.get("author", "")
    if author:
        return author
    return "Unknown"


def aggregate_by_employer(postings):
    """
    Aggregate postings by employer + location.
    Returns dict: {(employer, location, sector): count}
    """
    counts = defaultdict(int)
    for p in postings:
        key = (p["employer"], p["location"], p["sector"])
        counts[key] += 1
    return dict(counts)


def detect_hiring_spikes(current_counts, historical_counts):
    """
    Compare current week's employer counts against rolling 4-week average.
    Flag any employer whose posting count exceeds SPIKE_THRESHOLD x average.

    Args:
        current_counts: dict from aggregate_by_employer for this week
        historical_counts: list of dicts from previous 4 weeks

    Returns:
        list of spike alerts
    """
    averages = defaultdict(float)
    for week_counts in historical_counts:
        for key, count in week_counts.items():
            averages[key] += count
    for key in averages:
        averages[key] /= max(len(historical_counts), 1)

    spikes = []
    for key, count in current_counts.items():
        employer, location, sector = key
        avg = averages.get(key, 0)

        if count >= 5 and (avg == 0 or count >= avg * SPIKE_THRESHOLD):
            spikes.append({
                "employer": employer,
                "location": location,
                "sector": sector,
                "current_count": count,
                "average_count": round(avg, 1),
                "multiplier": round(count / max(avg, 1), 1),
                "signal": f"{employer} posted {count} jobs in {location} ({sector}) — "
                          f"{round(count / max(avg, 1), 1)}x normal volume"
            })

    return sorted(spikes, key=lambda x: x["current_count"], reverse=True)


def link_spikes_to_projects(spikes, conn):
    """
    Attempt to match hiring spikes to projects in the database by employer name
    and location/province.
    """
    linked = []
    cursor = conn.cursor()

    for spike in spikes:
        try:
            cursor.execute("""
                SELECT name, province, value, status, sector
                FROM projects
                WHERE (name LIKE ? OR name LIKE ?)
                AND province = ?
                ORDER BY value DESC
                LIMIT 3
            """, (
                f"%{spike['employer']}%",
                f"%{spike['employer'].split()[0]}%",
                spike["location"],
            ))

            matches = cursor.fetchall()
            spike["linked_projects"] = [
                {"name": m[0], "province": m[1], "value": m[2],
                 "status": m[3], "sector": m[4]}
                for m in matches
            ]
        except Exception as e:
            logger.debug(f"[JOBS] Project linking failed for {spike['employer']}: {e}")
            spike["linked_projects"] = []

        linked.append(spike)

    return linked


def _serialize_key(key):
    """Serialize a tuple key to a JSON-safe string."""
    return json.dumps(list(key))


def _deserialize_key(key_str):
    """Deserialize a JSON string back to a tuple key."""
    return tuple(json.loads(key_str))


def save_job_snapshot(conn, employer_counts, spikes, run_date):
    """
    Save weekly job posting snapshot to the database for historical comparison.
    """
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO job_snapshots (week_of, data, spikes)
        VALUES (?, ?, ?)
    """, (
        run_date,
        json.dumps({_serialize_key(k): v for k, v in employer_counts.items()}),
        json.dumps(spikes, default=str),
    ))
    conn.commit()


def get_historical_counts(conn, weeks=4):
    """Load previous N weeks of employer counts for spike detection."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT data FROM job_snapshots
        ORDER BY week_of DESC
        LIMIT ?
    """, (weeks,))

    historical = []
    for row in cursor.fetchall():
        try:
            data = json.loads(row[0])
            counts = {}
            for k, v in data.items():
                try:
                    counts[_deserialize_key(k)] = v
                except (json.JSONDecodeError, TypeError):
                    pass
            historical.append(counts)
        except json.JSONDecodeError:
            pass

    return historical


def run_job_monitor(conn, sectors=None, cmas=None):
    """
    Main entry point. Fetch postings, aggregate, detect spikes, link to projects.

    Args:
        conn: SQLite connection
        sectors: list of sector keys to monitor (defaults to all)
        cmas: list of CMA names to monitor (defaults to all)

    Returns:
        dict with job_spikes, employer_counts, summary stats
    """
    sectors = sectors or list(SECTOR_SEARCH_TERMS.keys())
    cmas = cmas or list(CMA_REGIONS.keys())

    all_postings = []

    for sector in sectors:
        for cma in cmas:
            postings = fetch_job_postings(sector, cma, source="indeed")
            all_postings.extend(postings)

    print(f"[JOBS] Fetched {len(all_postings)} postings across {len(sectors)} sectors, {len(cmas)} CMAs")

    current_counts = aggregate_by_employer(all_postings)
    historical = get_historical_counts(conn)
    spikes = detect_hiring_spikes(current_counts, historical)

    if spikes:
        spikes = link_spikes_to_projects(spikes, conn)
        print(f"[JOBS] Detected {len(spikes)} hiring spikes")
        for s in spikes[:5]:
            print(f"  → {s['signal']}")

    run_date = datetime.now().strftime("%Y-%m-%d")
    save_job_snapshot(conn, current_counts, spikes, run_date)

    return {
        "job_postings_total": len(all_postings),
        "job_spikes": spikes,
        "job_employer_counts": current_counts,
        "job_sectors_monitored": sectors,
        "job_cmas_monitored": cmas,
    }
