import csv
import os
import uuid
from itertools import cycle
from pathlib import Path

from locust import TaskSet, task

CSV_PATH = Path(__file__).resolve().parents[2] / "database" / "test_accounts.csv"
DEFAULT_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "password888")

# Read credentials from the CSV and create a cyclic iterator to reuse them
with CSV_PATH.open() as f:
    reader = csv.DictReader(f)
    cred_iter = cycle(
        [
            (row["email"], row.get("password", DEFAULT_PASSWORD))
            for row in reader
        ]
    )


class UserTasks(TaskSet):
    def on_start(self):
        # Open a log file to record all registered emails for cleanup
        self.reg_log = open("registered_emails.log", "a")

    def on_stop(self):
        # Close the registration log file
        self.reg_log.close()

    @task(1)
    def register_user(self):
        # 1. GET the registration page -> initial CSRF token
        r1 = self.client.get("/user/register/", name="GET /user/register/")
        csrf1 = r1.cookies.get("csrftoken", "")

        # 2. Generate email/password/display name
        email = f"locust_{uuid.uuid4().hex[:8]}@gastronome.loadtest.com"
        password = "Passw0rd!"
        display_name = email.split("@")[0]

        # 3. POST /user/register/ (captcha bypassed in view)
        with self.client.post(
            "/user/register/",
            name="POST /user/register/",
            headers={"X-CSRFToken": csrf1},
            data={
                "email": email,
                "password1": password,
                "password2": password,
                "display_name": display_name,
                "captcha": "ABCD",
            },
            catch_response=True,
        ) as post_res:
            if post_res.status_code not in (200, 302):
                post_res.failure(f"registration failed: HTTP {post_res.status_code}")
                return

        # 4. GET the verify-email page -> fresh CSRF token
        r2 = self.client.get(
            "/user/verify-email/",
            name="GET /user/verify-email/"
        )
        csrf2 = r2.cookies.get("csrftoken", "")

        # 5. POST /user/verify-email/ with dummy code
        with self.client.post(
            "/user/verify-email/",
            name="POST /user/verify-email/",
            headers={"X-CSRFToken": csrf2},
            data={"code": "000000"},
            catch_response=True,
        ) as verify_res:
            if verify_res.status_code not in (200, 302):
                verify_res.failure(f"verify-email failed: HTTP {verify_res.status_code}")
                return

        # 6. Log the new email for cleanup
        self.reg_log.write(email + "\n")
        self.reg_log.flush()

    @task(3)
    def login_profile_logout(self):
        # 1. Fetch the next test account credentials
        email, password = next(cred_iter)

        # 2. GET the login page to fetch CSRF token
        resp = self.client.get("/user/login/", name="GET /user/login/")
        csrf_token = resp.cookies.get("csrftoken", "")

        # 3. POST the login form with dummy captcha
        with self.client.post(
            "/user/login/",
            name="POST /user/login/",
            headers={"X-CSRFToken": csrf_token},
            data={
                "email": email,
                "password": password,
                "captcha": "ABCD",
            },
            catch_response=True,
        ) as login_res:
            if login_res.status_code not in (200, 302) or "Invalid" in login_res.text:
                login_res.failure(f"login failed for {email}")
                return

        # 4. GET the profile page to view reviews and tips
        with self.client.get(
            "/user/profile/", name="GET /user/profile/", catch_response=True
        ) as profile_res:
            if profile_res.status_code != 200:
                profile_res.failure(
                    f"profile fetch failed: HTTP {profile_res.status_code}"
                )
                return

        # 5. Retrieve the latest CSRF token and POST logout
        csrf_after = self.client.cookies.get("csrftoken", "")
        with self.client.post(
            "/user/logout/",
            name="POST /user/logout/",
            headers={"X-CSRFToken": csrf_after},
            catch_response=True,
        ) as logout_res:
            if logout_res.status_code not in (200, 302):
                logout_res.failure(f"logout failed: HTTP {logout_res.status_code}")
