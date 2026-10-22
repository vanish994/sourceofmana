#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate Godot Translation .tres resources from translation CSV files.

Usage:
    python3 tools/translations/csv_to_tres.py [data/translations/pt_BR.csv ...]

The CSV format is:
    keys,<locale>
    "<source string>","<translated string>"

For each input CSV, a `.tres` file with the same basename is written next to
it, containing a `Translation` resource that Godot loads natively (declared
in project.godot under [internationalization]).
"""
import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSVS = [REPO_ROOT / "data" / "translations" / "pt_BR.csv"]


def godot_escape(text: str) -> str:
    """Escape a string for inclusion in a .tres double-quoted literal."""
    out = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        else:
            out.append(ch)
    return "".join(out)


def convert(csv_path: Path) -> Path:
    locale = csv_path.stem
    rows = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if len(header) < 2 or header[0] != "keys":
            raise ValueError(f"{csv_path}: expected header 'keys,<locale>'")
        locale = header[1]
        for row in reader:
            if len(row) < 2 or not row[0]:
                continue
            rows.append((row[0], row[1]))

    tres_path = csv_path.with_suffix(".tres")
    with tres_path.open("w", encoding="utf-8", newline="\n") as out:
        out.write('[gd_resource type="Translation" format=3]\n\n')
        out.write("[resource]\n")
        out.write('locale = "%s"\n' % locale)
        out.write("messages = {\n")
        for index, (key, value) in enumerate(rows):
            comma = "," if index < len(rows) - 1 else ""
            out.write('"%s": "%s"%s\n' % (godot_escape(key), godot_escape(value), comma))
        out.write("}\n")
    return tres_path


def main() -> int:
    targets = [Path(arg) for arg in sys.argv[1:]] or DEFAULT_CSVS
    for csv_path in targets:
        tres_path = convert(csv_path)
        print(f"{csv_path} -> {tres_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
