"""Canonical state code mapping for Malaysia's 16 states and federal territories.

This module provides the authoritative mapping between state name variants
(English, Malay, abbreviated, and colloquial forms) and the canonical 3-letter
codes used throughout the MyTourismSCI pipeline.

Every ingestion script that encounters state-level data should call
normalize_state_name() to convert raw state strings to canonical form before
writing to data/processed/.

Inputs:  Raw state name strings from any data source
Outputs: Standardised 3-letter state codes (e.g. "JOH", "SGR", "KUL")
Dependencies: None (pure Python)
"""

from __future__ import annotations

CANONICAL_STATE_CODES: dict[str, str] = {
    "Johor": "JOH",
    "Kedah": "KDH",
    "Kelantan": "KTN",
    "Melaka": "MLK",
    "Negeri Sembilan": "NSN",
    "Pahang": "PHG",
    "Pulau Pinang": "PNG",
    "Perak": "PRK",
    "Perlis": "PLS",
    "Selangor": "SGR",
    "Terengganu": "TRG",
    "Sabah": "SBH",
    "Sarawak": "SWK",
    "W.P. Kuala Lumpur": "KUL",
    "W.P. Labuan": "LBN",
    "W.P. Putrajaya": "PJY",
}

VALID_CODES: set[str] = set(CANONICAL_STATE_CODES.values())

_ALIAS_MAP: dict[str, str] = {
    # Johor
    "johor": "JOH",
    "johor bahru": "JOH",
    "johor darul ta'zim": "JOH",
    "johor darul takzim": "JOH",
    "joh": "JOH",

    # Kedah
    "kedah": "KDH",
    "kedah darul aman": "KDH",
    "kdh": "KDH",

    # Kelantan
    "kelantan": "KTN",
    "kelantan darul naim": "KTN",
    "ktn": "KTN",

    # Melaka
    "melaka": "MLK",
    "malacca": "MLK",
    "mlk": "MLK",

    # Negeri Sembilan
    "negeri sembilan": "NSN",
    "n. sembilan": "NSN",
    "n.sembilan": "NSN",
    "n sembilan": "NSN",
    "negeri sembilan darul khusus": "NSN",
    "nsn": "NSN",

    # Pahang
    "pahang": "PHG",
    "pahang darul makmur": "PHG",
    "phg": "PHG",

    # Pulau Pinang
    "pulau pinang": "PNG",
    "p. pinang": "PNG",
    "p.pinang": "PNG",
    "penang": "PNG",
    "png": "PNG",

    # Perak
    "perak": "PRK",
    "perak darul ridzuan": "PRK",
    "prk": "PRK",

    # Perlis
    "perlis": "PLS",
    "perlis indera kayangan": "PLS",
    "pls": "PLS",

    # Selangor
    "selangor": "SGR",
    "selangor darul ehsan": "SGR",
    "sgr": "SGR",
    "sel": "SGR",

    # Terengganu
    "terengganu": "TRG",
    "trengganu": "TRG",
    "terengganu darul iman": "TRG",
    "trg": "TRG",

    # Sabah
    "sabah": "SBH",
    "sbh": "SBH",

    # Sarawak
    "sarawak": "SWK",
    "swk": "SWK",

    # W.P. Kuala Lumpur
    "w.p. kuala lumpur": "KUL",
    "wp kuala lumpur": "KUL",
    "w.p kuala lumpur": "KUL",
    "wilayah persekutuan kuala lumpur": "KUL",
    "kuala lumpur": "KUL",
    "kl": "KUL",
    "kul": "KUL",

    # W.P. Labuan
    "w.p. labuan": "LBN",
    "wp labuan": "LBN",
    "w.p labuan": "LBN",
    "wilayah persekutuan labuan": "LBN",
    "labuan": "LBN",
    "lbn": "LBN",

    # W.P. Putrajaya
    "w.p. putrajaya": "PJY",
    "wp putrajaya": "PJY",
    "w.p putrajaya": "PJY",
    "wilayah persekutuan putrajaya": "PJY",
    "putrajaya": "PJY",
    "pjy": "PJY",
}


def normalize_state_name(name: str) -> str:
    """Map a state name, alias, or code to its canonical 3-letter code.

    Handles common Malay and English variants, abbreviations, and
    colloquial forms. Matching is case-insensitive and strips whitespace.

    Parameters
    ----------
    name : str
        Raw state name string from any data source.

    Returns
    -------
    str
        Canonical 3-letter state code.

    Raises
    ------
    ValueError
        If the input cannot be resolved to any known Malaysian state.
    """
    if not isinstance(name, str) or not name.strip():
        raise ValueError(
            f"Cannot normalise state name: received empty or non-string value {name!r}"
        )

    cleaned = name.strip()

    if cleaned in VALID_CODES:
        return cleaned

    key = cleaned.lower()
    if key in _ALIAS_MAP:
        return _ALIAS_MAP[key]

    raise ValueError(
        f"Unknown state name: {name!r}. "
        f"Expected one of the 16 Malaysian states or a recognised alias. "
        f"Valid codes: {sorted(VALID_CODES)}"
    )


if __name__ == "__main__":
    test_cases = [
        ("Johor", "JOH"),
        ("JOH", "JOH"),
        ("joh", "JOH"),
        ("  Selangor  ", "SGR"),
        ("Penang", "PNG"),
        ("Pulau Pinang", "PNG"),
        ("P. Pinang", "PNG"),
        ("W.P. Kuala Lumpur", "KUL"),
        ("Wilayah Persekutuan Kuala Lumpur", "KUL"),
        ("KL", "KUL"),
        ("Kuala Lumpur", "KUL"),
        ("Malacca", "MLK"),
        ("N. Sembilan", "NSN"),
        ("Sabah", "SBH"),
        ("Labuan", "LBN"),
    ]

    passed = 0
    failed = 0
    for raw, expected in test_cases:
        result = normalize_state_name(raw)
        status = "PASS" if result == expected else "FAIL"
        if status == "FAIL":
            failed += 1
            print(f"  {status}: normalize_state_name({raw!r}) = {result!r}, expected {expected!r}")
        else:
            passed += 1
            print(f"  {status}: normalize_state_name({raw!r}) = {result!r}")

    try:
        normalize_state_name("Not A State")
        print("  FAIL: Expected ValueError for unknown input")
        failed += 1
    except ValueError:
        print("  PASS: ValueError raised for unknown input")
        passed += 1

    print(f"\nSelf-test complete: {passed} passed, {failed} failed")
