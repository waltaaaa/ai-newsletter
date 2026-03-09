"""GitHub Issues reader for user-submitted missing projects and corrections.

Fetches open issues from the repository using structured issue templates,
parses them into project dicts, and saves them via db.save_missed_project().
Processed issue numbers are tracked in dashboard_state to avoid re-processing.

Uses urllib.request (stdlib) — no new dependencies.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error

from db import get_dashboard_state, save_dashboard_state, save_missed_project

logger = logging.getLogger(__name__)

_REPO = "waltaaaa/ai-newsletter"
_API_BASE = f"https://api.github.com/repos/{_REPO}/issues"
_USER_AGENT = "CAN-Macro-Dashboard/1.0"
_STATE_KEY = "github_issues_last_id"

# Map display sector names to internal sector codes
_SECTOR_MAP = {
    "Oil & Gas": "oil_gas",
    "Mining": "mining",
    "Infrastructure": "infrastructure",
    "Power & Energy": "power_energy",
    "Manufacturing": "manufacturing",
    "Transport & Logistics": "transport_logistics",
    "Healthcare": "healthcare",
    "Education": "education",
    "Residential": "residential",
    "Commercial / Mixed Use": "commercial_mixed",
    "Agriculture": "agriculture",
    "Forestry": "forestry",
    "Defence": "defence",
    "Telecom": "telecom",
    "Indigenous": "indigenous",
    "Environment": "environment",
    "Tourism & Culture": "tourism_culture",
    "Government": "government",
}

# Map display province names to abbreviations used in database
_PROVINCE_MAP = {
    "Alberta": "AB",
    "British Columbia": "BC",
    "Manitoba": "MB",
    "New Brunswick": "NB",
    "Newfoundland and Labrador": "NL",
    "Northwest Territories": "NT",
    "Nova Scotia": "NS",
    "Nunavut": "NU",
    "Ontario": "ON",
    "Prince Edward Island": "PE",
    "Quebec": "QC",
    "Saskatchewan": "SK",
    "Yukon": "YT",
}


def _github_get(url: str) -> list:
    """Fetch JSON from GitHub API. Returns list of issues or empty list on error."""
    req = urllib.request.Request(url, headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/vnd.github+json",
    })
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _github_post(url: str, data: dict) -> dict:
    """POST JSON to GitHub API. Requires GITHUB_TOKEN."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {}
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _github_patch(url: str, data: dict) -> dict:
    """PATCH JSON to GitHub API. Requires GITHUB_TOKEN."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {}
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PATCH", headers={
        "User-Agent": _USER_AGENT,
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_issue_body(body: str) -> dict:
    """Parse structured issue template body into a dict of field -> value.

    GitHub YAML form issues produce body text like:
        ### Field Label

        value text

        ### Another Field

        another value
    """
    if not body:
        return {}
    fields = {}
    # Split on ### headers
    parts = re.split(r"^### ", body, flags=re.MULTILINE)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split("\n", 1)
        label = lines[0].strip()
        value = lines[1].strip() if len(lines) > 1 else ""
        # GitHub sometimes uses "_No response_" for optional empty fields
        if value == "_No response_":
            value = ""
        fields[label] = value
    return fields


def _close_issue(issue_number: int) -> None:
    """Comment on and close a processed issue. Requires GITHUB_TOKEN."""
    comment_url = f"{_API_BASE}/{issue_number}/comments"
    issue_url = f"{_API_BASE}/{issue_number}"
    try:
        _github_post(comment_url, {
            "body": "Thanks for the submission! This project has been added to the processing queue."
        })
        _github_patch(issue_url, {"state": "closed"})
    except Exception as e:
        logger.warning("Could not close issue #%d: %s", issue_number, e)


def _process_missing_project(conn, issue: dict, fields: dict) -> bool:
    """Process a missing-project issue. Returns True if saved, False if skipped."""
    source_url = fields.get("Source URL", "").strip()
    if not source_url:
        logger.warning("Issue #%d skipped: no source URL", issue["number"])
        return False

    project_name = fields.get("Project Name", "").strip()
    province_display = fields.get("Province / Territory", "").strip()
    province = _PROVINCE_MAP.get(province_display, province_display)
    sector_display = fields.get("Sector", "").strip()
    sector = _SECTOR_MAP.get(sector_display, sector_display)
    description = fields.get("Description", "").strip()
    estimated_value = fields.get("Estimated Value", "").strip()
    proponent = fields.get("Proponent / Developer", "").strip()

    project_dict = {
        "name": project_name,
        "province": province,
        "description": description,
        "source_url": source_url,
        "submitted_at": issue.get("created_at", ""),
        "data": json.dumps({
            "source": "github_issues",
            "issue_number": issue["number"],
            "issue_url": issue.get("html_url", ""),
            "sector": sector,
            "estimated_value": estimated_value,
            "proponent": proponent,
        }),
    }
    save_missed_project(conn, project_dict)
    return True


def _process_correction(conn, issue: dict, fields: dict) -> bool:
    """Process a project-correction issue. Returns True if saved, False if skipped."""
    source_url = fields.get("Source URL", "").strip()
    if not source_url:
        logger.warning("Correction issue #%d skipped: no source URL", issue["number"])
        return False

    project_name = fields.get("Project Name", "").strip()
    field_to_correct = fields.get("Field to Correct", "").strip()
    new_value = fields.get("Correct Value", "").strip()
    notes = fields.get("Additional Notes", "").strip()

    project_dict = {
        "name": project_name,
        "province": "",
        "description": f"Correction: {field_to_correct} -> {new_value}",
        "source_url": source_url,
        "submitted_at": issue.get("created_at", ""),
        "data": json.dumps({
            "source": "github_issues",
            "type": "correction",
            "issue_number": issue["number"],
            "issue_url": issue.get("html_url", ""),
            "project_name": project_name,
            "field_to_correct": field_to_correct,
            "new_value": new_value,
            "notes": notes,
        }),
    }
    save_missed_project(conn, project_dict)
    return True


def fetch_issue_submissions(conn) -> dict:
    """Fetch and process new issue submissions from GitHub Issues.

    Args:
        conn: SQLite connection (db.py interface).

    Returns:
        dict with keys: processed, new_projects, corrections, skipped_no_url.
        On error: {"skipped": True, "reason": "..."}.
    """
    result = {"processed": 0, "new_projects": 0, "corrections": 0, "skipped_no_url": 0}

    # Get last processed issue number
    last_id = get_dashboard_state(conn, _STATE_KEY)
    if last_id is None:
        last_id = 0
    else:
        last_id = int(last_id)

    max_seen = last_id
    all_issues = []

    # Fetch missing-project issues
    try:
        mp_url = f"{_API_BASE}?labels=missing-project&state=open&per_page=100"
        mp_issues = _github_get(mp_url)
        all_issues.extend([(issue, "missing-project") for issue in mp_issues])
    except Exception as e:
        logger.warning("GitHub API error (missing-project): %s", e)
        return {"skipped": True, "reason": f"GitHub API unreachable: {e}"}

    # Fetch project-correction issues
    try:
        pc_url = f"{_API_BASE}?labels=project-correction&state=open&per_page=100"
        pc_issues = _github_get(pc_url)
        all_issues.extend([(issue, "project-correction") for issue in pc_issues])
    except Exception as e:
        logger.warning("GitHub API error (project-correction): %s", e)
        return {"skipped": True, "reason": f"GitHub API unreachable: {e}"}

    # Process only new issues (number > last_id)
    for issue, label_type in all_issues:
        issue_num = issue.get("number", 0)
        if issue_num <= last_id:
            continue

        fields = _parse_issue_body(issue.get("body", ""))

        if label_type == "missing-project":
            saved = _process_missing_project(conn, issue, fields)
            if saved:
                result["new_projects"] += 1
            else:
                result["skipped_no_url"] += 1
        elif label_type == "project-correction":
            saved = _process_correction(conn, issue, fields)
            if saved:
                result["corrections"] += 1
            else:
                result["skipped_no_url"] += 1

        result["processed"] += 1
        if issue_num > max_seen:
            max_seen = issue_num

        # Close the issue if we have a token
        _close_issue(issue_num)

    # Update last processed issue number
    if max_seen > last_id:
        save_dashboard_state(conn, _STATE_KEY, max_seen)

    return result
