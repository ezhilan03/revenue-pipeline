# Local monitoring and notification audit

Set `DATABASE_URL` to an initialized local database reachable from Docker and set
`REVENUE_API_KEY` to a local secret. Do not point this stack at a test database
while pytest is running. On macOS, a host database can use `host.docker.internal`.
Also set `GRAFANA_ADMIN_PASSWORD` to a separate local password. Grafana configuration
is included on loopback port 3007. Dashboard provisioning, datasource connectivity
and the visible stat panels have been verified against live local metrics.

```sh
docker compose -p revenue-monitor -f compose.monitoring.yaml up -d --build
```

Ports are loopback-only: API 8018, notification audit 8037, Prometheus 9097 and
Alertmanager 9098. Prometheus and Alertmanager use Compose secret files for the
custom authentication header. The API/receiver currently receive the same local
key via environment; production requires separate identities, TLS and secret rotation.

## Signals

- API scrape failure for 30 seconds: critical notification.
- Latest job not successful for two minutes: warning (includes never-run/stuck jobs).
- Last successful job completion older than two hours for two minutes: warning.

Job metrics carry their own `job` label; Prometheus retains this as `exported_job`
alongside its scrape job `revenue-api`. Alert grouping preserves both labels.
No external recipients are configured. Alerts go to the local authenticated
receiver; SQLite persists accepted firing/resolved notifications on a Docker volume.
Identical normalized payloads are deduplicated, while changed/recovered alerts are
recorded. Audit retrieval returns the most recent 100 receipts; payloads remain
in SQLite. This proves local delivery, not human paging or email delivery.

## Exercise and inspect

Stop only this Compose project's API for at least 40 seconds. Confirm
`RevenueApiUnavailable` fires in Prometheus and a firing receipt appears at
`GET /notifications` with `X-API-Key`. Restart that API, wait for successful scraping
and the resolved receipt. Do not stop the unrelated older development API.
Exact waits can vary due to scrape/evaluation and notification batching intervals.

```sh
docker compose -p revenue-monitor -f compose.monitoring.yaml stop api
docker compose -p revenue-monitor -f compose.monitoring.yaml start api
```

Do not execute both immediately when testing an outage. Prometheus data is capped
at 100 MB/24 hours (not a hard total-disk cap). Audit retention, body-size limits,
receiver-outage monitoring, delivery-retry fault injection and Grafana dashboards
remain release work. The receiver being separate from the API allows API outage
notifications, but does not eliminate shared-host failure risk.

Stop the local stack without discarding evidence:

```sh
docker compose -p revenue-monitor -f compose.monitoring.yaml stop
```

References: [Prometheus configuration](https://prometheus.io/docs/prometheus/latest/configuration/configuration/),
[Alertmanager webhooks](https://prometheus.io/docs/alerting/latest/configuration/).
