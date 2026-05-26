import os, shutil, json, zipfile
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / 'payload'
LOGDIR = ROOT / 'logs'
BACKUPDIR = ROOT / 'backups'
UPDATES = ROOT / 'updates'
ARCHIVE = UPDATES / 'archive'
LOGDIR.mkdir(exist_ok=True)
BACKUPDIR.mkdir(exist_ok=True)
ARCHIVE.mkdir(parents=True, exist_ok=True)
log_file = LOGDIR / 'update.log'

def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {msg}"
    print(line)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(line+'\n')

log('=== Webshake Trading Update v1.4-full gestartet ===')
backup_name = f"pre_v1_4_full_{datetime.now():%Y%m%d_%H%M%S}"
backup_path = BACKUPDIR / backup_name
backup_path.mkdir(exist_ok=True)
for name in ['database','config','logs','version.json']:
    src = ROOT / name
    if src.exists():
        dst = backup_path / name
        if src.is_dir(): shutil.copytree(src, dst, dirs_exist_ok=True)
        else: shutil.copy2(src, dst)
log(f'Backup erstellt: {backup_path}')

if PAYLOAD.exists():
    for item in PAYLOAD.rglob('*'):
        if item.is_file():
            rel = item.relative_to(PAYLOAD)
            dst = ROOT / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dst)
            log(f'Installiert: {rel}')

# version.json from package root wins
src_version = ROOT / 'version.json'
if src_version.exists():
    log('Version gesetzt: v1.4-full')

# archive zip files in updates (except archive dir)
for z in list(UPDATES.glob('*.zip')):
    try:
        target = ARCHIVE / z.name
        if target.exists():
            target = ARCHIVE / f"{z.stem}_{datetime.now():%Y%m%d_%H%M%S}{z.suffix}"
        shutil.move(str(z), str(target))
        log(f'Update-ZIP archiviert: {target.name}')
    except Exception as e:
        log(f'ZIP-Archivierung übersprungen: {z.name} ({e})')

log('=== Update v1.4-full abgeschlossen ===')
