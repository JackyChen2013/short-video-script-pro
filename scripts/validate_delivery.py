#!/usr/bin/env python3
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Optional


REQUIRED_FIELDS = (
    "成片类型",
    "结构类型",
    "标题",
    "视频描述",
    "开头第一句",
)


def normalized(text: str) -> str:
    return "".join(re.findall(r"[\u3400-\u9fffA-Za-z0-9]", text))


def split_sections(text: str) -> list[tuple[str, str]]:
    matches = list(re.finditer(r"(?m)^## (?!#)(.+)$", text))
    numbered = [match for match in matches if re.match(r"\d+｜", match.group(1))]
    if not numbered:
        return [("single", text)]
    sections = []
    for index, match in enumerate(numbered):
        end = numbered[index + 1].start() if index + 1 < len(numbered) else len(text)
        sections.append((match.group(1).strip(), text[match.end():end]))
    return sections


def field_value(section: str, field: str) -> Optional[str]:
    match = re.search(rf"(?m)^- {re.escape(field)}：\s*(.+)$", section)
    return match.group(1).strip() if match else None


def body_text(section: str) -> str:
    match = re.search(r"(?m)^### 粗剪正文\s*$", section)
    if not match:
        return ""
    body = section[match.end():]
    body = re.split(r"(?m)^---\s*$", body, maxsplit=1)[0]
    return body.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delivery", required=True)
    parser.add_argument("--source")
    args = parser.parse_args()

    text = Path(args.delivery).read_text(encoding="utf-8")
    source_chars = normalized(
        Path(args.source).read_text(encoding="utf-8")
    ) if args.source else None
    results = []
    failed = False

    for title, section in split_sections(text):
        missing = [field for field in REQUIRED_FIELDS if not field_value(section, field)]
        body = body_text(section)
        body_lines = [line.strip() for line in body.splitlines() if line.strip()]
        first = field_value(section, "开头第一句") or ""
        first_matches = bool(body_lines) and normalized(first) == normalized(body_lines[0])
        normalized_lines = [normalized(line) for line in body_lines if normalized(line)]
        duplicates = sorted(
            {line for line in normalized_lines if normalized_lines.count(line) > 1}
        )
        extra_characters = (
            dict(Counter(normalized(body)) - Counter(source_chars))
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
            "body_characters": len(normalized(body)),
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
