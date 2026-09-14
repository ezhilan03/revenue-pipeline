"""Execute inside the pinned Airflow image; import checks do not prove scheduling."""
from airflow.models.dagbag import DagBag

bag = DagBag(dag_folder="/opt/revenue/dags", include_examples=False)
assert not bag.import_errors, bag.import_errors
dag = bag.dags.get("revenue_hourly")
assert dag is not None
assert dag.catchup is False
assert dag.max_active_runs == 1
assert set(dag.task_ids) == {"poll_sources", "dbt_quality_gate", "dispatch_simulated_tasks"}
assert dag.get_task("poll_sources").downstream_task_ids == {"dbt_quality_gate"}
assert dag.get_task("dbt_quality_gate").trigger_rule == "all_success"
assert dag.get_task("dbt_quality_gate").downstream_task_ids == {"dispatch_simulated_tasks"}
assert dag.get_task("dispatch_simulated_tasks").trigger_rule == "all_success"
print("DAG import, dependency, concurrency and failure-gate checks passed")
