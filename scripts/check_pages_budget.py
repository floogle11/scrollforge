"""Conservative project budgets, well below GitHub Pages' hosting limits."""
import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEED_BUDGET = 5 * 1024 * 1024
SITE_BUDGET = 20 * 1024 * 1024
FILE_BUDGET = 5 * 1024 * 1024


def check_budget(docs=ROOT / "docs"):
    files = [path for path in docs.rglob("*") if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    feed = (docs / "data/feed.json").read_bytes()
    errors = []
    if len(feed) > FEED_BUDGET:
        errors.append("feed.json exceeds the 5 MiB project budget")
    if total > SITE_BUDGET:
        errors.append("published site exceeds the 20 MiB project budget")
    for path in files:
        if path.stat().st_size > FILE_BUDGET:
            errors.append(f"{path.relative_to(docs)} exceeds the 5 MiB per-file budget")
    marker = json.loads((docs / "data/feed-meta.json").read_text(encoding="utf-8"))
    if marker != {"last_updated": json.loads(feed)["last_updated"], "bytes": len(feed)}:
        errors.append("feed-meta.json must match feed.json; regenerate with python -m worker.study_bank")
    report = {"site_bytes": total, "feed_bytes": len(feed), "feed_gzip_bytes": len(gzip.compress(feed)),
              "site_budget_bytes": SITE_BUDGET, "feed_budget_bytes": FEED_BUDGET,
              "full_feed_transfers_per_100GB_uncompressed": 100_000_000_000 // max(1, len(feed)),
              "errors": errors}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", type=Path, default=ROOT / "docs")
    report = check_budget(parser.parse_args().docs)
    print(json.dumps(report, indent=2))
    return int(bool(report["errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
