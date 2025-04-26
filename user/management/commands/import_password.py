from pathlib import Path
import os

from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from user.models import User
from dotenv import load_dotenv

load_dotenv()

class Command(BaseCommand):
    help = "Set an initial password for every imported Yelp user (single SQL UPDATE)."

    def handle(self, *args, **options):
        raw_pwd = os.getenv("DEFAULT_USER_PASSWORD")
        if not raw_pwd:
            self.stderr.write(self.style.ERROR(
                "Please set the DEFAULT_USER_PASSWORD environment variable in your .env file."
            ))
            return

        hashed_pwd = make_password(raw_pwd)

        rows = User.objects.filter(password="").update(password=hashed_pwd)
        self.stdout.write(self.style.SUCCESS(
            f"Initial password hashes have been written for {rows} users (completed in one SQL).。"
        ))
