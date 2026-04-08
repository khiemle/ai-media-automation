#!/usr/bin/env python3
"""Generate thumbnails for video assets using ffmpeg.

Run from the project root:
  python console/scripts/gen_thumbnails.py
"""
import os
import sys
import subprocess
from pathlib import Path

# Load .env and project path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set in console/.env")
    sys.exit(1)

engine = create_engine(DATABASE_URL)
THUMB_DIR = Path(__file__).parent.parent / "thumbnails"
THUMB_DIR.mkdir(exist_ok=True)


def generate_thumbnails():
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT id, file_path FROM video_assets "
                "WHERE thumbnail_path IS NULL AND file_path IS NOT NULL"
            )
        ).fetchall()

        print(f"Found {len(rows)} asset(s) needing thumbnails")

        ok = err = skip = 0
        for row in rows:
            src = Path(row.file_path)
            if not src.exists():
                print(f"  SKIP  id={row.id}: file not found at {src}")
                skip += 1
                continue

            thumb = THUMB_DIR / f"{row.id}.jpg"
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(src),
                    "-ss", "0",
                    "-vframes", "1",
                    "-vf", "scale=160:284:force_original_aspect_ratio=decrease,pad=160:284:(ow-iw)/2:(oh-ih)/2",
                    str(thumb),
                ],
                capture_output=True,
            )

            if result.returncode == 0:
                conn.execute(
                    text("UPDATE video_assets SET thumbnail_path = :tp WHERE id = :id"),
                    {"tp": str(thumb), "id": row.id},
                )
                conn.commit()
                print(f"  OK    id={row.id} → {thumb.name}")
                ok += 1
            else:
                stderr = result.stderr.decode(errors="replace")[:120]
                print(f"  ERROR id={row.id}: {stderr}")
                err += 1

        print(f"\nDone — {ok} generated, {skip} skipped, {err} errors")


if __name__ == "__main__":
    generate_thumbnails()
