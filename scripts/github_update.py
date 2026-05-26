import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPDATES_DIR = ROOT / "updates"
LOCAL_VERSION_FILE = ROOT / "version.json"
CONFIG_VERSION_FILE = ROOT / "config" / "version.json"

# GitHub Raw-Link zu update_manifest.json im main-Branch.
# Falls dein Repo später umbenannt wird, diese URL anpassen.
MANIFEST_URL = "https://raw.githubusercontent.com/Ghost265/webshake-trading/main/update_manifest.json"


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode("utf-8")


def download_file(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response:
        with target.open("wb") as f:
            f.write(response.read())


def version_tuple(label: str):
    nums = re.findall(r"\d+", label or "")
    return tuple(int(n) for n in nums[:4]) if nums else (0,)


def normalize_version(label: str) -> str:
    return (label or "").strip().lower().replace(" ", "-")


def get_local_version() -> str:
    data = read_json(LOCAL_VERSION_FILE, None)
    if data and data.get("version"):
        return data.get("version")

    data = read_json(CONFIG_VERSION_FILE, None)
    if data and data.get("version"):
        return data.get("version")

    current_version = ROOT / "current_version.txt"
    if current_version.exists():
        return current_version.read_text(encoding="utf-8").strip()

    return "0.0.0"


def is_newer(remote_version: str, local_version: str) -> bool:
    remote_nums = version_tuple(remote_version)
    local_nums = version_tuple(local_version)

    if remote_nums != local_nums:
        return remote_nums > local_nums

    return False


def main() -> int:
    print()
    print("Webshake-Trading GitHub Auto-Update")
    print("-----------------------------------")

    local_version = get_local_version()
    print(f"Lokale Version: {local_version}")

    try:
        manifest_raw = download_text(MANIFEST_URL)
        manifest = json.loads(manifest_raw)
    except Exception as exc:
        print(f"FEHLER: Update-Manifest konnte nicht geladen werden: {exc}")
        return 1

    remote_version = manifest.get("version", "").strip()
    download_url = manifest.get("download_url", "").strip()
    notes = manifest.get("notes", [])

    print(f"Online-Version: {remote_version}")

    if not remote_version:
        print("FEHLER: Im Manifest fehlt 'version'.")
        return 1

    if not download_url:
        print("FEHLER: Im Manifest fehlt 'download_url'.")
        return 1

    if not is_newer(remote_version, local_version):
        print("Kein Update notwendig.")
        return 0

    print()
    print("Neue Version gefunden.")
    if notes:
        print("Änderungen:")
        for note in notes:
            print(f"- {note}")

    safe_version = normalize_version(remote_version)
    if not safe_version.startswith("v"):
        safe_version = "v" + safe_version

    zip_name = f"WST-{safe_version}.zip"
    target = UPDATES_DIR / zip_name

    print()
    print(f"Lade Update herunter: {target.name}")

    try:
        download_file(download_url, target)
    except Exception as exc:
        print(f"FEHLER: Update-ZIP konnte nicht geladen werden: {exc}")
        return 1

    if not target.exists() or target.stat().st_size == 0:
        print("FEHLER: Download-Datei ist leer oder fehlt.")
        return 1

    print("Download abgeschlossen.")
    print("Starte lokale Update-Engine...")

    engine = ROOT / "scripts" / "update_engine.py"
    if not engine.exists():
        print("FEHLER: scripts/update_engine.py nicht gefunden.")
        return 1

    result = subprocess.run([sys.executable, str(engine)], cwd=str(ROOT))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
