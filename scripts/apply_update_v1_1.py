from __future__ import annotations
import json, shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload"
LOG_DIR = ROOT / "logs"
BACKUP_DIR = ROOT / "backups"
UPDATES_DIR = ROOT / "updates"

def log(message: str) -> None:
    LOG_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp} | {message}"
    print(line)
    with (LOG_DIR / "update.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def backup() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    b = BACKUP_DIR / f"backup_before_v1_1_{stamp}"
    b.mkdir(parents=True, exist_ok=True)
    for name in ["version.json", "config", "database", "logs"]:
        src = ROOT / name
        if not src.exists():
            continue
        dst = b / name
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)
    log(f"Backup erstellt: {b}")

def copy_payload() -> None:
    if not PAYLOAD.exists():
        raise RuntimeError("Payload-Ordner nicht gefunden.")
    for item in PAYLOAD.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(PAYLOAD)
        target = ROOT / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        log(f"Kopiert: {rel}")

def archive_zips() -> None:
    if not UPDATES_DIR.exists():
        return
    archive = UPDATES_DIR / "archive"
    archive.mkdir(exist_ok=True)
    for z in UPDATES_DIR.glob("*.zip"):
        target = archive / z.name
        if target.exists():
            target = archive / f"{z.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{z.suffix}"
        try:
            shutil.move(str(z), str(target))
            log(f"Update-ZIP archiviert: {target.name}")
        except Exception as exc:
            log(f"Archivierung übersprungen: {z.name} ({exc})")

def main() -> int:
    log("=== Webshake Trading v1.1 Beta Update gestartet ===")
    backup()
    copy_payload()
    (ROOT / "version.json").write_text(json.dumps({
        "app": "Webshake Trading",
        "version": "1.1 Beta",
        "build": "1.1.0-beta",
        "channel": "beta"
    }, indent=2), encoding="utf-8")
    archive_zips()
    log("=== Webshake Trading v1.1 Beta Update abgeschlossen ===")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
