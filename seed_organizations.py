"""
seed_organizations.py — One-time seed: extract proponents from projects, cluster, create organizations.

Usage: python seed_organizations.py
"""

from difflib import SequenceMatcher
from db import init_db, _normalize_org_name, resolve_organization, link_project_organization


def seed():
    conn = init_db()

    rows = conn.execute(
        "SELECT rowid, proponent FROM projects WHERE proponent IS NOT NULL AND proponent != ''"
    ).fetchall()

    print(f"Found {len(rows)} projects with proponents")

    # Collect unique normalized names
    name_map = {}  # normalized -> best (longest) original
    project_proponents = []  # (rowid, proponent)

    for row in rows:
        project_id = row[0]
        proponent = row[1].strip()
        if not proponent:
            continue
        project_proponents.append((project_id, proponent))
        norm = _normalize_org_name(proponent).lower()
        if norm not in name_map or len(proponent) > len(name_map[norm]):
            name_map[norm] = proponent

    unique_names = list(name_map.values())
    print(f"Unique normalized proponents: {len(unique_names)}")

    # Cluster similar names (SequenceMatcher >= 0.85)
    clusters = []  # list of sets of names
    assigned = set()

    for i, name_a in enumerate(unique_names):
        if name_a in assigned:
            continue
        cluster = {name_a}
        assigned.add(name_a)
        for j in range(i + 1, len(unique_names)):
            name_b = unique_names[j]
            if name_b in assigned:
                continue
            if SequenceMatcher(None, name_a.lower(), name_b.lower()).ratio() >= 0.85:
                cluster.add(name_b)
                assigned.add(name_b)
        clusters.append(cluster)

    print(f"Clustered into {len(clusters)} organizations")

    # For each cluster, pick the longest name as canonical
    canonical_map = {}  # any variant -> canonical
    for cluster in clusters:
        canonical = max(cluster, key=len)
        for variant in cluster:
            canonical_map[variant.strip()] = canonical

    # Create organizations and link projects
    linked = 0
    for project_id, proponent in project_proponents:
        canonical = canonical_map.get(proponent.strip(), proponent.strip())
        # resolve_organization will create if needed, find if alias exists
        org_id = resolve_organization(conn, canonical)
        if org_id:
            # Also register the original name as alias if different
            if proponent.strip() != canonical:
                norm = _normalize_org_name(proponent).lower()
                try:
                    conn.execute(
                        "INSERT INTO organization_aliases (organization_id, alias, alias_normalized) "
                        "VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                        (org_id, proponent.strip(), norm)
                    )
                    conn.commit()
                except Exception:
                    pass
            link_project_organization(conn, project_id, org_id, 'proponent')
            linked += 1

    org_count = conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0]
    alias_count = conn.execute("SELECT COUNT(*) FROM organization_aliases").fetchone()[0]
    link_count = conn.execute("SELECT COUNT(*) FROM project_organizations").fetchone()[0]
    print(f"\nSeeding complete:")
    print(f"  Organizations: {org_count}")
    print(f"  Aliases:       {alias_count}")
    print(f"  Project links: {link_count}")
    conn.close()


if __name__ == '__main__':
    seed()
