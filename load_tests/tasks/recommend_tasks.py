import csv
import os
from itertools import cycle
from pathlib import Path

from locust import TaskSet, task

CSV_PATH = Path(__file__).resolve().parents[2] / "database" / "test_accounts.csv"
PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "password888")

# Read credentials from the CSV and create a cyclic iterator to reuse them
with CSV_PATH.open() as f:
    reader = csv.DictReader(f)
    cred_iter = cycle(
        [(row["email"], PASSWORD, row["user_id"]) for row in reader]
    )


class RecommendTasks(TaskSet):
    @task
    def login_index_logout(self):
        # 1. Get the next set of test credentials
        email, password, uid = next(cred_iter)

        # 2. GET the login page to retrieve the CSRF token
        login_page = self.client.get("/user/login/", name="GET /user/login/")
        csrftoken = login_page.cookies.get("csrftoken", "")

        # 3. POST login with credentials and dummy captcha
        with self.client.post(
            "/user/login/",
            data={
                "email": email,
                "password": password,
                "captcha": "ABCD",
            },
            headers={"X-CSRFToken": csrftoken},
            name="POST /user/login/",
            catch_response=True,
        ) as login_res:
            if login_res.status_code not in (200, 302) or "Invalid" in login_res.text:
                login_res.failure(f"Login failed for {email}")
                return

        # 4. GET the homepage to trigger recommendation logic
        with self.client.get("/", name="GET / (index)", catch_response=True) as home_res:
            if home_res.status_code != 200:
                home_res.failure(f"Index request failed for {email}")
                return

        # 5. Retrieve latest CSRF token and POST logout
        csrf_token = self.client.cookies.get("csrftoken", "")
        with self.client.post(
            "/user/logout/",
            headers={"X-CSRFToken": csrf_token},
            name="POST /user/logout/",
            catch_response=True,
        ) as logout_res:
            if logout_res.status_code not in (200, 302):
                logout_res.failure(
                    f"Logout failed for {email}, status={logout_res.status_code}"
                )
