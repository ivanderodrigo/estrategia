"""Read-only CLI to inspect the new public query-discovery layer.

It never writes intelligence.json and never promotes a search result to evidence.
"""
from __future__ import annotations

import argparse
import json

import requests

from engine.research.query_discovery import discover


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe public discovery without mutating canonical intelligence")
    parser.add_argument("entity", help="Entity or topic to search")
    parser.add_argument("--family", default="official", help="Fallback research family")
    parser.add_argument("--query", action="append", default=[], help="Explicit query; repeatable")
    parser.add_argument("--max-queries", type=int, default=4)
    parser.add_argument("--results-per-query", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=8.0)
    args = parser.parse_args()

    queries = args.query or [
        f'"{args.entity}" partners vendors',
        f'"{args.entity}" services solutions',
        f'"{args.entity}" case study customer',
        f'"{args.entity}" annual report technology',
    ]
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Westcon-Iberia-Decision-Intelligence/4.4.0 discovery-probe",
        "Accept": "text/html,application/rss+xml,application/xml,text/xml;q=0.9,*/*;q=0.5",
    })
    seeds, stats = discover(
        session,
        queries,
        fallback_family=args.family,
        providers=("bing_rss", "duckduckgo_html"),
        timeout_s=args.timeout,
        max_queries=args.max_queries,
        results_per_query=args.results_per_query,
    )
    print(json.dumps({
        "entity": args.entity,
        "discovery_only": True,
        "queries": queries[: args.max_queries],
        "stats": stats,
        "candidates": [
            {
                "url": seed.url,
                "family": seed.family,
                "source_type": seed.source_type,
                "source_grade": seed.source_grade,
            }
            for seed in seeds
        ],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
