#!/usr/bin/env python3
"""
BirdBinder – Collection Progress Export
========================================
Fetches the user's bird collection progress from the BirdBinder API and
exports it as a CSV file.

Uses only the Python standard library (no pip dependencies).

Usage:
    python collection_export.py [OPTIONS]

Options:
    --base-url URL      API base URL          (default: http://localhost:8000)
    --api-key KEY       Bearer token           (default: empty / local mode)
    --output FILE       Output CSV path         (default: collection_progress.csv)
    --family-group      Group species by family (passes family_group=true)

Examples:
    python collection_export.py
    python collection_export.py --base-url https://api.birdbinder.example.com --api-key mykey
    python collection_export.py --output my_collection.csv --family-group
"""

import argparse
import csv
import json
import urllib.request
import urllib.error
import sys


def fetch_json(url: str, api_key: str = "") -> dict:
    """Perform a GET request and return parsed JSON."""
    req = urllib.request.Request(url)
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.reason}", file=sys.stderr)
        if exc.readable():
            body = exc.read().decode("utf-8", errors="replace")
            print(f"  Response body: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"Connection error: {exc.reason}", file=sys.stderr)
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export BirdBinder collection progress to CSV."
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Bearer token for authentication (default: empty)",
    )
    parser.add_argument(
        "--output",
        default="collection_progress.csv",
        help="Output CSV file path (default: collection_progress.csv)",
    )
    parser.add_argument(
        "--family-group",
        action="store_true",
        help="Request family-grouped data from the API",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Build the collection progress endpoint URL
    endpoint = f"{args.base_url.rstrip('/')}/api/collection/progress"
    if args.family_group:
        endpoint += "?family_group=true"

    print(f"Fetching collection progress from {endpoint} ...")
    data = fetch_json(endpoint, args.api_key)

    # The API may return the list directly or nested under a key — handle both
    if isinstance(data, dict):
        species_list = (
            data.get("species", data.get("results", data.get("entries", [])))
        )
    elif isinstance(data, list):
        species_list = data
    else:
        print("ERROR: Unexpected response format from the API.", file=sys.stderr)
        sys.exit(1)

    if not species_list:
        print("No species data found. Is the collection empty or the API key valid?")
        sys.exit(0)

    # Ensure species_list is a flat list even if grouped by family
    flat_rows: list[dict] = []
    for item in species_list:
        if isinstance(item, dict) and "species" in item:
            # Grouped format: { family: "...", species: [ ... ] }
            family_name = item.get("family", "")
            for sp in item["species"]:
                row = dict(sp)
                row.setdefault("family", family_name)
                flat_rows.append(row)
        elif isinstance(item, dict):
            flat_rows.append(item)

    # Write CSV
    columns = [
        "species_code",
        "common_name",
        "scientific_name",
        "family",
        "status",
        "rarity_tier",
    ]

    with open(args.output, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in flat_rows:
            writer.writerow(row)

    print(f"  ✓ Exported {len(flat_rows)} species to {args.output}")

    # Summary statistics
    discovered = sum(1 for r in flat_rows if str(r.get("status", "")).lower() == "discovered")
    total = len(flat_rows)
    pct = (discovered / total * 100) if total else 0

    print()
    print("=== Collection Summary ===")
    print(f"  Total species : {total}")
    print(f"  Discovered    : {discovered}")
    print(f"  Missing       : {total - discovered}")
    print(f"  Completion    : {pct:.1f}%")


if __name__ == "__main__":
    main()
