"""Synthetic healthcare-style claims generator.

Everything produced here is randomly generated. There is no PHI and no real
member, provider or claim data. Identifiers are opaque tokens, and diagnosis
and procedure codes are only illustrative values (no code descriptions).

A small share of rows is deliberately "dirty" so the cleaning job has real
work to do: exact duplicates, negative amounts, paid > billed, bad dates,
missing keys, unknown statuses, and messy casing or whitespace.

Output is deterministic for a given (ds, rows, seed), which keeps pipeline
reruns and tests reproducible.
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date
from pathlib import Path

COLUMNS = [
    "claim_id",
    "member_id",
    "provider_id",
    "service_date",
    "diagnosis_code",
    "procedure_code",
    "billed_amount",
    "paid_amount",
    "claim_status",
]

# Illustrative codes only.
DIAGNOSIS_CODES = [
    "E11.9", "I10", "J45.909", "M54.5", "F32.9", "N39.0",
    "K21.9", "E78.5", "J06.9", "R51.9", "Z00.00", "I25.10",
]
PROCEDURE_CODES = [
    "99213", "99214", "99203", "80053", "85025",
    "93000", "71046", "36415", "90471", "97110",
]
STATUSES = ["PAID", "DENIED", "PENDING"]
STATUS_WEIGHTS = [0.80, 0.12, 0.08]

DIRTY_KINDS = [
    "duplicate",
    "negative_billed",
    "paid_exceeds_billed",
    "bad_date",
    "missing_claim_id",
    "unknown_status",
    "messy_text",  # fixable by cleaning, should NOT be rejected
]


def _money(value: float) -> str:
    return f"{value:.2f}"


def _clean_row(rng: random.Random, ds: date, index: int) -> dict[str, str]:
    status = rng.choices(STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
    billed = round(rng.uniform(25, 2500), 2)
    paid = round(billed * rng.uniform(0.3, 0.95), 2) if status == "PAID" else 0.0
    return {
        "claim_id": f"CLM-{ds:%Y%m%d}-{index:06d}",
        "member_id": f"M{rng.randint(1, 5000):06d}",
        "provider_id": f"P{rng.randint(1, 400):05d}",
        "service_date": ds.isoformat(),
        "diagnosis_code": rng.choice(DIAGNOSIS_CODES),
        "procedure_code": rng.choice(PROCEDURE_CODES),
        "billed_amount": _money(billed),
        "paid_amount": _money(paid),
        "claim_status": status,
    }


def _make_dirty(
    rng: random.Random, row: dict[str, str], kind: str, ds: date, n: int
) -> dict[str, str]:
    dirty = dict(row)
    if kind not in ("messy_text", "missing_claim_id"):
        # Invalid rows get their own id so they do not collide with a valid claim.
        dirty["claim_id"] = f"CLM-{ds:%Y%m%d}-D{n:05d}"
    if kind == "negative_billed":
        dirty["billed_amount"] = _money(-abs(float(row["billed_amount"])))
    elif kind == "paid_exceeds_billed":
        dirty["paid_amount"] = _money(float(row["billed_amount"]) + rng.uniform(1, 100))
    elif kind == "bad_date":
        dirty["service_date"] = "2026-13-45"
    elif kind == "missing_claim_id":
        dirty["claim_id"] = ""
    elif kind == "unknown_status":
        dirty["claim_status"] = "UNKNOWN"
    elif kind == "messy_text":
        dirty["diagnosis_code"] = f"  {row['diagnosis_code'].lower()} "
        dirty["claim_status"] = row["claim_status"].title()
    return dirty


def generate_claims(
    ds: date,
    rows: int = 1000,
    seed: int = 42,
    dirty_rate: float = 0.05,
) -> list[dict[str, str]]:
    """Return `rows` clean claims for `ds` plus roughly `dirty_rate` extra dirty rows."""
    if rows < 0:
        raise ValueError("rows must be >= 0")
    if not 0 <= dirty_rate <= 1:
        raise ValueError("dirty_rate must be between 0 and 1")

    rng = random.Random(f"{ds.isoformat()}|{seed}")
    clean = [_clean_row(rng, ds, i) for i in range(rows)]
    output = list(clean)

    if clean:
        for n in range(int(rows * dirty_rate)):
            base = rng.choice(clean)
            kind = rng.choice(DIRTY_KINDS)
            if kind == "duplicate":
                output.append(dict(base))
            else:
                output.append(_make_dirty(rng, base, kind, ds, n))
    rng.shuffle(output)
    return output


def write_csv(rows: list[dict[str, str]], path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic claims as CSV.")
    parser.add_argument("--ds", required=True, help="Service date, YYYY-MM-DD")
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dirty-rate", type=float, default=0.05)
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    rows = generate_claims(
        date.fromisoformat(args.ds), args.rows, args.seed, args.dirty_rate
    )
    out = write_csv(rows, args.out)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    main()
