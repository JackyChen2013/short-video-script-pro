#!/usr/bin/env python3
"""Validate delivery markdown fields, first-sentence alignment, and optional Mode A source check."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Optional

from validate_roughcut import apply_asr_map, normalized, strip_metadata


REQUIRED_FIELDS = (
    "成片类型",
    "结构类型",
    "标题",
    "视频描述",
    "开头第一句",
)

BODY_HEADING_RE = re.compile(r"(?m)^###\s*(?:完整口播正文|粗剪正文|完整粗剪正文)[^\n]*$")
NEXT_SECTION_RE = re.compile(r"(?m)^(?:---|###\s+|-\s*待核对词：|-\s*待核听疑点：|>\s*提示：)")


def split_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^## (?!#)(.+)$", text))
    numbered = [match for match in matches if re.match(r"(?:C?\d+[｜|]|\d+｜)", match.group(1))]
    if not numbered:
        return [("single", text)]
    sections = []
    for index, match in enumerate(numbered):
        end = numbered[index + 1].start() if index + 1 < len(numbered) else len(text)
        sections.append((match.group(1).strip(), text[match.end():end]))
    return sections


def field_value(section: str, field: str) -> Optional[str]:
    match = re.search(rf"(?m)^(?:\s*[-*]\s*){re.escape(field)}：\s*(.+)$", section)
    return match.group(1).strip() if match else None


def body_text(section: str) -> str:
    match = BODY_HEADING_RE.search(section)
    if not match:
        return ""
    body = section[match.end():]
    body = NEXT_SECTION_RE.split(body, maxsplit=1)[0]
    return body.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery", required=True)
    parser.add_argument("--source")
    parser.add_argument("--asr-map")
    args = parser.parse_args()

    text = Path(args.delivery).read_text(encoding="utf-8")
    asr_map: dict[str, str] = {}
    if args.asr_map:
        asr_map = {str(k): str(v) for k, v in json.loads(Path(args.asr_map).read_text(encoding="utf-8")).items()}

    source_chars = None
    if args.source:
        cleaned_source = strip_metadata(Path(args.source).read_text(encoding="utf-8"), is_source=True)
        source_chars = normalized(apply_asr_map(cleaned_source, asr_map))

    results = []
    failed = False

    for title, section in split_sections(text):
        missing = [field for field in REQUIRED_FIELDS if not field_value(section, field)]
        body = body_text(section)
        cleaned_body = strip_metadata(body, is_source=False)
        body_lines = [line.strip() for line in cleaned_body.splitlines() if line.strip()]
        first = field_value(section, "开头第一句") or ""
        first_norm = normalized(strip_metadata(first, is_source=False))
        first_body_norm = normalized(body_lines[0]) if body_lines else ""
        first_matches = bool(first_norm) and bool(first_body_norm) and (
            first_norm == first_body_norm or first_body_norm.startswith(first_norm)
        )
        normalized_lines = [normalized(line) for line in body_lines if normalized(line)]
        duplicates = sorted(
            {line for line in normalized_lines if normalized_lines.count(line) > 1}
        )
        extra_characters = (
            dict(Counter(normalized(cleaned_body)) - Counter(source_chars))
            if source_chars is not None else {}
        )
        errors = []
        if missing:
            errors.append("missing_fields")
        if not body:
            errors.append("missing_body")
        if first and not first_matches:
            errors.append("first_sentence_mismatch")
        if duplicates:
            errors.append("duplicate_body_lines")
        if extra_characters:
            errors.append("source_character_check")
        failed = failed or bool(errors)
        results.append({
            "section": title,
            "missing_fields": missing,
            "body_characters": len(normalized(cleaned_body)),
            "first_sentence_matches_body": first_matches,
            "duplicate_body_lines": duplicates,
            "source_character_check": not extra_characters,
            "extra_characters": extra_characters,
            "errors": errors,
        })

    print(json.dumps({"sections": results}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
