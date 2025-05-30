import os
import sys
from pathlib import Path

import django
from colorama import Fore, Style, init
from django.contrib.auth import get_user_model


init(autoreset=True)

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = None
for parent in SCRIPT_PATH.parents:
    if (parent / "manage.py").exists():
        PROJECT_ROOT = parent
        break

if PROJECT_ROOT is None:
    print(Fore.RED + "[ERROR] Could not find manage.py in any parent directory.")
    sys.exit(1)

sys.path.insert(0, str(PROJECT_ROOT))


candidates = [
    p for p in PROJECT_ROOT.iterdir()
    if p.is_dir() and (p / "settings.py").exists()
]
if not candidates:
    print(Fore.RED + "[ERROR] Could not find settings.py in any subdirectory of project root.")
    sys.exit(1)

DJANGO_SETTINGS_MODULE = f"{candidates[0].name}.settings"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", DJANGO_SETTINGS_MODULE)


django.setup()

User = get_user_model()
LOG_FILE = PROJECT_ROOT / "registered_emails.log"


def main():
    if not LOG_FILE.exists():
        print(Fore.RED + f"[ERROR] Log file not found: {LOG_FILE}")
        sys.exit(1)

    emails = [
        line.strip() for line in LOG_FILE.read_text().splitlines() if line.strip()
    ]
    if not emails:
        print(f"[INFO] No emails in {LOG_FILE}, nothing to delete.")
        return

    deleted = []
    not_found = []

    for email in emails:
        try:
            user = User.objects.get(email=email)
            user.delete()
            deleted.append(email)
            print(Fore.GREEN + f"[DELETED] {email}")
        except User.DoesNotExist:
            not_found.append(email)
            print(Fore.YELLOW + f"[NOT FOUND] {email}")

    print("\n=== Summary ===")
    print(f"Total processed: {len(emails)}")
    print(f"Deleted:         {len(deleted)}")
    print(f"Not found:       {len(not_found)}")

    # Optionally clear the log file after deletion:
    # LOG_FILE.unlink()
    # print(f"[INFO] Removed log file {LOG_FILE}")


if __name__ == "__main__":
    main()
