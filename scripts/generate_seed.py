"""
generate_seed.py
================
Reads C:/Dev/learning-greek/js/words/lessons.js and produces:
  1. seed_data.sql     — full SQL seed (replaces the old one)
  2. bot/data/words.py — Python dict LESSONS_BY_ID + flat ALL_WORDS list
                         for use by the bot and by tests.

Usage:
  python scripts/generate_seed.py
"""

import re
import sys
import os
import json

LESSONS_JS = r"C:/Dev/learning-greek/js/words/lessons.js"
SEED_SQL   = os.path.join(os.path.dirname(__file__), "..", "seed_data.sql")
WORDS_PY   = os.path.join(os.path.dirname(__file__), "..", "bot", "data", "words.py")

# ---------------------------------------------------------------------------
# 1. Parse lessons.js
# ---------------------------------------------------------------------------

def parse_lessons_js(path: str) -> list[dict]:
    """Return list of {lesson_num, title, words:[{greek,russian}]}."""
    with open(path, encoding="utf-8") as f:
        content = f.read()

    # Find each LESSONS.push({ ... }); block
    # Also handle the initial assignment window.LESSONS = [ { ... } ];
    raw_blocks = []

    # Initial array block — use bracket matching to handle nested braces
    m = re.search(r"window\.LESSONS\s*=\s*\[", content)
    if m:
        start = m.end()
        # Find matching ] by counting brackets
        depth = 1
        pos = start
        while pos < len(content) and depth > 0:
            if content[pos] == '[':
                depth += 1
            elif content[pos] == ']':
                depth -= 1
            pos += 1
        array_content = content[start:pos-1]
        # Extract the first object from the array using brace matching
        obj_start = array_content.find('{')
        if obj_start >= 0:
            depth = 1
            pos = obj_start + 1
            while pos < len(array_content) and depth > 0:
                if array_content[pos] == '{':
                    depth += 1
                elif array_content[pos] == '}':
                    depth -= 1
                pos += 1
            raw_blocks.append(array_content[obj_start:pos])

    # .push({...}) blocks — use brace matching for robustness
    for m in re.finditer(r"window\.LESSONS\.push\(\s*\{", content):
        obj_start = m.end() - 1  # position of the opening {
        depth = 1
        pos = obj_start + 1
        while pos < len(content) and depth > 0:
            if content[pos] == '{':
                depth += 1
            elif content[pos] == '}':
                depth -= 1
            pos += 1
        raw_blocks.append(content[obj_start:pos])

    lessons = []
    for block in raw_blocks:
        # lesson number
        m_num = re.search(r"lesson:\s*([\d.]+)", block)
        if not m_num:
            continue
        lesson_num = float(m_num.group(1))

        # title
        m_title = re.search(r"title:\s*['\"]([^'\"]+)['\"]", block)
        title = m_title.group(1) if m_title else ""

        # words array
        words = []
        for m_word in re.finditer(
            r"\{\s*greek:\s*['\"]([^'\"]+)['\"]\s*,\s*russian:\s*['\"]([^'\"]+)['\"]\s*\}", block
        ):
            greek   = m_word.group(1).strip()
            russian = m_word.group(2).strip()
            words.append({"greek": greek, "russian": russian})

        lessons.append({"lesson_num": lesson_num, "title": title, "words": words})

    # Sort by lesson number
    lessons.sort(key=lambda x: x["lesson_num"])
    return lessons


# ---------------------------------------------------------------------------
# 2. Merge sub-lessons into major lessons (group by int(lesson_num))
# ---------------------------------------------------------------------------

def merge_into_major_lessons(lessons: list[dict]) -> dict[int, dict]:
    """
    Merge sub-lessons (e.g. 5.1, 5.2, 5.3) into one lesson per major number.
    Returns dict keyed by major lesson number (int), sorted.
    """
    merged: dict[int, dict] = {}
    for les in lessons:
        major = int(les["lesson_num"])
        if major not in merged:
            # For regular lessons (1-899), use simple title like "Урок 1"
            # For special ones like 900, 998, 999 keep their specific titles
            title = f"Урок {major}" if major < 900 else les["title"]
            merged[major] = {
                "title": title,
                "words": list(les["words"]),
            }
        else:
            merged[major]["words"].extend(les["words"])
    return merged


def build_lesson_id_map(merged: dict[int, dict]) -> dict[int, int]:
    """Assign sequential DB IDs (1-based) to each major lesson."""
    id_map = {}
    db_id = 1
    for major in sorted(merged.keys()):
        id_map[major] = db_id
        db_id += 1
    return id_map


# ---------------------------------------------------------------------------
# 3. Generate seed_data.sql
# ---------------------------------------------------------------------------

def generate_sql(merged: dict[int, dict], id_map: dict[int, int]) -> str:
    lines = [
        "-- Seed Data for Greek Learning Bot",
        "-- Auto-generated from lessons.js — DO NOT EDIT MANUALLY",
        "-- Run: python scripts/generate_seed.py",
        "",
        "-- Clear existing data",
        "TRUNCATE TABLE words CASCADE;",
        "TRUNCATE TABLE lessons CASCADE;",
        "",
        "-- Reset sequences",
        "ALTER SEQUENCE lessons_id_seq RESTART WITH 1;",
        "ALTER SEQUENCE words_id_seq RESTART WITH 1;",
        "",
        "-- Insert Lessons",
    ]

    # Build lesson INSERT
    lesson_vals = []
    for major in sorted(merged.keys()):
        les = merged[major]
        db_id = id_map[major]
        name  = les["title"].replace("'", "''")
        lesson_vals.append(f"('{name}', {major}, '')")

    lines.append("INSERT INTO lessons (name, order_number, description) VALUES")
    lines.append(",\n".join(lesson_vals) + ";")
    lines.append("")

    # Build word INSERTs grouped by lesson
    for major in sorted(merged.keys()):
        les = merged[major]
        db_id  = id_map[major]
        title  = les["title"]
        lines.append(f"-- Insert Words for Lesson {major} (DB ID {db_id}: {title})")
        lines.append("INSERT INTO words (greek_word, russian_translation, lesson_id) VALUES")
        word_vals = []
        for w in les["words"]:
            greek   = w["greek"].replace("'", "''")
            russian = w["russian"].replace("'", "''")
            word_vals.append(f"('{greek}', '{russian}', {db_id})")
        lines.append(",\n".join(word_vals) + ";")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Generate bot/data/words.py
# ---------------------------------------------------------------------------

def generate_words_py(merged: dict[int, dict], id_map: dict[int, int]) -> str:
    """
    Produces a Python module with:
      LESSONS_BY_ID: dict[int, dict]  — keyed by DB lesson id
      ALL_WORDS: list[str]            — flat deduplicated list of all greek words
    """
    lines = [
        '"""',
        "bot/data/words.py",
        "==================",
        "Auto-generated from C:/Dev/learning-greek/js/words/lessons.js",
        "DO NOT EDIT MANUALLY — run: python scripts/generate_seed.py",
        '"""',
        "",
        "from typing import Dict, List",
        "",
        "# Each lesson keyed by its DB lesson_id",
        "# Value: { 'title': str, 'words': [{'greek': str, 'russian': str}] }",
        "LESSONS_BY_ID: Dict[int, dict] = {",
    ]

    for major in sorted(merged.keys()):
        les = merged[major]
        db_id = id_map[major]
        title = les["title"]
        lines.append(f"    {db_id}: {{")
        lines.append(f"        'title': {repr(title)},")
        lines.append(f"        'lesson_num': {major},")
        lines.append(f"        'words': [")
        for w in les["words"]:
            lines.append(f"            {{'greek': {repr(w['greek'])}, 'russian': {repr(w['russian'])}}},")
        lines.append(f"        ],")
        lines.append(f"    }},")

    lines.append("}")
    lines.append("")

    # Flat deduplicated list (preserving first-seen order)
    all_words_seen = set()
    all_words = []
    for major in sorted(merged.keys()):
        for w in merged[major]["words"]:
            g = w["greek"]
            if g not in all_words_seen:
                all_words_seen.add(g)
                all_words.append(g)

    lines.append("# Flat deduplicated list of all Greek words, in lesson order")
    lines.append("ALL_WORDS: List[str] = [")
    for w in all_words:
        lines.append(f"    {repr(w)},")
    lines.append("]")
    lines.append("")

    # Also expose words grouped by lesson_id in a flat way
    lines.append("")
    lines.append("def get_words_for_lessons(lesson_ids: List[int]) -> List[str]:")
    lines.append('    """Return flat list of greek words for given lesson DB IDs."""')
    lines.append("    result = []")
    lines.append("    seen = set()")
    lines.append("    for lid in lesson_ids:")
    lines.append("        for w in LESSONS_BY_ID.get(lid, {}).get('words', []):")
    lines.append("            if w['greek'] not in seen:")
    lines.append("                seen.add(w['greek'])")
    lines.append("                result.append(w['greek'])")
    lines.append("    return result")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    print(f"Parsing {LESSONS_JS} ...")
    lessons = parse_lessons_js(LESSONS_JS)
    total_words = sum(len(l["words"]) for l in lessons)
    print(f"  Found {len(lessons)} lesson blocks, {total_words} word entries")

    merged = merge_into_major_lessons(lessons)
    id_map = build_lesson_id_map(merged)
    print(f"  Major lessons → DB IDs: {len(id_map)}")

    # Show lesson mapping
    for major in sorted(merged.keys()):
        db_id = id_map[major]
        title = merged[major]["title"]
        word_count = len(merged[major]["words"])
        print(f"    Lesson {major} → DB ID {db_id}: {title} ({word_count} words)")

    # Generate SQL
    sql = generate_sql(merged, id_map)
    sql_path = os.path.abspath(SEED_SQL)
    with open(sql_path, "w", encoding="utf-8") as f:
        f.write(sql)
    print(f"  ✅ Written {sql_path}  ({len(sql):,} bytes)")

    # Generate words.py
    words_py = generate_words_py(merged, id_map)
    words_path = os.path.abspath(WORDS_PY)
    os.makedirs(os.path.dirname(words_path), exist_ok=True)
    with open(words_path, "w", encoding="utf-8") as f:
        f.write(words_py)
    print(f"  ✅ Written {words_path}  ({len(words_py):,} bytes)")

    # Quick stats
    unique = len(set(
        w["greek"]
        for les in merged.values()
        for w in les["words"]
    ))
    print(f"\n  Total unique Greek words: {unique}")


if __name__ == "__main__":
    main()

