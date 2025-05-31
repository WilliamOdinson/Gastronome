import os
import sys
from pathlib import Path

from colorama import Fore, Style, init
from dotenv import load_dotenv
from locust import HttpUser, between

from tasks.recommend_tasks import RecommendTasks
from tasks.review_tasks import ReviewTasks
from tasks.user_tasks import UserTasks


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)
LOAD_TEST = os.getenv("LOAD_TEST", "False").lower() in ("1", "true", "yes")
init(autoreset=True)

if not LOAD_TEST:
    print(Fore.RED + "[ERROR] Load test mode is not enabled."
          "Please set LOAD_TEST=\"True\" in your .env file.")
    sys.exit(1)


class WebsiteUser(HttpUser):
    host = "http://localhost:8000"  # Base URL of the target Django server
    wait_time = between(0.5, 2.0)
    tasks = [UserTasks, ReviewTasks, RecommendTasks]
