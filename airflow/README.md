# Gastronome Airflow Integration

This document introduces the use of Airflow within the Gastronome system. For more information on how to use Apache Airflow 3, please refer to [docs/airflow/README.md](https://github.com/WilliamOdinson/Gastronome/tree/main/docs/airflow/README.md).

## Starting and Stopping Airflow

To manage your Apache Airflow services conveniently, use the provided shell script `airflow_server.sh` as follows:

```bash
./airflow_server.sh <command>
```

> For example:
>
> ```bash
> ./airflow_server.sh start
> ```

**Available Commands:**

- `start`: Initializes the Airflow environment, verifies configurations, performs database migrations, and launches the Airflow API server and scheduler as background processes.
- `stop`: Gracefully stops any running Airflow processes (API server and scheduler).
- `restart`: Combines the actions of `stop` and `start`, restarting the Airflow services.
- `status`: Checks and reports the current running status (active/inactive) of Airflow services.

Ensure your Python 3.11 environment is managed via `pyenv`, and that **Airflow version 3.x** is installed before executing this script.
