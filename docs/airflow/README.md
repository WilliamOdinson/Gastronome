# Apache Airflow 3.x Quick Start Guide

## 1. Environment Setup

Set up a separate virtual environment to isolate your Airflow installation:

> [!Note]
>
> Python 3.11 is recommended for Airflow, rather than the Gastronome's Python 3.13 environment.

```bash
pyenv install 3.11
pyenv virtualenv 3.11 airflow
pyenv activate airflow

pip install apache-airflow apache-airflow-providers-postgres psycopg2-binary
```
