import json
from pathlib import Path

def get_version():
    root = Path(__file__).resolve().parents[3]
    path = root / 'version.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {"version": "v1.4-full", "channel": "beta"}
