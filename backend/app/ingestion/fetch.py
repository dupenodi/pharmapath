import zipfile
from pathlib import Path

import httpx

from app.core.config import settings


def download_to_raw(url: str, dest_filename: str, timeout: float = 120.0) -> Path:
    """Downloads `url` into data/raw/<dest_filename>, skipping if already cached."""
    settings.raw_data_dir.mkdir(parents=True, exist_ok=True)
    dest = settings.raw_data_dir / dest_filename
    if dest.exists():
        return dest

    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as response:
        response.raise_for_status()
        with dest.open("wb") as f:
            for chunk in response.iter_bytes():
                f.write(chunk)
    return dest


def extract_zip_member(zip_path: Path, member_suffix: str, extract_dir: Path) -> Path:
    """Extracts the first member of `zip_path` whose name ends with `member_suffix`."""
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith(member_suffix):
                zf.extract(name, extract_dir)
                return extract_dir / name
    raise FileNotFoundError(f"No member ending in {member_suffix!r} found in {zip_path}")
