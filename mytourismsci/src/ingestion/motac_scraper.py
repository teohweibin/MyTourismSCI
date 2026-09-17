"""MOTAC hotel registry scraper for MyTourismSCI.

Scrapes three MOTAC hotel data sources via the WordPress AJAX API
and one static HTML page:
  1. Registered Hotels (hotel-berdaftar) — ~5,550 records
  2. Rated Hotels (penggredan-hotel) — ~757 records with star ratings
  3. Green Hotels (penggredan-green-hotel) — ~27 records
  4. ASEAN Green Hotel Awards — ~35 entries from static tables

Entry-point: run_all_scrapers()

Inputs:  MOTAC website (motac.gov.my AJAX + static HTML)
Outputs: 4 parquet files in data/raw/motac/
Dependencies: requests, beautifulsoup4, pandas, src.harmonization.state_codes
"""

from __future__ import annotations

import logging
import math
import re
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from src.harmonization.state_codes import normalize_state_name

logger = logging.getLogger(__name__)

AJAX_URL = "https://www.motac.gov.my/wp-admin/admin-ajax.php"
ASEAN_AWARDS_URL = (
    "https://www.motac.gov.my/asean-tourism-award-category/"
    "asean-tourism-awards/asean-green-hotel-awards/"
)

OUTPUT_DIR = Path("data/raw/motac")

_USER_AGENT = "MyTourismSCI/1.0 (DOSM Datathon 2026 academic research)"
_REQUEST_DELAY = 1.0
_PER_PAGE = 100
_REQUEST_TIMEOUT = 30


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _USER_AGENT})
    return s


# ---------------------------------------------------------------------------
# State extraction from address strings
# ---------------------------------------------------------------------------

def _extract_state_from_address(address: str) -> str | None:
    """Extract Malaysian state code from a MOTAC address string.

    Splits on commas and tests each segment from rightmost to leftmost
    against the state normalizer.
    """
    if not address or not isinstance(address, str):
        return None

    segments = [seg.strip() for seg in address.split(",") if seg.strip()]

    for seg in reversed(segments):
        cleaned = re.sub(r"\b\d{5}\b", "", seg).strip()
        cleaned = re.sub(r"^\d+\s*", "", cleaned).strip()
        if not cleaned:
            continue
        try:
            return normalize_state_name(cleaned)
        except ValueError:
            continue

    return None


# ---------------------------------------------------------------------------
# AJAX scraper core
# ---------------------------------------------------------------------------

def _fetch_ajax_page(
    session: requests.Session,
    kategori: str,
    page: int,
    per_page: int = _PER_PAGE,
) -> dict:
    resp = session.post(
        AJAX_URL,
        data={
            "action": "motac_semakan_filter",
            "kategori": kategori,
            "search": "",
            "negeri": "",
            "klasifikasi": "",
            "jenis": "",
            "page": str(page),
            "per_page": str(per_page),
        },
        timeout=_REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _parse_cards(html: str, kategori: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(".motac-card")
    rows: list[dict] = []

    for card in cards:
        name_el = card.select_one(".company-name")
        addr_el = card.select_one(".company-address")
        phone_el = card.select_one(".company-phone")
        tempoh_el = card.select_one(".col-tempoh")

        name = name_el.get_text(strip=True) if name_el else ""
        address = addr_el.get_text(strip=True) if addr_el else ""
        phone = ""
        if phone_el:
            phone = phone_el.get_text(strip=True)
            phone = re.sub(r"\s+", " ", phone).strip()

        row: dict = {
            "name": name,
            "address": address,
            "phone": phone,
        }

        if tempoh_el:
            tempoh_text = tempoh_el.get_text(strip=True)
            if kategori == "hotel-berdaftar":
                row["registration_date"] = tempoh_text
            else:
                row["period"] = tempoh_text

        if kategori == "penggredan-hotel":
            star_div = card.select_one(".star-rating")
            if star_div:
                stars = len(star_div.select("span"))
                row["star_rating"] = stars
            orchid = card.select_one(".motac-orchid-badge")
            if orchid:
                row["orchid_rating"] = True
                row["star_rating"] = 0

        rows.append(row)

    return rows


def _scrape_ajax_kategori(
    kategori: str,
    label: str,
) -> pd.DataFrame:
    session = _session()

    logger.info("Fetching %s page 1 to determine total records...", label)
    data = _fetch_ajax_page(session, kategori, page=1)
    if not data.get("success"):
        logger.error("AJAX request failed for %s", label)
        return pd.DataFrame()

    total = int(data["data"]["total"])
    total_pages = math.ceil(total / _PER_PAGE)
    logger.info("%s: %d total records, %d pages", label, total, total_pages)

    all_rows = _parse_cards(data["data"]["html"], kategori)
    logger.info("  Page 1/%d: %d records parsed", total_pages, len(all_rows))

    for page_num in range(2, total_pages + 1):
        time.sleep(_REQUEST_DELAY)
        try:
            data = _fetch_ajax_page(session, kategori, page=page_num)
            if not data.get("success"):
                logger.warning("Page %d failed for %s", page_num, label)
                continue
            rows = _parse_cards(data["data"]["html"], kategori)
            all_rows.extend(rows)
            if page_num % 10 == 0 or page_num == total_pages:
                logger.info(
                    "  Page %d/%d: %d cumulative records",
                    page_num, total_pages, len(all_rows),
                )
        except requests.RequestException as exc:
            logger.warning(
                "Request error on page %d of %s: %s", page_num, label, exc
            )
            time.sleep(3)
            try:
                data = _fetch_ajax_page(session, kategori, page=page_num)
                if data.get("success"):
                    all_rows.extend(
                        _parse_cards(data["data"]["html"], kategori)
                    )
            except Exception:
                logger.error("Retry failed on page %d of %s", page_num, label)

    logger.info("%s scrape complete: %d records", label, len(all_rows))

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    df["state_code"] = df["address"].apply(_extract_state_from_address)
    n_missing = df["state_code"].isna().sum()
    pct_missing = n_missing / len(df) * 100
    logger.info(
        "%s state extraction: %d/%d failed (%.1f%%)",
        label, n_missing, len(df), pct_missing,
    )
    if n_missing > 0:
        failed = df.loc[df["state_code"].isna(), ["name", "address"]]
        for _, r in failed.iterrows():
            logger.warning(
                "  State parse failure: name=%r address=%r",
                r["name"], r["address"],
            )

    return df


# ---------------------------------------------------------------------------
# ASEAN Green Hotel Awards (static HTML)
# ---------------------------------------------------------------------------

def _scrape_asean_green_awards() -> pd.DataFrame:
    session = _session()
    logger.info("Fetching ASEAN Green Hotel Awards page...")
    resp = session.get(ASEAN_AWARDS_URL, timeout=_REQUEST_TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows: list[dict] = []
    current_level = ""
    current_edition = ""

    content = soup.select_one("article, .entry-content, main")
    if not content:
        logger.error("Cannot find main content on ASEAN awards page")
        return pd.DataFrame()

    for element in content.descendants:
        if element.name == "h2":
            text = element.get_text(strip=True)
            upper = text.upper()
            if "PERINGKAT" in upper and "ASEAN" in upper:
                current_level = "ASEAN"
            elif "KEBANGSAAN" in upper:
                current_level = "National"

            edition_match = re.search(
                r"\((\d+)[A-Z]{2}\)\s+(\d{4})-(\d{4})", text
            )
            if edition_match:
                current_edition = (
                    f"{edition_match.group(1)}th "
                    f"{edition_match.group(2)}-{edition_match.group(3)}"
                )

        if element.name == "table":
            trs = element.select("tr")
            for tr in trs[1:]:
                cells = tr.select("td")
                if len(cells) < 2:
                    continue
                hotel_name = cells[0].get_text(strip=True)
                state_raw = cells[1].get_text(strip=True)
                phone = cells[2].get_text(strip=True) if len(cells) > 2 else ""

                state_code = None
                try:
                    state_code = normalize_state_name(state_raw)
                except ValueError:
                    logger.warning(
                        "ASEAN awards state parse failure: %r", state_raw
                    )

                rows.append({
                    "name": hotel_name,
                    "state_raw": state_raw,
                    "state_code": state_code,
                    "phone": phone if phone != "-" else "",
                    "award_level": current_level,
                    "award_edition": current_edition,
                })

    logger.info("ASEAN Green Hotel Awards: %d entries parsed", len(rows))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scrape_registered_hotels() -> pd.DataFrame:
    return _scrape_ajax_kategori("hotel-berdaftar", "Registered Hotels")


def scrape_rated_hotels() -> pd.DataFrame:
    return _scrape_ajax_kategori("penggredan-hotel", "Rated Hotels")


def scrape_green_hotels() -> pd.DataFrame:
    return _scrape_ajax_kategori("penggredan-green-hotel", "Green Hotels")


def scrape_asean_green_awards() -> pd.DataFrame:
    return _scrape_asean_green_awards()


def run_all_scrapers() -> dict[str, pd.DataFrame]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: dict[str, pd.DataFrame] = {}

    scrapers = [
        ("registered", scrape_registered_hotels, "motac_hotels_registered.parquet"),
        ("rated", scrape_rated_hotels, "motac_hotels_rated.parquet"),
        ("green", scrape_green_hotels, "motac_hotels_green.parquet"),
        ("asean_awards", scrape_asean_green_awards, "motac_asean_green_awards.parquet"),
    ]

    for key, func, filename in scrapers:
        try:
            df = func()
            if not df.empty:
                out_path = OUTPUT_DIR / filename
                df.to_parquet(out_path, index=False)
                logger.info("Wrote %s (%d rows) → %s", key, len(df), out_path)
            else:
                logger.warning("No data for %s — skipping write", key)
            results[key] = df
        except Exception as exc:
            logger.error("Scraper %s failed: %s", key, exc)
            results[key] = pd.DataFrame()

    logger.info("=== MOTAC Scrape Summary ===")
    for key, df in results.items():
        n_states = (
            df["state_code"].notna().sum() if "state_code" in df.columns else 0
        )
        n_total = len(df)
        logger.info(
            "  %s: %d records, %d with state (%s)",
            key,
            n_total,
            n_states,
            f"{n_states / n_total * 100:.1f}%" if n_total > 0 else "N/A",
        )

    return results


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    run_all_scrapers()
