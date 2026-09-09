import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILES = (
    DATA_DIR / "arabam_brands.json",
    DATA_DIR / "arabam_brands_ticari.json",
)


def load_arabam_vehicles():
    """Return all available arabam.com vehicle hierarchies as one catalog."""
    vehicles = []
    for data_file in DATA_FILES:
        if not data_file.exists():
            continue
        with open(data_file, encoding="utf-8") as f:
            vehicles.extend(json.load(f))
    return vehicles
