import hashlib
import os
from pathlib import Path

from colorama import Fore, Style, init

USER = os.getenv("POSTGRES_USER")
PASSWORD = os.getenv("POSTGRES_PASSWORD")
FILE = Path("docs/pgbouncer/userlist.txt")
init(autoreset=True)

if USER and PASSWORD:
    md5_user = hashlib.md5((PASSWORD + USER).encode("utf-8")).hexdigest()
    md5_appuser = hashlib.md5((PASSWORD + "appuser").encode("utf-8")).hexdigest()

    with FILE.open("a", encoding="utf-8") as f:
        f.write(f'"{USER}" "md5{md5_user}"\n')
        f.write(f'"appuser" "md5{md5_appuser}"\n')

    print(Fore.GREEN + f"[SUCCESSFUL] Appended entry for {USER} to {FILE}.")
    print(Fore.GREEN + f"[SUCCESSFUL] Appended entry for appuser to {FILE}.")
else:
    print(Fore.RED + "[ERROR] POSTGRES_USER or POSTGRES_PASSWORD not set.")
