# Apache Airflow 3.x Quick Start Guide

This guide provides a concise quick-start procedure for setting up Apache Airflow 3.x, focusing on key configuration steps for a robust deployment. An example configuration with custom settings is provided in [docs/airflow/airflow.cfg](https://github.com/WilliamOdinson/Gastronome/blob/main/docs/airflow/airflow.cfg).

## 1  Environment Setup

To avoid conflicts with other Python packages, start by creating a dedicated virtual environment for your Airflow installation.

> [!NOTE]
>
> Python 3.11 is recommended for Apache Airflow. According to the [official documentation](https://airflow.apache.org/docs/apache-airflow/stable/start.html#quick-start), supported Python versions are 3.9 through 3.12. Avoid using Python 3.13, which is not currently supported.

```bash
pyenv install 3.11
pyenv virtualenv 3.11 airflow
pyenv activate airflow

pip install apache-airflow apache-airflow-providers-postgres psycopg2-binary
```

## 2  Configuring PostgreSQL as the Metadata Backend

By default, Airflow uses an embedded SQLite database, which is intended only for development and testing. The [official documentation](https://airflow.apache.org/docs/apache-airflow/stable/howto/set-up-database.html) strongly recommends using a more robust database for production or multi-user environments to enable features like concurrent scheduling. Here, PostgreSQL is recommended as the metadata backend. The supported PostgreSQL versions are 12-16; for example, the Gastronome project uses version 14.18 for stability.

First, create the Airflow metadata database and user by logging into PostgreSQL and running the following commands:

```sql
CREATE DATABASE airflow ENCODING 'UTF8';
-- For security, change the default password 'airflow' in production!
CREATE USER airflow WITH PASSWORD 'airflow';

GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;
```

Next, configure the connection to PostgreSQL in Airflow. In Airflow 3.x, set the SQLAlchemy connection string in the `[database]` section of your `airflow.cfg` file:

```ini
[database]
sql_alchemy_conn = postgresql+psycopg2://airflow:airflow@localhost:5432/airflow
```

Alternatively, you can specify the connection using an environment variable:

```bash
export AIRFLOW__DATABASE__SQL_ALCHEMY_CONN="postgresql+psycopg2://airflow:airflow@localhost:5432/airflow"
```

> [!NOTE]
>
> Airflow components, including the Webserver, Scheduler, and Executor/Worker, can open a large number of concurrent connections to the metadata database. Because PostgreSQL uses a "one connection per process" model, this can easily exhaust system memory or available file descriptors, especially in production environments. **It is strongly recommended to use [PgBouncer](https://www.pgbouncer.org/) as a connection pooler in production deployments** to efficiently manage database connections and prevent resource exhaustion. For instructions on integrating PgBouncer with PostgreSQL, refer to [docs/pgbouncer/README.md](https://github.com/WilliamOdinson/Gastronome/blob/main/docs/pgbouncer/README.md).

## 3  Airflow Metadata Database Initialization and Migrationone connection

To set up the Airflow metadata database and manage schema migrations, use

```bash
airflow db migrate
```

This command creates all necessary tables and structures for a new deployment and also applies any required schema upgrades when updating your Airflow installation.

> [!NOTE]
>
> As of Airflow 3.x, the `airflow db init` and `airflow db upgrade` commands are deprecated. Use `airflow db migrate` for both the initial setup and all future database migrations.

After initialization, you can check database connectivity with:

```bash
airflow db check
```

## 4  User and Authentication Mechanism

**Default Authentication:** Apache Airflow 3.0 introduces the lightweight [SimpleAuthManager](https://airflow.apache.org/docs/apache-airflow/stable/core-concepts/auth-manager/simple/index.html) by default, which supports static user configuration primarily intended for development and testing scenarios. With SimpleAuth enabled, user passwords are auto-generated. When launching the web server for the first time, the random password for the `admin` user is displayed in the console logs and also saved in `${AIRFLOW_HOME}/simple_auth_manager_passwords.json.generated`. Users should refer to the startup logs or this file to retrieve the password. The password can be directly modified in this file.

## 5  Managing User Configuration

SimpleAuthManager users are configured via the `airflow.cfg` file. Locate or add the configuration option `simple_auth_manager_users` within the `[core]` section. This option accepts a comma-separated list in the format `username:role`. For example:

```ini
[core]
simple_auth_manager_users = admin:admin,bob:viewer
```

The above configuration sets up two users: `admin` with Admin privileges and `bob` with Viewer (read-only) privileges. Changes require restarting the web server to take effect. SimpleAuth supports fixed roles (`viewer`, `user`, `op`, `admin`); custom permissions are not supported ([detailed documentation](http://airflow.apache.org/docs/apache-airflow/stable/core-concepts/auth-manager/simple/index.html#manage-roles-and-permissions)).

> [!NOTE]
>
> When using the default SimpleAuth mode, creating users via the command line (`airflow users create`) is no longer supported. Initially, only the default `admin` user (with the Admin role) exists. To add additional users, modifications must be made to the configuration file (`airflow.cfg`), and passwords must be retrieved from the logs or generated file ([more info](https://stackoverflow.com/questions/79596338/airflow-users-create-command-not-working-with-3-0-version-failing#:~:text=0,airflow%27s%20document%20here)).

## 6  Starting the Airflow Services

To launch the Airflow web interface (API server) and the scheduler in the background, use the following commands:

```bash
airflow api-server -p 8080 -D
airflow scheduler -D
```

Once started, open your browser and navigate to [http://localhost:8080](http://localhost:8080/) to access the Airflow UI.

> [!CAUTION]
>
> SimpleAuthManager is designed for simplicity for development and testing environments.
>
> For production deployments, consider using more robust authentication mechanisms. The [AWS Auth Manager](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/auth-manager/index.html) is available but still experimental. <u>If your Airflow deployment is only accessible from an internal network, the security risk is reduced</u>; however, always evaluate your organization's security requirements before deploying in production.

## 7  Email Notifications via SMTP

Airflow supports sending task failure alerts and other notifications via SMTP out of the box. This enables you to receive timely notifications for operational issues. Configure SMTP settings in the `airflow.cfg` file as follows:

```ini
[email]
email_backend = airflow.utils.email.send_email_smtp
from_email = "Airflow Alert <airflow@example.com>"

[smtp]
smtp_host = smtp.example.com
smtp_port = 587
smtp_user = airflow
smtp_password = yourpassword
smtp_mail_from = airflow@example.com
smtp_starttls = True
smtp_ssl = False
```

To test email delivery, trigger a failed task in a sample DAG or use the Airflow CLI. If no email arrives, check the Airflow scheduler logs for authentication or delivery errors.

> [!NOTE]
>
> For advanced configuration (including Amazon SES, SendGrid, and provider-based backends), see the [official Airflow email documentation](https://airflow.apache.org/docs/apache-airflow/stable/howto/email-config.html).
