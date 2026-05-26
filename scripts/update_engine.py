import argparse
import datetime as dt
import json
import re
import shutil
import zipfile
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
BACKUP_DIR = ROOT / "backups"
UPDATES_DIR = ROOT / "updates"
TEMP_DIR = ROOT / "temp" / "update_stage"
LOCAL_PAYLOAD = ROOT / "update_payload"
ENGINE_VERSION = "v1.7.5"
KEEP_BACKUP_NAMES = {"database", "config", "logs"}


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(message: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{now()} | {message}"
    print(line)
    with (LOG_DIR / "update.log").open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def run_ps(command: str) -> None:
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            cwd=str(ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
    except Exception as exc:
        log(f"PowerShell-Schritt übersprungen: {exc}")


def stop_running_webshake() -> None:
    """Beendet alte Backend-/Frontend-/Electron-Prozesse vor dem Kopieren.

    Wichtig: Dadurch lädt das Backend nach dem Update wirklich neuen Code.
    """
    log("Stoppe laufende Webshake-Prozesse vor dem Update...")
    try:
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts" / "stop_webshake.ps1")],
                       cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
    except Exception as exc:
        log(f"stop_webshake.ps1 konnte nicht ausgeführt werden: {exc}")

    # Sicherheitsnetz: Ports 8765 und 5173 freiräumen
    run_ps("""
    $ports=@(8765,5173)
    foreach($p in $ports){
      try {
        Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue |
        ForEach-Object { if($_.OwningProcess){ Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }
      } catch {}
    }
    """)

    # Sicherheitsnetz: Prozesse mit Projektpfad beenden
    root_escaped = str(ROOT).replace("\\", "\\\\")
    run_ps(f"""
    try {{
      Get-CimInstance Win32_Process | Where-Object {{
        ($_.Name -in @('python.exe','pythonw.exe','node.exe','electron.exe')) -and ($_.CommandLine -like '*{root_escaped}*')
      }} | ForEach-Object {{
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
      }}
    }} catch {{}}
    """)
    time.sleep(2)
    log("Prozess-Stopp abgeschlossen.")


def read_json(path: Path, default=None):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_zip_manifest(path: Path) -> dict:
    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            if "manifest.json" in names:
                return json.loads(zf.read("manifest.json").decode("utf-8"))
            for name in names:
                if name.endswith("/manifest.json"):
                    return json.loads(zf.read(name).decode("utf-8"))
    except Exception as exc:
        log(f"Manifest konnte nicht aus {path.name} gelesen werden: {exc}")
    return {}


def version_tuple(label: str):
    nums = re.findall(r"\d+", label or "")
    return tuple(int(n) for n in nums[:4]) if nums else (0,)


def copy_merge(src: Path, dst: Path) -> None:
    if not src.exists():
        log(f"Payload nicht gefunden: {src}")
        return
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            log(f"Installiert: {rel}")


def make_backup(version_label: str) -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_version = "".join(c if c.isalnum() or c in "._-" else "_" for c in version_label)
    dest = BACKUP_DIR / f"pre_{safe_version}_{stamp}"
    dest.mkdir(parents=True, exist_ok=True)
    for name in KEEP_BACKUP_NAMES:
        src = ROOT / name
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dest / name, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dest / name)
    current_version = ROOT / "current_version.txt"
    if current_version.exists():
        shutil.copy2(current_version, dest / "current_version.txt")
    log(f"Backup erstellt: {dest}")


def write_version(version_label: str, notes=None, client_version=None) -> None:
    notes = notes or []
    cfg_dir = ROOT / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "version": version_label,
        "client_version": client_version or version_label,
        "updated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "update_engine": ENGINE_VERSION,
        "notes": notes,
    }
    (cfg_dir / "version.json").write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (ROOT / "current_version.txt").write_text(version_label + "\n", encoding="utf-8")
    log(f"Version gesetzt: {version_label}")


def cleanup_old_root_files() -> None:
    patterns = [
        "update_to_v0_", "update_to_v1_0_1", "update_to_v1_0_2", "update_to_v1_0_cleanup",
        "webshake_trading_v0_", "hotfix", "_hotfix_",
    ]
    removed = 0
    for item in list(ROOT.iterdir()):
        low = item.name.lower()
        if item.name in {"update_webshake.bat", "start_webshake.bat", "stop_webshake.bat"}:
            continue
        if any(p.lower() in low for p in patterns):
            try:
                if item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                else:
                    item.unlink(missing_ok=True)
                removed += 1
            except Exception as exc:
                log(f"Konnte Altlast nicht entfernen ({item.name}): {exc}")
    log(f"Aufraeumen abgeschlossen. Entfernte Altlasten: {removed}")


def find_payload_base(stage: Path):
    manifest = read_json(stage / "manifest.json", {}) or {}
    if (stage / "update_payload").exists():
        return stage / "update_payload", manifest
    dirs = [p for p in stage.iterdir() if p.is_dir()]
    if len(dirs) == 1:
        nested = dirs[0]
        manifest = read_json(nested / "manifest.json", manifest) or manifest
        if (nested / "update_payload").exists():
            return nested / "update_payload", manifest
        return nested, manifest
    return stage, manifest


def archive_package(package: Path) -> None:
    installed_dir = UPDATES_DIR / "installed"
    installed_dir.mkdir(parents=True, exist_ok=True)
    if package.is_file():
        target = installed_dir / package.name
        if target.exists():
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            target = installed_dir / f"{package.stem}_{stamp}{package.suffix}"
        shutil.move(str(package), str(target))
        log(f"Update-Paket archiviert: {target}")


def archive_old_update_zips(selected: Path | None = None) -> None:
    installed_dir = UPDATES_DIR / "installed"
    installed_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for p in UPDATES_DIR.iterdir():
        if p == selected or p.name.lower() == "installed":
            continue
        if p.is_file() and p.suffix.lower() == ".zip":
            try:
                target = installed_dir / p.name
                if target.exists():
                    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
                    target = installed_dir / f"{p.stem}_{stamp}{p.suffix}"
                shutil.move(str(p), str(target))
                moved += 1
            except Exception as exc:
                log(f"Altes Update konnte nicht archiviert werden ({p.name}): {exc}")
    if moved:
        log(f"Alte Update-ZIPs archiviert: {moved}")


def apply_update_package(package: Path) -> None:
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    log(f"Update-Paket gefunden: {package.name}")
    if package.is_file() and package.suffix.lower() == ".zip":
        with zipfile.ZipFile(package, "r") as zf:
            zf.extractall(TEMP_DIR)
        payload, manifest = find_payload_base(TEMP_DIR)
    elif package.is_dir():
        payload, manifest = find_payload_base(package)
    else:
        raise RuntimeError("Unbekanntes Update-Paketformat")

    version = manifest.get("version") or package.stem.replace("webshake_trading_", "")
    client_version = manifest.get("client_version") or version
    notes = manifest.get("notes") or ["Update aus updates-Ordner installiert"]

    stop_running_webshake()
    make_backup(version)
    copy_merge(payload, ROOT)
    write_version(version, notes, client_version=client_version)
    cleanup_old_root_files()
    archive_package(package)
    archive_old_update_zips()
    log("Update-Paket erfolgreich installiert.")
    log("Bitte danach start_webshake.bat starten, damit Backend und Frontend frisch laden.")


def install_local() -> None:
    manifest = read_json(ROOT / "manifest.json", {}) or {}
    version = manifest.get("version") or (ENGINE_VERSION + " Beta")
    client_version = manifest.get("client_version") or version
    notes = manifest.get("notes") or [
        "Update-Engine installiert",
        "Backend wird vor Updates sauber beendet",
        "Versionsdatei zentralisiert",
    ]
    stop_running_webshake()
    make_backup(version)
    copy_merge(LOCAL_PAYLOAD, ROOT)
    write_version(version, notes, client_version=client_version)
    cleanup_old_root_files()
    log("Lokales Update erfolgreich installiert.")


def find_latest_update() -> Path | None:
    UPDATES_DIR.mkdir(parents=True, exist_ok=True)
    candidates = []
    for p in UPDATES_DIR.iterdir():
        if p.name.lower() == "installed":
            continue
        if p.is_file() and p.suffix.lower() == ".zip":
            manifest = read_zip_manifest(p)
            candidates.append((version_tuple(manifest.get("version", "")), p.stat().st_mtime, p))
        elif p.is_dir() and ((p / "manifest.json").exists() or (p / "update_payload").exists()):
            manifest = read_json(p / "manifest.json", {}) or {}
            candidates.append((version_tuple(manifest.get("version", "")), p.stat().st_mtime, p))
    if not candidates:
        return None
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return candidates[0][2]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install-local", action="store_true", help="Installiert das im Hauptordner liegende update_payload.")
    args = parser.parse_args()
    try:
        log(f"=== Webshake Trading Update-Engine {ENGINE_VERSION} gestartet ===")
        if args.install_local:
            install_local()
        else:
            pkg = find_latest_update()
            if not pkg:
                log("Kein Update-Paket im Ordner 'updates' gefunden.")
                log("Lege zukuenftige Update-ZIPs einfach in diesen Ordner und starte update_webshake.bat.")
                return 0
            apply_update_package(pkg)
        log("=== Update abgeschlossen ===")
        return 0
    except Exception as exc:
        log(f"FEHLER: {exc}")
        return 1
    finally:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
