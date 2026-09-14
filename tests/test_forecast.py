from copy import deepcopy

import pytest

from revenue_pipeline.forecast import forecast


def row(key="a", **kwargs):
    return {"opportunity_id": key, "known_from": "2026-01-01T00:00:00+00:00",
            "known_to": None, "stage": "open", "amount_minor": 101, "currency": "GBP",
            "deleted": False, **kwargs}


def test_currency_separation_and_half_up_rounding():
    result = forecast([row(), row("b", currency="USD", amount_minor=300)],
                      "2026-01-02T00:00:00+00:00")
    assert [r["expected_open_bookings_minor"] for r in result["items"]] == [51, 150]


def test_future_outcome_cannot_leak_into_cutoff():
    past = row(known_to="2026-02-01T00:00:00+00:00")
    future = row(known_from="2026-02-01T00:00:00+00:00", stage="closed_won")
    cutoff = "2026-01-15T00:00:00+00:00"
    assert forecast([past, future], cutoff) == forecast([past], cutoff)
    assert forecast([past, future], "2026-02-01T00:00:00+00:00")["items"][0][
        "booked_amount_minor"] == 101


def test_deleted_and_lost_are_not_open_bookings():
    result = forecast([row(deleted=True), row("b", stage="closed_lost")],
                      "2026-02-01T00:00:00+00:00")
    assert result["items"][0]["expected_open_bookings_minor"] == 0


def test_known_outcome_baseline_and_input_unchanged():
    history = [row(str(i), stage="closed_won") for i in range(5)] + [row("open", amount_minor=700)]
    before = deepcopy(history)
    result = forecast(history, "2026-02-01T00:00:00+00:00")["items"][0]
    assert result["expected_open_bookings_minor"] == 600
    assert result["method"] == "smoothed_known_outcomes"
    assert history == before


def test_overlap_refused():
    with pytest.raises(ValueError, match="Overlapping"):
        forecast([row(), row()], "2026-02-01T00:00:00+00:00")


@pytest.mark.parametrize("changes", [{"amount_minor": True}, {"amount_minor": -1},
                                     {"currency": "XYZ"}, {"stage": "unknown"}])
def test_invalid_values_refused(changes):
    with pytest.raises(ValueError):
        forecast([row(**changes)], "2026-02-01T00:00:00+00:00")


def test_naive_cutoff_refused():
    with pytest.raises(ValueError, match="timezone"):
        forecast([], "2026-01-01")
