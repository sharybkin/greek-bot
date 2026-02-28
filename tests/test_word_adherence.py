"""
Test environment: validates that AI-generated sentences ONLY use words
from the user's word list (+ the verb είναι + articles/conjunctions).

# Usage:
#   # Full tests against live Groq API
#   python tests/test_word_adherence.py --verbose
# 
#   # Validate ONLY the Python validator logic (no API calls)
#   python tests/test_word_adherence.py --mock
# 
#   # Repeat each case N times
#   python tests/test_word_adherence.py --runs 3
"""

import asyncio
import argparse
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))



from bot.services.ai_service import (
    AIService,
    _ARTICLES,
    _HELPER_VERB,
    _CONJUNCTIONS,
    _tokenize_sentence,
    _strip_accents,
    _expand_word_forms,
    _build_stem_set,
    _MIN_STEM_LEN,
)

# ──────────────────────────────────────────────────────────────────────────────
# Simulated user word dictionaries (like a real user's lesson words)
# ──────────────────────────────────────────────────────────────────────────────

from bot.data.words import ALL_WORDS

# ──────────────────────────────────────────────────────────────────────────────
# Simulated user word dictionaries (like a real user's lesson words)
# ──────────────────────────────────────────────────────────────────────────────

# We load ALL_WORDS to provide a robust vocabulary equivalent to a real user.
SAMPLE_WORD_LIST: List[str] = ALL_WORDS

# ──────────────────────────────────────────────────────────────────────────────
# Mock sentences for --mock mode (pre-defined realistic AI responses)
# Indexed by (mandatory_words joined, difficulty)
# ──────────────────────────────────────────────────────────────────────────────

MOCK_RESPONSES = {
    # Good responses (should PASS all checks)
    ("το παραμύθι", 1): {
        "greek": "Το βιβλίο είναι καλό.",
        "russian": "Книга хорошая.",
        "used_greek_words": ["το παραμύθι"],
    },
    ("το μουσείο", 1): {
        "greek": "Το σπίτι είναι μεγάλο.",
        "russian": "Дом большой.",
        "used_greek_words": ["το μουσείο", "μεγάλο"],
    },
    ("τρώω|το γάλα", 2): {
        "greek": "Εγώ τρώω το ψωμί σήμερα εδώ.",
        "russian": "Я ем хлеб здесь сегодня.",
        "used_greek_words": ["τρώω", "το γάλα", "σήμερα", "εδώ"],
    },
    ("μαθαίνω|το πανεπιστήμιο", 2): {
        "greek": "Το παιδί μαθαίνει στο σχολείο σήμερα.",
        "russian": "Ребёнок учится в школе сегодня.",
        "used_greek_words": ["το παιδί", "μαθαίνω", "το πανεπιστήμιο", "σήμερα"],
    },
    ("αγαπώ|το παιδί|το μουσείο", 3): {
        "greek": "Εγώ αγαπώ το παιδί μου και το σπίτι μας είναι πολύ ωραίο.",
        "russian": "Я люблю своего ребёнка, и наш дом очень красивый.",
        "used_greek_words": ["αγαπώ", "το παιδί", "το μουσείο", "ωραίος"],
    },
    ("θέλω|κάνω|η δουλειά", 3): {
        "greek": "Εγώ θέλω να κάνω καλή δουλειά και να μαθαίνω σήμερα στο σπίτι.",
        "russian": "Я хочу хорошо работать и учиться сегодня дома.",
        "used_greek_words": ["θέλω", "κάνω", "η δουλειά", "σήμερα", "μαθαίνω", "το μουσείο"],
    },
    # Bad response (should FAIL – contains a word not in the list)
    ("INVALID_TEST", 1): {
        "greek": "Το σύμπαν εξερευνώ αύριο.",   # εξερευνώ NOT in list
        "russian": "Вселенную исследую завтра.",
        "used_greek_words": ["το μουσείο", "εξερευνώ", "αύριο"],
    },
    # Too-short response (should FAIL length)
    ("SHORT_TEST", 1): {
        "greek": "Το σπίτι.",   # only 2 words
        "russian": "Дом.",
        "used_greek_words": ["το μουσείο"],
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Test case definition
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class TestCase:
    name: str
    mandatory_words: List[str]
    all_words: List[str]
    difficulty: int
    plural: bool = True
    tenses: List[str] = field(default_factory=lambda: ["present", "past", "future"])
    personal_pronouns: bool = True
    possessive_pronouns: bool = True
    prepositions: bool = True
    # For mock mode: expected to pass or fail?
    expect_pass: bool = True

# ──────────────────────────────────────────────────────────────────────────────
# Live test cases — 30 cases across all difficulty levels
# ──────────────────────────────────────────────────────────────────────────────

LIVE_TEST_CASES: List[TestCase] = [
    # ── DIFFICULTY 1 (3-5 words) ──────────────────────────────────────────────
    TestCase(name="[D1] φίλος",
             mandatory_words=["ο φίλος"], all_words=SAMPLE_WORD_LIST, difficulty=1),
    TestCase(name="[D1] παιδί",
             mandatory_words=["το παιδί"], all_words=SAMPLE_WORD_LIST, difficulty=1),
    TestCase(name="[D1] singular μαμά",
             mandatory_words=["η μαμά"], all_words=SAMPLE_WORD_LIST, difficulty=1,
             plural=False),
    TestCase(name="[D1] μπαμπάς",
             mandatory_words=["ο μπαμπάς"], all_words=SAMPLE_WORD_LIST, difficulty=1),
    TestCase(name="[D1] αύριο",
             mandatory_words=["αύριο"], all_words=SAMPLE_WORD_LIST, difficulty=1),
    TestCase(name="[D1] σχολείο",
             mandatory_words=["το πανεπιστήμιο"], all_words=SAMPLE_WORD_LIST, difficulty=1),
    TestCase(name="[D1] present only – βλέπω",
             mandatory_words=["βλέπω"], all_words=SAMPLE_WORD_LIST, difficulty=1,
             tenses=["present"]),

    # ── DIFFICULTY 2 (6-9 words) ──────────────────────────────────────────────
    TestCase(name="[D2] τρώω + ψωμί",
             mandatory_words=["τρώω", "το γάλα"], all_words=SAMPLE_WORD_LIST, difficulty=2),
    TestCase(name="[D2] μαθαίνω + σχολείο",
             mandatory_words=["μαθαίνω", "το πανεπιστήμιο"], all_words=SAMPLE_WORD_LIST, difficulty=2),
    TestCase(name="[D2] πηγαίνω + σπίτι",
             mandatory_words=["πηγαίνω", "το μουσείο"], all_words=SAMPLE_WORD_LIST, difficulty=2),
    TestCase(name="[D2] έχω + δουλειά",
             mandatory_words=["έχω", "η δουλειά"], all_words=SAMPLE_WORD_LIST, difficulty=2),
    TestCase(name="[D2] παίζω + παιδί",
             mandatory_words=["παίζω", "το παιδί"], all_words=SAMPLE_WORD_LIST, difficulty=2),
    TestCase(name="[D2] no pronouns – μαθαίνω + σχολείο",
             mandatory_words=["μαθαίνω", "το πανεπιστήμιο"], all_words=SAMPLE_WORD_LIST, difficulty=2,
             personal_pronouns=False),
    TestCase(name="[D2] past only – πηγαίνω",
             mandatory_words=["πηγαίνω", "το μουσείο"], all_words=SAMPLE_WORD_LIST, difficulty=2,
             tenses=["past"]),
    TestCase(name="[D2] future only – κάνω + δουλειά",
             mandatory_words=["κάνω", "η δουλειά"], all_words=SAMPLE_WORD_LIST, difficulty=2,
             tenses=["future"]),
    TestCase(name="[D2] singular – τρώω + ψωμί",
             mandatory_words=["τρώω", "το γάλα"], all_words=SAMPLE_WORD_LIST, difficulty=2,
             plural=False),
    TestCase(name="[D2] ακούω + φαγητό",
             mandatory_words=["ακούω", "το φαγητό"], all_words=SAMPLE_WORD_LIST, difficulty=2),

    # ── DIFFICULTY 3 (10-15 words) ────────────────────────────────────────────
    TestCase(name="[D3] αγαπώ + παιδί + σπίτι",
             mandatory_words=["αγαπώ / αγαπάω", "το παιδί", "το μουσείο"], all_words=SAMPLE_WORD_LIST, difficulty=3),
    TestCase(name="[D3] θέλω + κάνω + δουλειά",
             mandatory_words=["θέλω", "κάνω", "η δουλειά"], all_words=SAMPLE_WORD_LIST, difficulty=3),
    TestCase(name="[D3] μαθαίνω + σχολείο + παιδί",
             mandatory_words=["μαθαίνω", "το πανεπιστήμιο", "το παιδί"], all_words=SAMPLE_WORD_LIST, difficulty=3),
    TestCase(name="[D3] βλέπω + έχω + φίλος",
             mandatory_words=["βλέπω", "έχω", "ο φίλος"], all_words=SAMPLE_WORD_LIST, difficulty=3),
    TestCase(name="[D3] present only – θέλω + κάνω + δουλειά",
             mandatory_words=["θέλω", "κάνω", "η δουλειά"], all_words=SAMPLE_WORD_LIST, difficulty=3,
             tenses=["present"]),
    TestCase(name="[D3] past only – πηγαίνω + σχολείο",
             mandatory_words=["πηγαίνω", "το πανεπιστήμιο", "μαθαίνω"], all_words=SAMPLE_WORD_LIST, difficulty=3,
             tenses=["past"]),
    TestCase(name="[D3] no pronouns – αγαπώ + φαγητό + σπίτι",
             mandatory_words=["αγαπώ / αγαπάω", "το φαγητό", "το μουσείο"], all_words=SAMPLE_WORD_LIST, difficulty=3,
             personal_pronouns=False),
    TestCase(name="[D3] singular – θέλω + νερό + φαγητό",
             mandatory_words=["θέλω", "το γάλα", "το φαγητό"], all_words=SAMPLE_WORD_LIST, difficulty=3,
             plural=False),
    TestCase(name="[D3] future – έχω + σπίτι + παιδί",
             mandatory_words=["έχω", "το μουσείο", "το παιδί"], all_words=SAMPLE_WORD_LIST, difficulty=3,
             tenses=["future"]),
]

# ──────────────────────────────────────────────────────────────────────────────
# Mock test cases (used in --mock mode with pre-defined responses)
# ──────────────────────────────────────────────────────────────────────────────

MOCK_TEST_CASES: List[TestCase] = [
    TestCase(name="[MOCK-PASS] Easy – house",
             mandatory_words=["το παραμύθι"], all_words=SAMPLE_WORD_LIST, difficulty=1, expect_pass=True),
    TestCase(name="[MOCK-PASS] Easy – house sentence",
             mandatory_words=["το μουσείο"], all_words=SAMPLE_WORD_LIST, difficulty=1, expect_pass=True),
    TestCase(name="[MOCK-PASS] Medium – food sentence",
             mandatory_words=["τρώω", "το γάλα"], all_words=SAMPLE_WORD_LIST, difficulty=2, expect_pass=True),
    TestCase(name="[MOCK-PASS] Medium – school (no pronouns)",
             mandatory_words=["μαθαίνω", "το πανεπιστήμιο"], all_words=SAMPLE_WORD_LIST, difficulty=2,
             personal_pronouns=False, expect_pass=True),
    TestCase(name="[MOCK-PASS] Hard – love/house",
             mandatory_words=["αγαπώ", "το παιδί", "το μουσείο"], all_words=SAMPLE_WORD_LIST, difficulty=3, expect_pass=True),
    TestCase(name="[MOCK-PASS] Hard – work sentence",
             mandatory_words=["θέλω", "κάνω", "η δουλειά"], all_words=SAMPLE_WORD_LIST, difficulty=3,
             tenses=["present"], expect_pass=True),
    # Intentionally bad responses — validator should detect and FAIL them
    TestCase(name="[MOCK-FAIL-EXPECTED] Unknown word εξερευνώ",
             mandatory_words=["INVALID_TEST"], all_words=SAMPLE_WORD_LIST, difficulty=1, expect_pass=False),
    TestCase(name="[MOCK-FAIL-EXPECTED] Sentence too short",
             mandatory_words=["SHORT_TEST"], all_words=SAMPLE_WORD_LIST, difficulty=1, expect_pass=False),
]

# ──────────────────────────────────────────────────────────────────────────────
# Standalone validator
# ──────────────────────────────────────────────────────────────────────────────

class SentenceValidator:
    ALWAYS_ALLOWED: set = (
        {t.lower() for t in _ARTICLES}
        | {t.lower() for t in _HELPER_VERB}
        | {t.lower() for t in _CONJUNCTIONS}
    )

    def __init__(self, user_words: List[str]):
        self.allowed: set = set(self.ALWAYS_ALLOWED)
        for w in user_words:
            self.allowed.update(_expand_word_forms(w))
        self.allowed.update({_strip_accents(t) for t in self.allowed})
        self.stems = _build_stem_set(self.allowed)

    def unknown_tokens(self, sentence: str) -> List[str]:
        bad = []
        for token in _tokenize_sentence(sentence):
            if token in self.allowed or _strip_accents(token) in self.allowed:
                continue
            stripped = _strip_accents(token)
            # Stem-based match to handle conjugation/declension
            if len(token) >= _MIN_STEM_LEN and token[:_MIN_STEM_LEN] in self.stems:
                continue
            if len(stripped) >= _MIN_STEM_LEN and stripped[:_MIN_STEM_LEN] in self.stems:
                continue
            bad.append(token)
        return bad

    def word_count_ok(self, sentence: str, difficulty: int) -> tuple:
        wc = len(sentence.split())
        lo, hi = {1: (3, 5), 2: (6, 9), 3: (10, 15)}.get(difficulty, (3, 5))
        return lo <= wc <= hi, wc, lo, hi

# ──────────────────────────────────────────────────────────────────────────────
# Result tracking
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    case_name: str
    difficulty: int
    sentence: Optional[str]
    translation: Optional[str]
    word_count: int
    word_count_ok: bool
    unknown_words: List[str]
    passed: bool
    expected_pass: bool = True

    def validator_passed(self) -> bool:
        """Whether technical validation passed (sentence exists + length OK + no unknown words)."""
        return bool(self.sentence) and self.word_count_ok and not self.unknown_words

    def test_passed(self) -> bool:
        """Whether the test RESULT matched the expectation."""
        return self.validator_passed() == self.expected_pass

    def summary_line(self) -> str:
        verdict = "✅" if self.test_passed() else "❌"
        issues = []
        if not self.word_count_ok:
            lo, hi = {1: (3, 5), 2: (6, 9), 3: (10, 15)}.get(self.difficulty, (3, 5))
            issues.append(f"length {self.word_count} (expected {lo}–{hi})")
        if self.unknown_words:
            issues.append(f"unknown: {self.unknown_words}")
        if not self.sentence:
            issues.append("NO SENTENCE GENERATED")
        expected_str = "" if self.expected_pass else " [expected FAIL]"
        issue_str = " | ".join(issues) if issues else "OK"
        return f"{verdict} [{self.case_name}]{expected_str}  {self.sentence or '—'}  ({issue_str})"

# ──────────────────────────────────────────────────────────────────────────────
# Mock AI response helper
# ──────────────────────────────────────────────────────────────────────────────

def _make_mock_client(mandatory_words: List[str], difficulty: int):
    """Return a mock OpenAI client that returns a pre-defined sentence."""
    import json
    key = "|".join(mandatory_words)
    mock_data = MOCK_RESPONSES.get((key, difficulty))
    if mock_data is None:
        key = mandatory_words[0] if mandatory_words else ""
        mock_data = MOCK_RESPONSES.get((key, difficulty))
    if mock_data is None:
        mock_data = {"greek": "", "russian": "", "used_greek_words": []}

    mock_content = json.dumps(mock_data)
    mock_message = MagicMock()
    mock_message.content = mock_content
    mock_choice = MagicMock()
    mock_choice.message = mock_message
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    return mock_client

# ──────────────────────────────────────────────────────────────────────────────
# Core runner
# ──────────────────────────────────────────────────────────────────────────────

async def run_test_case(
    service: AIService,
    validator: SentenceValidator,
    tc: TestCase,
    verbose: bool = False,
    mock: bool = False,
) -> RunResult:
    system_prompt = service.generate_system_prompt(
        all_words=tc.all_words,
        plural=tc.plural,
        tenses=tc.tenses,
        personal_pronouns=tc.personal_pronouns,
        possessive_pronouns=tc.possessive_pronouns,
        prepositions=tc.prepositions,
    )

    if verbose:
        print(f"\n{'─'*62}")
        print(f"  [{tc.name}]")
        print(f"  Difficulty  : {tc.difficulty}")
        print(f"  Mandatory   : {tc.mandatory_words}")
        print(f"  Plural      : {tc.plural}  |  Tenses: {tc.tenses}")

    if mock:
        service.client = _make_mock_client(tc.mandatory_words, tc.difficulty)

    result = await service.generate_sentence(
        review_words=tc.mandatory_words,
        general_words=[w for w in tc.all_words if w not in tc.mandatory_words],
        difficulty=tc.difficulty,
        system_prompt=system_prompt,
        plural=tc.plural,
        tenses=tc.tenses,
        personal_pronouns=tc.personal_pronouns,
        possessive_pronouns=tc.possessive_pronouns,
        prepositions=tc.prepositions,
        all_user_words=tc.all_words,
    )

    if not result:
        if verbose:
            print("  ❌ No sentence generated!")
        return RunResult(
            case_name=tc.name, difficulty=tc.difficulty,
            sentence=None, translation=None, word_count=0,
            word_count_ok=False, unknown_words=[], passed=False,
            expected_pass=tc.expect_pass,
        )

    sentence = result["greek"]
    translation = result.get("russian", "")
    unknown = validator.unknown_tokens(sentence)
    wc_ok, wc, lo, hi = validator.word_count_ok(sentence, tc.difficulty)

    if verbose:
        val_status = "✅ PASS" if (wc_ok and not unknown) else "❌ FAIL"
        print(f"  {val_status}")
        print(f"  Sentence    : {sentence}")
        print(f"  Translation : {translation}")
        print(f"  Word count  : {wc} (expected {lo}–{hi}) {'✅' if wc_ok else '❌'}")
        if unknown:
            print(f"  ❌ Unknown  : {unknown}")
        else:
            print(f"  ✅ Vocabulary OK")

    validator_ok = wc_ok and not unknown and bool(sentence)
    return RunResult(
        case_name=tc.name, difficulty=tc.difficulty,
        sentence=sentence, translation=translation,
        word_count=wc, word_count_ok=wc_ok,
        unknown_words=unknown, passed=validator_ok,
        expected_pass=tc.expect_pass,
    )

# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

async def main(verbose: bool, runs: int, mock: bool):
    mode = "MOCK" if mock else "LIVE (Groq)"
    print("═" * 62)
    print(f"  Greek Bot — Word Adherence Test Suite  [{mode}]")
    print("═" * 62)

    service = AIService()
    test_cases = MOCK_TEST_CASES if mock else LIVE_TEST_CASES

    total = 0
    ok_count = 0
    results_all: List[RunResult] = []

    # Per-difficulty stats (for live mode)
    diff_stats = {1: {"ok": 0, "total": 0}, 2: {"ok": 0, "total": 0}, 3: {"ok": 0, "total": 0}}

    for tc in test_cases:
        validator = SentenceValidator(tc.all_words)
        for run_idx in range(runs):
            print(f"\n{'·'*62}")
            label = tc.name
            if runs > 1:
                label += f"  (run {run_idx+1}/{runs})"
            print(f"  CASE : {label}")

            r = await run_test_case(service, validator, tc, verbose=verbose, mock=mock)
            results_all.append(r)
            total += 1

            passes = r.test_passed()
            if passes:
                ok_count += 1
            if not verbose:
                print(f"  {r.summary_line()}")

            if not mock:
                diff_stats[tc.difficulty]["total"] += 1
                if r.validator_passed():
                    diff_stats[tc.difficulty]["ok"] += 1

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "═" * 62)
    print("  SUMMARY")
    print("═" * 62)
    failed = [r for r in results_all if not r.test_passed()]
    print(f"  Tests passed : {ok_count}/{total}")
    print(f"  Tests failed : {len(failed)}/{total}")

    if not mock:
        print()
        print("  Per-difficulty breakdown:")
        for d in [1, 2, 3]:
            ds = diff_stats[d]
            label = {1: "Easy   (3-5 words)", 2: "Medium (6-9 words)", 3: "Hard  (10-15 words)"}[d]
            bar_ok = ds["ok"]
            bar_total = ds["total"]
            pct = int(100 * bar_ok / bar_total) if bar_total else 0
            icon = "✅" if bar_ok == bar_total else ("⚠️" if pct >= 50 else "❌")
            print(f"    {icon} {label}: {bar_ok}/{bar_total} ({pct}%)")

        if failed:
            print("\n  Failed cases:")
            for r in failed:
                issues = []
                if not r.word_count_ok:
                    lo, hi = {1: (3, 5), 2: (6, 9), 3: (10, 15)}.get(r.difficulty, (3, 5))
                    issues.append(f"length {r.word_count}/{lo}–{hi}")
                if r.unknown_words:
                    issues.append(f"unknown={r.unknown_words}")
                if not r.sentence:
                    issues.append("no sentence")
                print(f"    ❌ {r.case_name}: {' | '.join(issues)}")
        else:
            print("\n  ✅ All live tests passed!")
    else:
        if failed:
            print("\n  Failed:")
            for r in failed:
                issues = []
                if not r.word_count_ok:
                    lo, hi = {1: (3, 5), 2: (6, 9), 3: (10, 15)}.get(r.difficulty, (3, 5))
                    issues.append(f"length {r.word_count}/{lo}–{hi}")
                if r.unknown_words:
                    issues.append(f"unknown={r.unknown_words}")
                if not r.sentence:
                    issues.append("no sentence")
                expected_str = "" if r.expected_pass else " (expected to fail!)"
                print(f"    ❌ {r.case_name}{expected_str}: {' | '.join(issues)}")
            sys.exit(1)
        else:
            print("\n  ✅ All tests produced expected results!")

    if not mock and failed:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Word adherence tests for greek-bot AI service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show full sentence details per test")
    parser.add_argument("--runs", type=int, default=1,
                        help="How many times to run each case (default: 1)")
    parser.add_argument("--mock", action="store_true",
                        help="Use pre-defined mock responses (no LM Studio needed)")
    args = parser.parse_args()
    asyncio.run(main(verbose=args.verbose, runs=args.runs, mock=args.mock))
