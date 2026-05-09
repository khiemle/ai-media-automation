import re
from datetime import date
from pathlib import Path

from unidecode import unidecode


def _slugify(text: str) -> str:
    text = unidecode(text)
    text = text.lower()
    text = re.sub(r'[—–]', '-', text)
    text = re.sub(r'&', 'and', text)
    text = re.sub(r'[^a-z0-9-]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def make_filename(title: str, ext: str, for_date: date | None = None) -> str:
    """Return a readable filename: YYYYMMDD_{slug}{ext}.

    Args:
        title: Human-readable name (Vietnamese or ASCII).
        ext:   File extension including leading dot, e.g. ".mp3". Pass "" for directories.
        for_date: Date prefix; defaults to today.
    """
    d = for_date or date.today()
    slug = _slugify(title)
    if not slug:
        slug = "untitled"
    return f"{d.strftime('%Y%m%d')}_{slug}{ext}"


def make_unique_path(title: str, ext: str, directory: Path, for_date: date | None = None) -> Path:
    """Return a unique Path in directory using the title slug.

    Appends _2, _3, ... before the extension if the base name already exists.
    """
    base = make_filename(title, ext, for_date)
    stem = Path(base).stem  # date_slug without ext
    candidate = directory / base
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = directory / f"{stem}_{counter}{ext}"
        if not candidate.exists():
            return candidate
        counter += 1
