#!/usr/bin/env python3
"""Validate Mode A / A+ rough-cut text against raw or timestamped source transcripts.

v1.2 upgrades:
- Automatically strips bracketed timestamps (e.g. [00:01:23.450 --> 00:01:26.100])
  and leading speaker tags (e.g. （记者） / 说话人1：) before character counting.
- Supports optional --asr-map JSON file ({"raw_typo": "corrected_term"}) so
  transparently documented contextual ASR homophone fixes pass validation cleanly
  without relaxing the zero-fabricated-content rule.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path


TIMESTAMP_RE = re.compile(r"\[?\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?\s*(?:-->|-|–)\s*\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?\]?")
HEADER_LINE_RE = re.compile(r"^(?:#\s+|原文件|原文件\s*SHA|时间点对应|机器识别稿)")
SPEAKER_PREFIX_RE = re.compile(r"^(?:[（(][^）)]{1,12}[）)]|[A-Za-z\u4e00-\u9fff0-9]{1,10}\s*[：:])\s*")
INLINE_NOTE_RE = re.compile(r"\[[^\]]*待核听[^\]]*\]")


def strip_metadata(text: str, is_source: bool = False) -> str:
    cleaned_lines = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if is_source and HEADER_LINE_RE.match(line):
            continue
        line = TIMESTAMP_RE.sub("", line).strip()
        line = SPEAKER_PREFIX_RE.sub("", line).strip()
        line = INLINE_NOTE_RE.sub("", line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def normalized(text: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text)).lower()


def apply_asr_map(source_text: str, asr_map: dict[str, str]) -> str:
    if not asr_map:
        return source_text
    # Apply longer keys first to avoid partial shadowing.
    updated = source_text
    for wrong, right in sorted(asr_map.items(), key=lambda kv: len(kv[0]), reverse=True):
        if wrong:
            updated = updated.replace(wrong, right)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Original transcript/text file")
    parser.add_argument("--cut", required=True, help="Rough-cut body text file")
    parser.add_argument("--asr-map", help="Optional JSON dict mapping raw ASR typos to corrected terms")
    parser.add_argument("--warn-unit", type=int, default=70)
    args = parser.parse_args()

    raw_source = Path(args.source).read_text(encoding="utf-8")
    raw_cut = Path(args.cut).read_text(encoding="utf-8")

    asr_map: dict[str, str] = {}
    if args.asr_map:
        loaded = json.loads(Path(args.asr_map).read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise SystemExit("--asr-map must be a JSON object mapping wrong -> right strings")
        asr_map = {str(k): str(v) for k, v in loaded.items()}

    cleaned_source = strip_metadata(raw_source, is_source=True)
    effective_source = apply_asr_map(cleaned_source, asr_map)
    cleaned_cut = strip_metadata(raw_cut, is_source=False)

    source_chars = normalized(effective_source)
    cut_chars = normalized(cleaned_cut)
    missing = Counter(cut_chars) - Counter(source_chars)

    units = [line.strip() for line in cleaned_cut.splitlines() if line.strip()]
    normalized_units = [normalized(line) for line in units]
    duplicates = sorted({line for line in normalized_units if line and normalized_units.count(line) > 1})
    long_units = [line for line in units if len(normalized(line)) > args.warn_unit]

    result = {
        "source_chars": len(source_chars),
        "cut_chars": len(cut_chars),
        "compression_ratio": round(len(cut_chars) / len(source_chars), 3) if source_chars else None,
        "deleted_ratio": round(1 - len(cut_chars) / len(source_chars), 3) if source_chars else None,
        "asr_map_entries": len(asr_map),
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
