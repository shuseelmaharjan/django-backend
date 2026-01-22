from pathlib import Path
import json
from functools import lru_cache
from django.conf import settings

DATA_PATH = Path(settings.BASE_DIR) / "locations.json"


@lru_cache(maxsize=1)
def load_locations() -> dict:
    """
    Loads locations.json once per process and caches it.
    Returns a dict with expected keys even if file is missing.
    """
    base = {"provinces": [], "districts": [], "municipalities": []}

    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            # ensure missing keys don't break APIs
            base.update({k: data.get(k, []) for k in base.keys()})
            return base
    except FileNotFoundError:
        return base
    except json.JSONDecodeError:
        raise
