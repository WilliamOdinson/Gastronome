from pathlib import Path
import subprocess
import pandas as pd
from tqdm import tqdm

CSV_PATH = Path(__file__).resolve().parent.parent / "database" / "Yelp_final.csv"
MIN_RATINGS = 50
COMMANDS = [
    ("train_svd", "Training SVD"),
    ("train_sgd", "Training SGD"),
    ("train_als", "Training ALS"),
    ("train_ensemble", "Training Ensemble"),
]


def load_valid_states() -> list[str]:
    """Read CSV once, count ratings per state and keep those above threshold."""
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")
    series = pd.read_csv(CSV_PATH, usecols=["state"])["state"]
    counts = series.value_counts()
    return [state for state, n in counts.items() if n >= MIN_RATINGS]


def run_manage_cmd(cmd: str, state: str) -> None:
    """Invoke manage.py command"""
    try:
        subprocess.run(
            ["python", "manage.py", cmd, "--state", state],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(f"[ERROR] {cmd} failed for state {state}")


def main() -> None:
    """Iterate over commands and states with tqdm progress bars."""
    states = load_valid_states()
    for cmd, label in COMMANDS:
        print(f"\n==> {label} models")
        for state in tqdm(states, desc=label, unit="state"):
            run_manage_cmd(cmd, state)


if __name__ == "__main__":
    main()
