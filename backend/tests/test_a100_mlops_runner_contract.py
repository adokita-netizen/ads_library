from app.tasks import runner


def test_a100_runner_exposes_mlops_tasks():
    assert runner._TASK_IMPORTS["mlops_retrain"] == "app.tasks.mlops_tasks:mlops_retrain_task"
    assert runner._TASK_IMPORTS["mlops_monitoring"] == "app.tasks.mlops_tasks:mlops_monitoring_task"


def test_a100_runner_loads_mlops_monitoring_callable():
    task = runner._load_task("mlops_monitoring")
    assert task is not None
    assert task.__name__ == "mlops_monitoring_task"
