import csv
import os
import re
import time
import uuid
from itertools import cycle
from pathlib import Path

from locust import TaskSet, task


CSV_PATH = Path(__file__).resolve().parents[2] / "database" / "test_review.csv"
DEFAULT_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD", "password888")
TIME_INTERVAL = 0  # Time interval between tasks in seconds

# Read all review rows into a list of dicts
with CSV_PATH.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    all_reviews = [
        {
            "business_id": row["business_id"],
            "text": row["text"],
            "stars": row["stars"],
        }
        for row in reader
    ]


class ReviewTasks(TaskSet):
    def on_start(self):
        self.reg_log = open("registered_emails.log", "a")

        # 1. register a new user for posting reviews
        r1 = self.client.get("/user/register/", name="GET /user/register/")
        csrf1 = r1.cookies.get("csrftoken", "")

        self.email = f"locust_{uuid.uuid4().hex[:8]}@gastronome.loadtest.com"
        self.password = "Passw0rd!"
        display_name = self.email.split("@")[0]

        with self.client.post(
            "/user/register/",
            name="POST /user/register/",
            headers={"X-CSRFToken": csrf1},
            data={
                "email": self.email,
                "password1": self.password,
                "password2": self.password,
                "display_name": display_name,
                "captcha": "ABCD",
            },
            catch_response=True,
        ) as reg_res:
            if reg_res.status_code not in (200, 302):
                reg_res.failure(f"registration failed: HTTP {reg_res.status_code}")
                # Abort further tasks if registration fails
                self.interrupt()

        r2 = self.client.get("/user/verify-email/", name="GET /user/verify-email/")
        csrf2 = r2.cookies.get("csrftoken", "")

        with self.client.post(
            "/user/verify-email/",
            name="POST /user/verify-email/",
            headers={"X-CSRFToken": csrf2},
            data={"code": "000000"},
            catch_response=True,
        ) as verify_res:
            if verify_res.status_code not in (200, 302):
                verify_res.failure(f"verify-email failed: HTTP {verify_res.status_code}")
                self.interrupt()

        self.reg_log.write(self.email + "\n")
        self.reg_log.flush()

        self.review_iter = iter(all_reviews)
        self.posted_ids = []

    def on_stop(self):
        self.reg_log.close()

    @task
    def post_and_delete_reviews(self):
        try:
            rev = next(self.review_iter)
        except StopIteration:
            # All reviews posted -> proceed to delete them
            self._delete_reviews()
            # Stop further tasks
            self.interrupt()
            return

        biz_id = rev["business_id"]
        review_text = rev["text"]
        stars = rev["stars"]

        # 2. Post a single review
        r_get = self.client.get(
            f"/review/add/{biz_id}/", name=f"GET /review/add/{biz_id}/"
        )
        csrftoken = r_get.cookies.get("csrftoken", "")

        with self.client.post(
            f"/review/add/{biz_id}/",
            name=f"POST /review/add/{biz_id}/",
            headers={"X-CSRFToken": csrftoken},
            data={"stars": stars, "text": review_text},
            catch_response=True,
        ) as post_res:
            if post_res.status_code not in (200, 302):
                post_res.failure(
                    f"create_review failed for business {biz_id}: HTTP {post_res.status_code}"
                )
                return

        r_prof = self.client.get("/user/profile/", name="GET /user/profile/for-delete")
        html = r_prof.text

        # Try to find a delete link matching this biz_id
        pattern = rf'href="/review/delete/(?P<rid>[0-9a-f]+?)/".*?data-biz="{biz_id}"'
        match = re.search(pattern, html, flags=re.DOTALL)
        if match:
            rid = match.group("rid")
            self.posted_ids.append(rid)
        else:
            # Fallback: pick the first delete link found
            fallback = re.search(r'href="/review/delete/(?P<rid>[0-9a-f]+?)/"', html)
            if fallback:
                self.posted_ids.append(fallback.group("rid"))

        # Sleep before posting the next review
        time.sleep(TIME_INTERVAL)

    def _delete_reviews(self):
        # 3. Sequentially delete each review_id in posted_ids
        for rid in self.posted_ids:
            r_get = self.client.get("/user/profile/", name="GET /user/profile/for-csrf")
            csrf_tok = r_get.cookies.get("csrftoken", "")

            with self.client.post(
                f"/review/delete/{rid}/",
                name=f"POST /review/delete/{rid}/",
                headers={"X-CSRFToken": csrf_tok},
                catch_response=True,
            ) as del_res:
                if del_res.status_code not in (200, 302):
                    del_res.failure(f"delete_review failed for {rid}: HTTP {del_res.status_code}")

            # Pause ~1 second between deletes
            # time.sleep(1)
