from pathlib import Path
from datetime import datetime
import shutil

def archive_old_file(path, archive_root):
    path=Path(path); archive_root=Path(archive_root)
    archive_root.mkdir(parents=True, exist_ok=True)
    if path.exists():
        target=archive_root / f"{path.stem}_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}"
        shutil.move(str(path), str(target))
        return target
    return None
