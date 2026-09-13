"""Seed an entirely synthetic missing-contract incident and optionally deliver its fix."""
import argparse
import json

from revenue_pipeline.store import checkpoint, ingest_page, initialize

CRM = {
    "source": "crm", "entity_id": "demo-001", "version": 1,
    "effective_at": "2026-01-05T12:00:00Z", "opportunity_id": "demo-001",
    "stage": "closed_won", "amount_minor": 1250000, "currency": "GBP",
}
CONTRACT = {
    "source": "contracts", "entity_id": "contract-001", "version": 1,
    "effective_at": "2026-01-05T12:00:00Z", "opportunity_id": "demo-001",
    "status": "signed",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--deliver-contract", action="store_true")
    args = parser.parse_args()
    initialize()
    c = checkpoint("crm")
    inserted = ingest_page("crm", [CRM], c, c + 1)
    c = checkpoint("contracts")
    records = [CONTRACT] if args.deliver_contract else []
    contracts = ingest_page("contracts", records, c, c + len(records))
    print(json.dumps({"crm_inserted": inserted, "contracts_inserted": contracts}))


if __name__ == "__main__":
    main()
