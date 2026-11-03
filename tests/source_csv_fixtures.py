import csv
import shutil
import tempfile
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def copy_sources(test_case):
    temporary = tempfile.TemporaryDirectory()
    test_case.addCleanup(temporary.cleanup)
    destination = Path(temporary.name) / "data"
    shutil.copytree(DATA_DIR, destination)
    return destination


def source_file(source_dir, name):
    return source_dir / f"desafio_tecnico_ai_eng - {name}.csv"


def edit_first_row(source_dir, name, field, value, duplicate=False):
    path = source_file(source_dir, name)
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields, rows = reader.fieldnames, list(reader)
    rows[0][field] = value
    if duplicate:
        rows.append(rows[0].copy())
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
