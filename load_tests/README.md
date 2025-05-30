# Gastronome Load Testing

This folder contains scripts for performing load tests on the **Gastronome** web application.

Load Testing Framework: [![Locust](https://img.shields.io/badge/Locust-2.37.6-brightgreen?logo=python\&logoColor=white)](https://locust.io/)

## 0  Prerequisites

You must prepare a CSV file named `test_accounts.csv` containing user data required for load testing. Follow these steps:

### Generating Test Accounts CSV

Run the following PostgreSQL command to export user accounts with at least 10 reviews in Pennsylvania (`PA`) directly into a CSV file:

```sql
-- PostgreSQL \copy requires single-line SQL
\copy (SELECT r.user_id, COUNT(*) AS review_count, u.email FROM review_review AS r LEFT JOIN user_user AS u ON r.user_id = u.user_id WHERE r.business_id IN (SELECT business_id FROM business_business WHERE state = 'PA') GROUP BY r.user_id, u.email HAVING COUNT(*) > 10 ORDER BY review_count DESC) TO 'test_accounts.csv' WITH CSV HEADER;
```

Formatted SQL Query (for clarity): (\~ 1 minute)

```sql
SELECT 
    r.user_id, 
    COUNT(*) AS review_count, 
    u.email
FROM review_review AS r
LEFT JOIN user_user AS u ON r.user_id = u.user_id
WHERE r.business_id IN (
    SELECT business_id
    FROM business_business
    WHERE state = 'PA'
)
GROUP BY r.user_id, u.email
HAVING COUNT(*) > 10
ORDER BY review_count DESC;
```

After generating, move or copy this CSV file to:

```
database/test_accounts.csv
```

### Directory Structure

The load testing scripts are organized as follows:

```
load_tests/
├── locustfile.py                # Entry point for Locust tests
└── tasks/
    ├── recommend_tasks.py       # Recommendation system tasks
    └── user_tasks.py            # User actions (login/logout/profile)
```

## 1  Running Load Tests

> [!CAUTION]
>
> **Never run load tests against the production database**, as they can corrupt real user data. Always set up a separate environment (ideally identical hardware) for load testing before deployment.

### Bypassing Captcha for Load Testing

Since automated tests cannot reliably solve captchas, you should bypass captcha verification for load testing. You should see the login view as follows:

```python
@csrf_protect
def user_login(request):
    # other login logic
    if not settings.LOAD_TEST:
        # captcha validation here
        ...
```

During load testing, set an environment variable in your `.env` file:

```
LOAD_TEST="True"
```

Setting `LOAD_TEST` to `True` will:

* Disable captcha validation.
* Disable Sentry logging (to prevent unnecessary error logs during testing).

### Start Load Testing with Locust

Run the following command from your project's root directory:

```bash
locust -f load_tests/locustfile.py --host=http://localhost:8000
```

Replace `http://localhost:8000` with your actual host if testing remotely.

Open your browser and go to:

```
http://localhost:8089
```

Adjust the following settings in the Locust UI:

* **Number of users (peak concurrency)**:
  The maximum number of concurrent users simulated during the test (e.g., 100).

* **Ramp up (users started/second)**:
  How quickly the test reaches peak concurrency (e.g., 100 users/sec means it reaches full load in 1 second).

## 2  Understanding the Metrics

Locust provides the following key metrics in its web UI:

|                   Metric | Explanation                                                  |
| -----------------------: | ------------------------------------------------------------ |
|                 **Name** | Endpoint/task name *(e.g., login, logout, recommend API calls)* |
|           **# Requests** | Total number of requests made                                |
|              **# Fails** | Total number of failed requests                              |
|          **Median (ms)** | Median response time                                         |
|          **95%ile (ms)** | 95th percentile response time *(95% of requests are faster)* |
|          **99%ile (ms)** | 99th percentile response time *(99% of requests are faster)* |
|         **Average (ms)** | Average response time                                        |
|             **Min (ms)** | Minimum response time                                        |
|             **Max (ms)** | Maximum response time                                        |
| **Average size (bytes)** | Average size of responses *(helps evaluate network throughput)* |
|          **Current RPS** | Current Requests per Second                                  |
|   **Current Failures/s** | Current number of request failures per second                |

## 3  Running Celery Tasks During Load Tests

Make sure your Celery worker is running with the required queues (`bert-predict`, `recommendation`). Optionally include the `business_status` queue. Start Celery workers:

```bash
celery -A Gastronome worker -l info -P gevent -Q bert-predict,recommendation
# Optional additional queue:
# celery -A Gastronome worker -l info -P gevent -Q bert-predict,recommendation,business_status
```

### Pre-caching Recommendations (Recommended)

Before running the load tests on the recommendation endpoints, you should pre-cache the recommendations to simulate realistic, optimized performance:

Run in Django shell:

```bash
python manage.py shell

In [1]: from recommend.tasks import precache_recommendations
   ...: precache_recommendations.delay()
Out[1]: <AsyncResult: 3c574fd7-ee85-4018-907b-82a14deb0a69>
```

Wait until caching completes before initiating your load tests for best results.

## 4  Cleaning Up Test Users After Load Tests

Running the `UserTasks` in Locust will automatically register a set of dummy accounts to verify the robustness of the registration endpoint. These test accounts are logged in `registered_emails.log` at the project root (next to `manage.py`). Once your load test finishes, remove all of these accounts by executing:

```bash
python scripts/cleanup_registered_users.py
```

This cleanup script reads each email from `registered_emails.log` and deletes the matching user records from the database. To confirm that no test accounts remain, connect to PostgreSQL:

```bash
psql -h localhost -U postgres -d gastronome -p 5432
```

and run:

```sql
SELECT email
FROM user_user
WHERE email LIKE '%test.com';
```

If this query returns no rows, all test users have been successfully removed.

## Additional Notes

To monitor Celery task execution and diagnose potential issues during load tests, it is recommended to use [Flower](https://github.com/mher/flower), a web-based tool for Celery monitoring.

Install Flower with pip:

```bash
pip install flower
```

Start Flower alongside your Celery workers:

```bash
celery -A Gastronome flower
```

Then, open your browser and navigate to [http://localhost:5555](http://localhost:5555)

For detailed information and advanced configuration, refer to [Flower's official documentation](https://flower.readthedocs.io/en/latest/).
