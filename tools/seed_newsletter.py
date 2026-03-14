"""
seed_newsletter.py — One-time script to seed SQLite with the March 2 newsletter.

Loads from newsletters_backup_2026-03-03.json and pushes to:
- dashboard_state/newsletter_2026-03-02
- dashboard_state/latest
- dashboard_state/latest_briefing (placeholder)

NOTE: Migrated from Firestore to SQLite (db.py) for DB-07 compliance.
This is a one-time seeding script.

Usage:
    python seed_newsletter.py
"""

import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import json
import os
from dotenv import load_dotenv
load_dotenv()

from db import init_db, save_dashboard_state


def seed():
    conn = init_db()

    # Load backup
    with open('newsletters_backup_2026-03-03.json', 'r', encoding='utf-8') as f:
        backup = json.load(f)

    mar2 = backup.get('2026-03-02')
    if not mar2:
        print("[ERROR] No 2026-03-02 entry in backup")
        conn.close()
        return

    # Fix missing fields
    mar2['updated_at'] = '2026-03-02'
    mar2['edition'] = 'EDITION: FEB 24 \u2013 MAR 02 // STATUS: AI-SYNTHESIZED'

    # Write to dashboard_state with newsletter_ prefix
    print("[SEED] Writing newsletter_2026-03-02...")
    save_dashboard_state(conn, 'newsletter_2026-03-02', mar2)

    print("[SEED] Writing latest...")
    save_dashboard_state(conn, 'latest', mar2)

    # Write placeholder briefing to dashboard_state/latest_briefing
    print("[SEED] Writing latest_briefing...")
    briefing = {
        "content": (
            "HEADLINE\n"
            "The CAN-MACRO Strategic Dashboard is now live. "
            "The first automated weekly intelligence briefing will be generated on March 9, 2026.\n\n"
            "MACRO PULSE\n"
            "National economic indicators are being tracked across 13 provinces and territories. "
            "The dashboard monitors Bank of Canada rates, StatCan employment and CPI data, "
            "CMHC housing starts, and GDP figures from primary government sources.\n\n"
            "UNDER THE MICROSCOPE\n"
            "This section will feature a weekly deep-dive on the dominant economic story, "
            "drawing connections between macro indicators and the project pipeline.\n\n"
            "PROVINCIAL SPOTLIGHT\n"
            "Each week, one province with notable project activity will be highlighted "
            "with specific data on new discoveries, value changes, and status updates.\n\n"
            "SECTOR WATCH\n"
            "The pipeline tracks 18 NAICS-aligned sectors across 14 discovery tiers. "
            "Sector momentum and geographic shifts will be reported weekly.\n\n"
            "PROJECT TRACKER\n"
            "The database currently tracks projects discovered through government registries, "
            "Google News RSS (759 queries), RSS feeds (201+), and municipal development applications.\n\n"
            "MARKETS & COMMODITIES\n"
            "Commodity prices, equity indices, FX rates, and yield curves are fetched from "
            "Yahoo Finance, Bank of Canada, and FRED. All values are primary-source verified.\n\n"
            "LOOKING AHEAD\n"
            "Upcoming scheduled events including Bank of Canada rate decisions, "
            "StatCan releases, and federal/provincial budget dates will be tracked here."
        ),
        "date": "2026-03-02",
        "week_number": 9,
        "cost_usd": 0,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    save_dashboard_state(conn, 'latest_briefing', briefing)

    # Also seed statcan_indicators if backup exists
    try:
        with open('indicators_backup_2026-03-03.json', 'r', encoding='utf-8') as f:
            ind_backup = json.load(f)
        if ind_backup.get('latest'):
            print("[SEED] Writing statcan_indicators_latest...")
            save_dashboard_state(conn, 'statcan_indicators_latest', ind_backup['latest'])
    except FileNotFoundError:
        print("[SEED] No indicators backup found, skipping")

    conn.close()
    print("[SEED] Done. Dashboard should now show March 2 data.")


if __name__ == '__main__':
    seed()
