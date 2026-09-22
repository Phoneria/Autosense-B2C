import json
import threading
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILES = (
    DATA_DIR / "arabam_brands.json",
    DATA_DIR / "arabam_brands_ticari.json",
)

# Katalog her istekte diskten okunup parse edilmesin: dosya mtime'ına bağlı bellek cache'i.
_lock = threading.Lock()
_cache: dict = {"key": None, "vehicles": []}


def _files_key():
    key = []
    for data_file in DATA_FILES:
        try:
            st = data_file.stat()
            key.append((str(data_file), st.st_mtime_ns, st.st_size))
        except OSError:
            key.append((str(data_file), None, None))
    return tuple(key)


def load_arabam_vehicles():
    """Return all available arabam.com vehicle hierarchies as one catalog.

    Dönen liste paylaşılan bellek nesnelerini içerir; çağıranlar SADECE OKUMALIDIR."""
    key = _files_key()
    if _cache["key"] == key:
        return list(_cache["vehicles"])
    with _lock:
        if _cache["key"] != key:
            vehicles = []
            for data_file in DATA_FILES:
                if not data_file.exists():
                    continue
                with open(data_file, encoding="utf-8") as f:
                    vehicles.extend(json.load(f))
            _cache["vehicles"] = vehicles
            _cache["key"] = key
        return list(_cache["vehicles"])
