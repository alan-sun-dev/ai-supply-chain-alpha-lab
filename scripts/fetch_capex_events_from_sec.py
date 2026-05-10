"""Auto-extract TSMC capex events from SEC EDGAR 6-K filings.

Pipeline (path C from research note):
1. Pull TSMC's filing index from `data.sec.gov` (CIK 0001046179).
2. Filter to 6-K filings landing in earnings-call windows (Jan/Apr/Jul/Oct,
   day 10-30). Other 6-Ks (monthly revenue, board resolutions, AGM) are
   skipped because they never contain capex guidance.
3. For each candidate accession, fetch its `index.json` and pick the press
   release exhibit (`*4q*`, `*guidance*`, `*highlights*`, `*press*`, `*release*`).
4. Strip HTML, run the parser, derive `capex_signal` / `revision_direction`
   by comparing to the previous quarter's midpoint.
5. Merge into `data/manual/tsmc_capex_events.csv`. Existing rows take
   precedence on conflict (manual curation > auto-extract).

SEC requires a real User-Agent. Configure
`config/data_sources.yaml: settings.sec_user_agent` first.

Usage:
    python scripts/fetch_capex_events_from_sec.py
    python scripts/fetch_capex_events_from_sec.py --start 2018-01-01
    python scripts/fetch_capex_events_from_sec.py --dry-run    # no merge
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from capex_alpha.sec_capex_parser import (  # noqa: E402
    CapexParse,
    derive_signal,
    parse_capex_text,
)
from capex_alpha.utils import (  # noqa: E402
    get_logger,
    load_data_sources_config,
    resolve_path,
)

logger = get_logger("fetch_capex_events_from_sec")

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
ACCESSION_INDEX = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/index.json"
ARCHIVE_FILE = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{name}"

# Filename keywords that indicate a press release / earnings highlights exhibit
# (in order of preference — first match wins).
PRESS_HINTS = [
    "guidance",
    "highlights",
    "press",
    "release",
    "4q",
    "1q",
    "2q",
    "3q",
    "4quarter",
    "1quarter",
    "2quarter",
    "3quarter",
]


def _http_get(url: str, headers: dict[str, str], timeout: int = 30) -> bytes:
    import requests
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def _user_agent() -> str:
    cfg = load_data_sources_config()
    ua = cfg.get("settings", {}).get("sec_user_agent", "")
    if not ua or "your-email@example.com" in ua:
        raise SystemExit(
            "SEC requires a real User-Agent. Edit "
            "config/data_sources.yaml: settings.sec_user_agent with your name + email."
        )
    return ua


def _list_filings(cik: str, ua: str) -> pd.DataFrame:
    url = SUBMISSIONS_URL.format(cik=cik)
    raw = _http_get(url, headers={"User-Agent": ua})
    payload = json.loads(raw)
    recent = payload.get("filings", {}).get("recent", {})
    if not recent:
        return pd.DataFrame()
    df = pd.DataFrame(recent)
    df["filingDate"] = pd.to_datetime(df["filingDate"])
    return df


def _is_earnings_window(d: pd.Timestamp) -> bool:
    """Earnings calls land Jan/Apr/Jul/Oct 11-25.

    Day 10 is the monthly revenue release (filed as 6-K with no capex content);
    days 26+ tend to be ADR-related housekeeping. The actual earnings call has
    been on day 12 (2023-01), 13 (2022-01), 14 (2020-04), 15 (2019-04, 2026-01),
    16 (2025-01), 17 (2024-04), 18 (2018-01, 2024-01), 20 (2023-04, 2023-07).
    Routine 6-Ks falling in this window are filtered separately by filename.
    """
    return d.month in {1, 4, 7, 10} and 11 <= d.day <= 25


def _looks_like_routine(primary: str | None) -> bool:
    """Names like tsm-revenue / monthend / board-resolution / dividend are not earnings."""
    if not primary:
        return False
    low = primary.lower()
    return any(k in low for k in ("revenue", "monthend", "board", "agm", "dividend",
                                   "boddate", "directors", "ceo", "treasurer",
                                   "namechange", "media", "namedirector"))


def _find_press_exhibit(
    cik_int: int,
    acc_clean: str,
    ua: str,
) -> str | None:
    """Return the filename of the press release exhibit, or None."""
    url = ACCESSION_INDEX.format(cik_int=cik_int, acc_clean=acc_clean)
    try:
        raw = _http_get(url, headers={"User-Agent": ua})
    except Exception as exc:  # noqa: BLE001
        logger.warning("  index fetch failed: %s", exc)
        return None
    items = json.loads(raw).get("directory", {}).get("item", [])

    htmls = [it["name"] for it in items if it["name"].lower().endswith((".htm", ".html"))]
    # Filter out generic SEC index pages
    htmls = [n for n in htmls if "index" not in n.lower()]

    # First pass: name contains a PRESS_HINTS keyword
    for hint in PRESS_HINTS:
        for name in htmls:
            if hint in name.lower():
                return name
    # Fallback: pick the largest non-cover HTML (cover doc is usually small)
    sized = [(it["name"], int(it.get("size") or 0))
             for it in items if it["name"] in htmls]
    if not sized:
        return None
    sized.sort(key=lambda t: -t[1])
    name, size = sized[0]
    if size < 5000:
        return None
    return name


def _extract_text(html: bytes) -> str:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def _parse_one_filing(
    cik_int: int,
    accession: str,
    primary: str,
    ua: str,
) -> tuple[CapexParse, str | None]:
    """Try press exhibit first; fall back to primary doc text."""
    acc_clean = accession.replace("-", "")
    exhibit = _find_press_exhibit(cik_int, acc_clean, ua)
    target = exhibit or primary

    url = ARCHIVE_FILE.format(cik_int=cik_int, acc_clean=acc_clean, name=target)
    try:
        html = _http_get(url, headers={"User-Agent": ua}, timeout=45)
    except Exception as exc:  # noqa: BLE001
        logger.warning("  fetch failed for %s: %s", target, exc)
        return parse_capex_text(""), None

    text = _extract_text(html)
    parsed = parse_capex_text(text)
    if not parsed.is_valid and exhibit and exhibit != primary:
        # Try primary doc as fallback
        url2 = ARCHIVE_FILE.format(cik_int=cik_int, acc_clean=acc_clean, name=primary)
        try:
            html2 = _http_get(url2, headers={"User-Agent": ua}, timeout=45)
            text2 = _extract_text(html2)
            parsed = parse_capex_text(text + " " + text2)
        except Exception:  # noqa: BLE001
            pass
    return parsed, url


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default=datetime.today().strftime("%Y-%m-%d"))
    parser.add_argument("--throttle", type=float, default=0.2)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print extracted rows but do not write CSV.")
    args = parser.parse_args()

    cfg = load_data_sources_config()["sources"].get("sec_edgar", {})
    cik = str(cfg.get("cik", "0001046179")).zfill(10)
    cik_int = int(cik)
    ua = _user_agent()

    logger.info("Fetching SEC submissions index for CIK=%s …", cik)
    filings = _list_filings(cik, ua)
    if filings.empty:
        logger.error("No filings returned. Check CIK / network.")
        return 1

    start = pd.Timestamp(args.start)
    end = pd.Timestamp(args.end)

    earnings_mask = (
        (filings["form"] == "6-K")
        & (filings["filingDate"] >= start)
        & (filings["filingDate"] <= end)
        & filings["filingDate"].apply(_is_earnings_window)
        & (~filings["primaryDocument"].apply(_looks_like_routine))
    )
    target = filings[earnings_mask].sort_values("filingDate").reset_index(drop=True)
    logger.info("Found %d candidate earnings 6-Ks in [%s, %s].",
                len(target), args.start, args.end)
    if target.empty:
        return 0

    # Group by quarter so multiple 6-Ks on same earnings day collapse to one event.
    target["quarter_key"] = target["filingDate"].dt.to_period("Q")
    target = target.drop_duplicates(subset=["quarter_key"], keep="first").reset_index(drop=True)
    logger.info("After collapsing to one filing per quarter: %d events.", len(target))

    new_rows: list[dict] = []
    prior_midpoint: float | None = None

    for _, row in target.iterrows():
        date = row["filingDate"].date().isoformat()
        accession = row["accessionNumber"]
        primary = row.get("primaryDocument") or ""
        logger.info("Parsing %s  acc=%s  primary=%s", date, accession, primary)

        parsed, url = _parse_one_filing(cik_int, accession, primary, ua)
        time.sleep(args.throttle)

        if not parsed.is_valid:
            logger.info("  → no capex range detected; skipping.")
            continue

        signal, direction = derive_signal(parsed.capex_midpoint, prior_midpoint)
        logger.info(
            "  → low=%.1f  high=%.1f  mid=%.2f  vs prior=%s  signal=%s  drivers=%s",
            parsed.capex_low, parsed.capex_high, parsed.capex_midpoint,
            f"{prior_midpoint:.2f}" if prior_midpoint else "NA",
            signal, parsed.technology_drivers,
        )
        new_rows.append({
            "event_date": date,
            "event_type": "earnings_call",
            "capex_signal": signal,
            "capex_value_low_usd_bn": parsed.capex_low,
            "capex_value_high_usd_bn": parsed.capex_high,
            "capex_midpoint_usd_bn": parsed.capex_midpoint,
            "prior_guidance_midpoint_usd_bn": prior_midpoint,
            "revision_direction": direction,
            "technology_driver": "/".join(parsed.technology_drivers) or "",
            "source_title": f"SEC 6-K {accession}",
            "source_url": url or "",
            "analyst_note": (parsed.matched_excerpt or "")[:240],
        })
        prior_midpoint = parsed.capex_midpoint

    if not new_rows:
        logger.warning("No capex events extracted.")
        return 0

    fresh = pd.DataFrame(new_rows)
    if args.dry_run:
        print()
        print("=== Extracted (dry run, not written) ===")
        print(fresh[[
            "event_date", "capex_signal", "capex_value_low_usd_bn",
            "capex_value_high_usd_bn", "capex_midpoint_usd_bn",
            "prior_guidance_midpoint_usd_bn", "revision_direction",
            "technology_driver",
        ]].to_string(index=False))
        return 0

    out_path = resolve_path("data/manual/tsmc_capex_events.csv")
    if out_path.exists():
        existing = pd.read_csv(out_path)
        # Existing manual rows take precedence on date conflict.
        existing["event_date"] = pd.to_datetime(existing["event_date"]).dt.strftime("%Y-%m-%d")
        manual_dates = set(existing["event_date"])
        fresh_unique = fresh[~fresh["event_date"].isin(manual_dates)]
        merged = pd.concat([existing, fresh_unique], ignore_index=True)
        logger.info("Manual: %d, Auto-only-new: %d, Merged: %d",
                    len(existing), len(fresh_unique), len(merged))
    else:
        merged = fresh

    merged["event_date"] = pd.to_datetime(merged["event_date"])
    merged = (
        merged.sort_values("event_date")
        .drop_duplicates(subset=["event_date"], keep="first")
        .reset_index(drop=True)
    )
    merged["event_date"] = merged["event_date"].dt.strftime("%Y-%m-%d")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out_path, index=False)
    logger.info("Wrote %s rows → %s", len(merged), out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
