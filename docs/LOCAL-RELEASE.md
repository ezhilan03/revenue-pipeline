# Dedicated-login local release

This is an operated local release, not Azure hosting or production isolation.
Requires the existing local PostgreSQL server and project Python environment.
Provisioning uses a loopback `_test` database connection solely to create a new,
separate database. It never resets the source database or other projects.

```sh
uv run python scripts/local_release.py init
```

Set `REVENUE_TEST_DATABASE_URL` securely before that command. The command prints
a new `.runtime/<id>` path and database name, not credentials. Credentials are
generated randomly and stored in a 0600 file inside a 0700 directory, excluded
from Git and Docker build context. The provisioning/owner credential is not saved.
Do not share `.runtime`, process environments or screenshots containing secrets.

Use the returned path for every command below:

```sh
uv run python scripts/local_release.py seed --runtime .runtime/<id>
uv run python scripts/local_release.py publish --runtime .runtime/<id>
uv run python scripts/local_release.py dispatch --runtime .runtime/<id>
uv run python scripts/local_release.py api --runtime .runtime/<id>
```

The last command runs an authenticated API on loopback port 8028. `/health/live`
is public liveness; `/exceptions`, `/cases`, `/forecast`, `/metrics` and history
require the private API key. Use the locally stored key through a trusted client;
do not publish it in README examples. Stop the foreground API with Ctrl-C.

The launcher passes only the chosen role's DSN to each process. It does not pass
the owner DSN or sibling passwords. The host operator can still read all locally
stored credentials; this is not an OS sandbox or a secret-management service.
Do not treat the current standalone Airflow container as isolated workers.

`seed` uses a synthetic incident plus an open opportunity, not the HTTP feed
cursor namespace. Do not point a live feed poller at this seeded database.
Source HTTP polling, raw archive/replay and Airflow scheduling have separate
verification flows documented in LOCAL-OPERATIONS.md and REPLAY.md.

The optional triage command calls an already-installed local Qwen model:

```sh
uv run python scripts/local_release.py triage --runtime .runtime/<id>
```

It does not download a model or contact a paid model provider. Unavailable or invalid
responses produce a labelled deterministic fallback. The pipeline does not depend
on the model. See FORECAST-AND-AI.md for evidence and limitations.

## Automated verification

```sh
uv run python scripts/verify_identity_flow.py
```

This creates a separate database, authenticates using four random restricted
logins, ingests data, runs real dbt twice, publishes/resolves a case, dispatches
idempotently and exercises a real Uvicorn HTTP process. Forty reads at concurrency
four verify stable release IDs. The API process receives no owner/sibling credentials.
All generated verification logins are disabled and their passwords cleared afterward;
the database evidence is retained. No existing database or role is deleted.

This verification is included in GitHub CI. Local latency is a small smoke result,
not a capacity guarantee, cloud benchmark or production SLA. The script still needs
an administrator to create its isolated test database and login roles.

## Remaining deployment gates

TLS/public routing, managed identity/secrets, automated credential rotation,
isolated scheduling workers, external notifications, retention and a cloud backup
policy are not supplied by this local launcher. No cloud resources are created.
