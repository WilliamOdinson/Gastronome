from locust import HttpUser, between
from tasks.recommend_tasks import RecommendTasks


class WebsiteUser(HttpUser):
    host = "http://localhost:8000"  # Base URL of the target Django server
    wait_time = between(0.5, 2.0)
    tasks = [RecommendTasks]
