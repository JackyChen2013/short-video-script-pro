#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from pathlib import Path


def normalized(text: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--cut", required=True)
    parser.add_argument("--warn-unit", type=int, default=70)
    args = parser.parse_args()

    source = Path(args.source).read_text(encoding="utf-8")
    cut = Path(args.cut).read_text(encoding="utf-8")
    source_chars = normalized(source)
    cut_chars = normalized(cut)
    missing = Counter(cut_chars) - Counter(source_chars)
    units = [line.strip() for line in cut.splitlines() if line.strip()]
    normalized_units = [normalized(line) for line in units]
    duplicates = sorted({line for line in normalized_units if line and normalized_units.count(line) > 1})
    long_units = [line for line in units if len(normalized(line)) > args.warn_unit]

    result = {
        "source_chars": len(source_chars),
        "cut_chars": len(cut_chars),
        "compression_ratio": round(len(cut_chars) / len(source_chars), 3) if source_chars else None,
        "source_character_check": not missing,
        "extra_characters": dict(missing),
        "meaning_units": len(units),
        "duplicate_units": duplicates,
        "units_over_warning": long_units,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not missing else 1)


if __name__ == "__main__":
    main()
