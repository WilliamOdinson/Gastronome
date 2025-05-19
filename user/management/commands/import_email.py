import re
import unicodedata
from django.core.management.base import BaseCommand
from django.db import transaction
from user.models import User
from tqdm import tqdm

DOMAIN = "gastronome.com"
BATCH = 10_000


def ascii_slug(text: str) -> str:
    """
    Normalize text to lowercase ASCII alphanumeric slug. e.g., 'Renée Zhang!' -> 'reneezhang'
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_str = normalized.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", ascii_str.lower()) or "user"


class Command(BaseCommand):
    help = "Fill missing email addresses for Yelp users using display_name, ASCII-encoded."

    def handle(self, *args, **options):
        existing_locals = {
            email.split("@", 1)[0].lower()
            for email in User.objects.exclude(email=None).values_list("email", flat=True)
        }

        qs = User.objects.filter(email__isnull=True).only("pk", "display_name")
        total = qs.count()
        self.stdout.write(f"Found {total} users without email. Generating...")

        buffer = []

        with transaction.atomic():
            for user in tqdm(qs.iterator(chunk_size=BATCH), desc="Email pass"):
                base_local = ascii_slug(user.display_name)
                local = base_local
                count = 1
                while local in existing_locals:
                    local = f"{base_local}{count}"
                    count += 1

                existing_locals.add(local)
                user.email = f"{local}@{DOMAIN}"
                buffer.append(user)

                if len(buffer) >= BATCH:
                    User.objects.bulk_update(buffer, ["email"])
                    buffer.clear()

            if buffer:
                User.objects.bulk_update(buffer, ["email"])

        self.stdout.write(self.style.SUCCESS(f"Email generation completed for {total} users."))
