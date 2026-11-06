#!/usr/bin/env python3
"""Read the bundled Kancolle corpus and check candidate text; stdlib only."""

import argparse
import csv
import difflib
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

REFERENCES = Path(__file__).resolve().parent.parent / "references"


def emit(value, stream=None):
    print(json.dumps(value, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def normalize(text):
    text = unicodedata.normalize("NFKC", text).casefold()
    return "".join(c for c in text if unicodedata.category(c)[0] in "LN")


def load_data():
    with (REFERENCES / "corpus.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    curated = json.loads((REFERENCES / "curated-examples.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item for item in curated["examples"]}
    for row in rows:
        example = by_id.get(row["id"])
        if example:
            source_text = example.get("source_text", example)
            original = {field: row[field] for field in example["checked_fields"]}
            for field in example["checked_fields"]:
                if row[field] != source_text[field]:
                    raise ValueError("Curated source text no longer matches corpus: " + row["id"])
                row[field] = example[field]
            if any(original[field] != row[field] for field in original):
                row["ocr_text"] = original
        row["text_verified"] = bool(example) or row["review_status"] == "人工已核对"
        if example:
            row["curated"] = example
    return rows


def trust(row):
    if "curated" in row:
        return 3
    if row["review_status"] == "人工已核对":
        return 2
    if row["review_status"] == "两次识别一致，未人工校对":
        return 1
    return 0


def month_value(value):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", value):
        raise argparse.ArgumentTypeError("Use YYYY-MM with a valid month")
    return value


def month_set(value):
    try:
        result = {int(part) for part in value.split(",")}
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Use month numbers such as 9,10,11") from exc
    if not result or any(number < 1 or number > 12 for number in result):
        raise argparse.ArgumentTypeError("Months must be between 1 and 12")
    return result


def result_limit(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Limit must be an integer") from exc
    if not 1 <= number <= 30:
        raise argparse.ArgumentTypeError("Limit must be between 1 and 30")
    return number


def theme_tags(row):
    return row.get("curated", {}).get("themes", [])


def coverage(rows):
    tagged = sum(bool(theme_tags(row)) for row in rows)
    return {
        "corpus_records": len(rows),
        "theme_tagged_records": tagged,
        "theme_untagged_records": len(rows) - tagged,
        "theme_tagged_percent": round(100 * tagged / len(rows), 2) if rows else 0,
    }


def search(rows, args):
    if args.since and args.until and args.since > args.until:
        raise ValueError("--since must not be later than --until")
    terms = [unicodedata.normalize("NFKC", token).casefold() for token in args.query.split()]
    expand_query = getattr(args, "expand_query", "")
    expansion = [unicodedata.normalize("NFKC", token).casefold() for token in expand_query.split()]
    flagship = unicodedata.normalize("NFKC", args.flagship).casefold()
    theme = unicodedata.normalize("NFKC", args.theme).casefold().strip()
    if expansion and not theme:
        raise ValueError("--expand-query requires --theme; use --query for keyword-only search")
    if expand_query and not expansion:
        raise ValueError("--expand-query must contain at least one keyword")
    matched, eligible = [], []
    for row in rows:
        if args.reviewed_only and not row["text_verified"]:
            continue
        if args.month and int(row["month"][5:]) not in args.month:
            continue
        if args.since and row["month"] < args.since:
            continue
        if args.until and row["month"] > args.until:
            continue
        ship = unicodedata.normalize("NFKC", row["flagship"]).casefold()
        if flagship and flagship not in ship:
            continue
        eligible.append(row)
        text = unicodedata.normalize("NFKC", row["fleet"] + "\n" + row["comment"]).casefold()
        query_hits = [term for term in terms if term in text]
        expansion_hits = [term for term in expansion if term in text]
        query_match = not terms or bool(query_hits) and (not args.all or len(query_hits) == len(terms))
        theme_match = not theme or any(
            theme in unicodedata.normalize("NFKC", tag).casefold() for tag in theme_tags(row)
        )
        expanded = bool(expansion_hits) and (not args.all or len(expansion_hits) == len(expansion))
        routes = []
        if query_match and theme_match:
            routes.append("theme" if theme else "keywords" if terms else "all_records")
        if expanded:
            routes.append("keyword_expansion")
        if not routes:
            continue
        matched.append({
            "row": row,
            "score": max(len(query_hits) if query_match and theme_match else 0,
                         len(expansion_hits) if expanded else 0),
            "retrieval": {
                "routes": routes,
                "query_matches": query_hits if query_match and theme_match else [],
                "expansion_matches": expansion_hits if expanded else [],
            },
        })
    rng = random.Random(args.seed) if args.seed is not None else random.SystemRandom()
    rng.shuffle(matched)
    matched.sort(key=lambda item: (item["score"], trust(item["row"])), reverse=True)
    by_pair = {}
    for item in matched:
        row = item["row"]
        key = (normalize(row["fleet"]), normalize(row["comment"]))
        if key not in by_pair or trust(row) > trust(by_pair[key]["row"]):
            by_pair[key] = item
    unique = sorted(by_pair.values(), key=lambda item: (item["score"], trust(item["row"])), reverse=True)
    if expansion:
        themed = [item for item in unique if "theme" in item["retrieval"]["routes"]]
        untagged = [item for item in unique if not theme_tags(item["row"])]
        other_tagged = [item for item in unique
                        if "theme" not in item["retrieval"]["routes"] and theme_tags(item["row"])]
        additional = untagged + other_tagged
        # Keep untagged leads visible even when many tagged examples rank highly.
        mixed = []
        for index in range(max(len(themed), len(additional))):
            if index < len(themed):
                mixed.append(themed[index])
            if index < len(additional):
                mixed.append(additional[index])
        unique = mixed
    selected = unique[:args.limit]
    scope = coverage(rows)
    eligible_tagged = sum(bool(theme_tags(row)) for row in eligible)
    scope.update({
        "mode": "theme_with_keyword_expansion" if expansion else "theme_tags" if theme else "full_corpus",
        "eligible_records": len(eligible),
        "eligible_theme_tagged_records": eligible_tagged,
        "eligible_theme_untagged_records": len(eligible) - eligible_tagged,
        "eligible_text_verified_records": sum(row["text_verified"] for row in eligible),
        "filters": {
            "month": sorted(args.month) if args.month else [], "since": args.since,
            "until": args.until, "flagship": args.flagship, "reviewed_only": args.reviewed_only,
        },
    })
    warnings = []
    if theme:
        warnings.append("Theme counts describe only the tagged subset, not full-corpus theme prevalence; "
                        "untagged records have unknown themes.")
        if not expansion:
            warnings.append("Use --expand-query with related Japanese words to explore untagged records.")
    if expansion:
        warnings.append("Keyword expansion is literal retrieval, not theme annotation; judge relevance "
                        "and check source images before quoting unverified OCR as historical text.")
    if args.reviewed_only and expansion:
        warnings.append("--reviewed-only also restricts keyword expansion; unverified OCR is excluded.")
    routes = ("theme", "keywords", "all_records", "keyword_expansion")
    return {
        "query": args.query,
        "theme": args.theme,
        "expand_query": expand_query,
        "scope": scope,
        "warnings": warnings,
        "matched_records": len(matched),
        "matched_by_route": {route: sum(route in item["retrieval"]["routes"] for item in matched)
                             for route in routes},
        "unique_combinations": len(unique),
        "returned": len(selected),
        "returned_by_route": {route: sum(route in item["retrieval"]["routes"] for item in selected)
                              for route in routes},
        "records": [dict(item["row"], retrieval=item["retrieval"]) for item in selected],
    }


def character_report(value):
    errors, warnings = [], []
    if not isinstance(value, str):
        return {"errors": ["Must be a non-empty string"], "warnings": []}
    units = len(value.encode("utf-16-le", errors="surrogatepass")) // 2
    if not value.strip():
        errors.append("Text must not be empty or whitespace only")
    if len(value) > 12 or units > 12:
        errors.append("Exceeds the 12-character limit")
    if any(ord(c) > 0xFFFF for c in value):
        errors.append("Non-BMP characters are outside the supported game-safe text subset")
    if any(unicodedata.category(c) in {"Cc", "Cf", "Cs", "Zl", "Zp"} for c in value):
        errors.append("Contains control, invisible format, surrogate or line separator characters")
    if any(unicodedata.category(c).startswith("M") for c in value):
        warnings.append("Combining marks or variation selectors need manual display verification")
    if value != unicodedata.normalize("NFC", value):
        warnings.append("NFC composition may change the count; check the final copied text")
    if value != value.strip():
        warnings.append("Leading or trailing whitespace counts toward the limit")
    return {"codepoints": len(value), "utf16_units": units, "errors": errors, "warnings": warnings}


def short_record(row, similarity=None):
    result = {key: row[key] for key in (
        "id", "fleet", "comment", "flagship", "review_status", "text_verified", "source_url"
    )}
    if similarity is not None:
        result["text_similarity"] = round(similarity, 3)
    if "ocr_text" in row:
        result["ocr_text"] = row["ocr_text"]
    return result


def history_matches(fleet, comment, rows):
    target = normalize(comment)
    target_fleet = normalize(fleet) if isinstance(fleet, str) else None
    if not target:
        return {"exact_comment_count": 0, "exact_pair_count": 0, "examples": [], "near": []}
    exact = [row for row in rows if normalize(row["comment"]) == target]
    exact.sort(key=trust, reverse=True)
    pairs = sum(target_fleet == normalize(row["fleet"]) for row in exact) if target_fleet is not None else 0
    near = []
    if len(target) >= 6:
        target_bigrams = {target[i:i + 2] for i in range(len(target) - 1)}
        for row in rows:
            other = normalize(row["comment"])
            if other == target or not other or 2 * min(len(target), len(other)) / (len(target) + len(other)) < 0.82:
                continue
            other_bigrams = {other[i:i + 2] for i in range(len(other) - 1)}
            if len(target_bigrams & other_bigrams) < 2:
                continue
            ratio = difflib.SequenceMatcher(None, target, other, autojunk=False).ratio()
            if ratio >= 0.82:
                near.append((ratio, row))
    near.sort(key=lambda item: (item[0], trust(item[1])), reverse=True)
    distinct_near, seen = [], set()
    for ratio, row in near:
        key = normalize(row["comment"])
        if key not in seen:
            distinct_near.append(short_record(row, ratio))
            seen.add(key)
        if len(distinct_near) == 3:
            break
    return {
        "exact_comment_count": len(exact), "exact_pair_count": pairs,
        "examples": [short_record(row) for row in exact[:3]], "near": distinct_near,
    }


def check_candidates(candidates, rows):
    if isinstance(candidates, dict):
        candidates = [candidates]
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Input must be a candidate object or a non-empty array of objects")
    results, seen = [], {}
    for index, candidate in enumerate(candidates, 1):
        if not isinstance(candidate, dict):
            results.append({"candidate": index, "ok": False, "errors": ["Candidate must be an object"]})
            continue
        fields = {"comment": character_report(candidate.get("comment"))}
        if "fleet" in candidate:
            fields["fleet"] = character_report(candidate["fleet"])
        errors = [field + ": " + error for field, report in fields.items() for error in report["errors"]]
        warnings = [field + ": " + warning for field, report in fields.items() for warning in report["warnings"]]
        comment = candidate.get("comment")
        history = None
        if isinstance(comment, str):
            normalized = normalize(comment)
            if normalized and normalized in seen:
                warnings.append("Comment duplicates candidate " + str(seen[normalized]) + " after normalization")
            if normalized:
                seen.setdefault(normalized, index)
            history = history_matches(candidate.get("fleet"), comment, rows)
            if history["exact_comment_count"]:
                warnings.append("Comment already appears in the historical corpus; review originality")
            if history["near"]:
                warnings.append("Similar historical comments found; compare wording and idea")
        results.append({
            "candidate": index, "text": candidate, "ok": not errors,
            "fields": fields, "errors": errors, "warnings": warnings, "history": history,
        })
    return {"ok": all(result["ok"] for result in results), "results": results}


def main():
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="strict")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("stats", help="Print provenance and coverage metadata")
    show_parser = commands.add_parser("show", help="Get exact source records by ID")
    show_parser.add_argument("ids", nargs="+")
    search_parser = commands.add_parser("search", help="Find examples using keywords, theme tags or both routes")
    search_parser.add_argument("--query", default="")
    search_parser.add_argument("--all", action="store_true")
    search_parser.add_argument("--flagship", default="")
    search_parser.add_argument("--theme", default="", help="Filter curated Chinese theme tags by literal substring")
    search_parser.add_argument("--expand-query", default="",
                               help="With --theme, add a separate full-corpus keyword search and mix results")
    search_parser.add_argument("--month", type=month_set)
    search_parser.add_argument("--since", type=month_value)
    search_parser.add_argument("--until", type=month_value)
    search_parser.add_argument("--reviewed-only", action="store_true")
    search_parser.add_argument("--limit", type=result_limit, default=8)
    search_parser.add_argument("--seed", type=int)
    check_parser = commands.add_parser("check", help="Check a JSON candidate file; '-' reads stdin")
    check_parser.add_argument("input")
    args = parser.parse_args()
    try:
        if args.command == "stats":
            metadata = json.loads((REFERENCES / "corpus-meta.json").read_text(encoding="utf-8"))
            metadata["retrieval_coverage"] = coverage(load_data())
            emit(metadata)
            return 0
        rows = load_data()
        if args.command == "show":
            by_id = {row["id"]: row for row in rows}
            missing = [identifier for identifier in args.ids if identifier not in by_id]
            if missing:
                raise ValueError("Unknown record IDs: " + ", ".join(missing))
            emit({"records": [by_id[identifier] for identifier in args.ids]})
        elif args.command == "search":
            emit(search(rows, args))
        else:
            text = sys.stdin.read() if args.input == "-" else Path(args.input).read_text(encoding="utf-8-sig")
            report = check_candidates(json.loads(text), rows)
            emit(report)
            return 0 if report["ok"] else 1
        return 0
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        emit({"error": str(exc)}, sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
