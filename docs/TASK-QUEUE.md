# Local incident task queue

Validated publication updates cases and queues lifecycle events in the same
transaction as the frozen release pointer. If publication rolls back, the case
changes and queued events roll back too. The case key combines opportunity ID
and reason; a generation distinguishes a reopened incident from the first one.

Repeated publication does not generate another open task. A resolved case emits
a resolution event; reopening increments its generation. Evidence updates on
an already open case are visible in `/cases` without creating a new task.
Resolution evidence references the previous incident plus the resolving release;
absence in a valid release is not proof of a successful external business action.

`python -m revenue_pipeline.outbox` sends up to 100 queued events to a database-local
simulator. Pending rows are locked with `SKIP LOCKED`; simulator acceptance and
delivery acknowledgement commit together. Retrying/concurrent dispatch does not
duplicate event keys. This is not an external exactly-once delivery guarantee.
Events are an audit stream, not a remote mutable ticket whose order is guaranteed
across concurrent workers. A real downstream system needs idempotency and ordering.

Airflow sequence: poll and archive -> validate/publish/queue -> simulated dispatch.
The dispatcher runs only after successful publication. The authenticated `/cases`
endpoint returns current lifecycle state; it can advance independently between
requests, and each case carries its publication release ID.

Monitoring adds open-case and pending-outbox gauges and a five-minute backlog alert.
Grafana provisioning files define panels for those gauges, scrape health, job
freshness and latest attempt state. Grafana runtime and datasource connectivity
are verified; visible stat panels showed API up, one open incident and zero backlog.

No actual CRM tasks, Slack messages, emails or customer actions are created.
Queue retention, external adapters and dead-letter policies remain future work.
