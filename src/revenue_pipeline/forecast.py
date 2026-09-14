"""Point-in-time, per-currency pipeline baseline. Not cash or recognized revenue."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal


def timestamp(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Forecast timestamps must include a timezone")
    return result


def forecast(history, as_of):
    cutoff = timestamp(as_of)
    current = {}
    for row in history:
        start = timestamp(row["known_from"])
        end = timestamp(row["known_to"]) if row["known_to"] else None
        if start <= cutoff and (end is None or cutoff < end):
            key = row["opportunity_id"]
            if key in current:
                raise ValueError("Overlapping known-time intervals")
            current[key] = row
    grouped = {}
    for row in current.values():
        if row["deleted"]:
            continue
        currency = row["currency"]
        if currency not in {"GBP", "USD", "EUR", "INR"}:
            raise ValueError("Unsupported currency")
        if type(row["amount_minor"]) is not int or row["amount_minor"] < 0:
            raise ValueError("Amounts must be nonnegative integer minor units")
        if row["stage"] not in {"open", "closed_won", "closed_lost"}:
            raise ValueError("Unsupported stage")
        grouped.setdefault(currency, []).append(row)
    output = []
    for currency, rows in sorted(grouped.items()):
        won = [r for r in rows if r["stage"] == "closed_won"]
        lost = [r for r in rows if r["stage"] == "closed_lost"]
        opened = [r for r in rows if r["stage"] == "open"]
        count = len(won) + len(lost)
        # Outcomes are restricted to those known at cutoff. Sparse cohorts use
        # an explicit neutral prior, not a fabricated learned conversion rate.
        probability = Decimal(len(won) + 1) / Decimal(count + 2) if count >= 5 else Decimal("0.5")
        amount = sum(r["amount_minor"] for r in opened)
        output.append({
            "currency": currency, "open_count": len(opened), "open_amount_minor": amount,
            "booked_amount_minor": sum(r["amount_minor"] for r in won),
            "closed_outcome_count": count, "open_win_probability": str(probability),
            "method": "smoothed_known_outcomes" if count >= 5 else "neutral_prior_sparse_cohort",
            "expected_open_bookings_minor": int((Decimal(amount) * probability).quantize(
                Decimal(1), rounding=ROUND_HALF_UP)),
        })
    return {"as_of": cutoff.isoformat(), "model_version": "known-outcomes-v1",
            "measure": "undated_expected_open_bookings_not_cash", "items": output}
