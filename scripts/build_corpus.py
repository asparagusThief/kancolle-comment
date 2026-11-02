#!/usr/bin/env python3
"""Build a portable text-only corpus from the original Chinese-header CSV."""

import argparse
import collections
import csv
import datetime
import hashlib
import io
import json
import re
import sys
from pathlib import Path

REFERENCES = Path(__file__).resolve().parent.parent / "references"
COLUMNS = {
    "month": "作战月份", "server_id": "服务器编号", "fleet": "舰队名",
    "comment": "Comment", "flagship": "旗舰", "review_status": "校对状态",
    "review_notes": "需核对项", "source_url": "原图链接",
}


def build(source, as_of):
    source_bytes = source.read_bytes()
    reader = csv.DictReader(io.StringIO(source_bytes.decode("utf-8-sig"), newline=""))
    required = set(COLUMNS.values()) | {"图片编号", "栏目内序号"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Missing input columns: " + ", ".join(sorted(required - set(reader.fieldnames or []))))
    rows, seen = [], set()
    for original in reader:
        row = {key: original[value] for key, value in COLUMNS.items()}
        if not re.fullmatch(r"20\d{2}-(0[1-9]|1[0-2])", row["month"]):
            raise ValueError("Invalid operation month: " + row["month"])
        server = int(row["server_id"])
        index = int(original["栏目内序号"])
        if not 1 <= server <= 20 or not 1 <= index <= 8:
            raise ValueError("Invalid server or selection-row number")
        code = row["month"][2:4] + row["month"][5:7] + str(server).zfill(2)
        if original["图片编号"] != code:
            raise ValueError("Image code does not match month/server: " + original["图片编号"])
        expected_url = "https://w00g.kancolle-server.com/kcscontents/information/image/rank" + code + ".jpg"
        if row["source_url"] != expected_url:
            raise ValueError("Unexpected source URL for " + code)
        row["id"] = code + "-" + str(index).zfill(2)
        if row["id"] in seen:
            raise ValueError("Duplicate record ID: " + row["id"])
        seen.add(row["id"])
        rows.append(row)
    if not rows:
        raise ValueError("Source CSV contains no records")
    curated = json.loads((REFERENCES / "curated-examples.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in rows}
    for example in curated["examples"]:
        row = by_id.get(example["id"])
        source_text = example.get("source_text", example)
        if row is None or any(row[field] != source_text[field] for field in example["checked_fields"]):
            raise ValueError("Recheck the curated example before rebuilding: " + example["id"])
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=["id"] + list(COLUMNS), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    payload = buffer.getvalue().encode("utf-8")
    periods = sorted({row["month"] for row in rows})
    metadata = {
        "version": "1.3.0", "built_on": as_of,
        "period_start": periods[0], "period_end": periods[-1], "months": len(periods),
        "servers": len({row["server_id"] for row in rows}),
        "images": len({row["source_url"] for row in rows}), "records": len(rows),
        "source_review_counts": dict(collections.Counter(row["review_status"] for row in rows)),
        "curated_text_verified": len(curated["examples"]),
        "curated_coverage": curated.get("coverage", {}),
        "empty_fields": {field: sum(not row[field] for row in rows) for field in ("fleet", "comment")},
        "over_12_codepoints": {field: sum(len(row[field]) > 12 for row in rows) for field in ("fleet", "comment")},
        "input_filename": source.name,
        "input_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "corpus_sha256": hashlib.sha256(payload).hexdigest(),
        "notice": "Selected records only. Most text is unreviewed OCR; this is not an award-probability dataset.",
    }
    (REFERENCES / "corpus.csv").write_bytes(payload)
    (REFERENCES / "corpus-meta.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metadata


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--as-of", required=True, help="Build date in the user's timezone, YYYY-MM-DD")
    args = parser.parse_args()
    try:
        datetime.date.fromisoformat(args.as_of)
        print(json.dumps(build(args.input, args.as_of), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
