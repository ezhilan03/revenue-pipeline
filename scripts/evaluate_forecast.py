"""Handcrafted temporal holdouts, not evidence of real-world predictive accuracy."""

import json

from revenue_pipeline.forecast import forecast


def evaluate():
    results = []
    for currency, train_won, train_lost, future_won in [("GBP", 9, 3, 3), ("EUR", 1, 5, 1)]:
        history = []
        for i in range(train_won + train_lost):
            history.append({"opportunity_id": f"train-{i}", "currency": currency,
                            "amount_minor": 250, "deleted": False,
                            "known_from": "2026-01-01T00:00:00+00:00", "known_to": None,
                            "stage": "closed_won" if i < train_won else "closed_lost"})
        for i in range(4):
            opened = {"opportunity_id": f"holdout-{i}", "currency": currency,
                      "amount_minor": 250, "deleted": False, "stage": "open",
                      "known_from": "2026-01-15T00:00:00+00:00",
                      "known_to": "2026-03-01T00:00:00+00:00"}
            history += [opened, {**opened, "known_from": opened["known_to"], "known_to": None,
                                 "stage": "closed_won" if i < future_won else "closed_lost"}]
        predicted = forecast(history, "2026-02-01T00:00:00+00:00")["items"][0]
        actual = future_won * 250
        expected = predicted["expected_open_bookings_minor"]
        results.append({"currency": currency, "holdout_opportunities": 4,
                        "prediction_cutoff": "2026-02-01T00:00:00+00:00",
                        "outcome_observed_at": "2026-03-01T00:00:00+00:00",
                        "actual_bookings_minor": actual, "cohort_prediction_minor": expected,
                        "cohort_absolute_error_minor": abs(expected - actual),
                        "neutral_prediction_minor": 500,
                        "neutral_absolute_error_minor": abs(500 - actual)})
    return {"scope": "two_handcrafted_temporal_holdouts_not_real_accuracy", "results": results}


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
