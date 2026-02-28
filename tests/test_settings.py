"""
Tests for all bot settings using a LIVE LM Studio model.

Validates that every user setting actually affects the AI-generated output:
  1. difficulty_level (1/2/3) — word count ranges
  2. plural_enabled — singular only vs both
  3. tense_restriction — present / past / future
  4. personal_pronouns_enabled — εγώ, εσύ, αυτός …
  5. possessive_pronouns_enabled — μου, σου, του …
  6. prepositions_enabled — με, για, από, σε …
  7. interrogative_words_enabled — τι, ποιος, πού, πότε, πώς, γιατί …

Usage:
  # Run all settings tests (LM Studio must be running locally)
  python tests/test_settings.py

  # Verbose — show every generated sentence
  python tests/test_settings.py -v

  # Run a specific setting group
  python tests/test_settings.py --setting tenses
  python tests/test_settings.py --setting plural
  python tests/test_settings.py --setting difficulty
  python tests/test_settings.py --setting personal_pronouns
  python tests/test_settings.py --setting possessive_pronouns
  python tests/test_settings.py --setting prepositions
  python tests/test_settings.py --setting interrogative

  # Multiple runs per case for statistical confidence
  python tests/test_settings.py --runs 3
"""

import asyncio
import argparse
import os
import sys
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple
from datetime import datetime

# Fix Windows terminal encoding for Greek characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Make project root importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Override Docker URL to localhost for local test runs
if "LM_STUDIO_BASE_URL" not in os.environ:
    os.environ.setdefault("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")

from bot.services.ai_service import (
    AIService,
    _ARTICLES,
    _HELPER_VERB,
    _CONJUNCTIONS,
    _tokenize_sentence,
    _strip_accents,
    _expand_word_forms,
)
from bot.data.words import ALL_WORDS

# ──────────────────────────────────────────────────────────────────────────────
# Shared word list — same as a real user with all lessons selected
# ──────────────────────────────────────────────────────────────────────────────
WORD_LIST: List[str] = ALL_WORDS

# Small focused word list for settings tests (verbs + nouns — easier to force tense usage)
FOCUSED_WORDS: List[str] = [
    "πηγαίνω", "τρώω", "βλέπω", "θέλω", "κάνω", "μαθαίνω", "γράφω",
    "διαβάζω", "ακούω", "παίζω", "μιλώ / μιλάω", "αγαπώ / αγαπάω",
    "το μουσείο", "το πανεπιστήμιο", "το αγόρι", "ο φίλος", "η μαμά",
    "η δουλειά", "το φαγητό", "η θάλασσα", "ο δρόμος", "το παραμύθι",
    "μεγάλος", "μικρός", "καλός", "ωραίος", "αύριο",
    "τώρα", "εδώ", "εκεί",
]

# ──────────────────────────────────────────────────────────────────────────────
# Greek linguistic helpers
# ──────────────────────────────────────────────────────────────────────────────

# Personal pronouns (all forms)
PERSONAL_PRONOUNS: Set[str] = {
    "εγώ", "εγω", "εσύ", "εσυ",
    "αυτός", "αυτος", "αυτή", "αυτη", "αυτό", "αυτο",
    "εμείς", "εμεις", "εσείς", "εσεις",
    "αυτοί", "αυτοι", "αυτές", "αυτες", "αυτά", "αυτα",
    # Weak (clitic) object forms
    "με", "σε", "τον", "την", "το", "μας", "σας", "τους", "τις", "τα",
}

# Possessive pronouns (short forms)
POSSESSIVE_PRONOUNS: Set[str] = {
    "μου", "σου", "του", "της", "μας", "σας", "τους",
}

# Prepositions
PREPOSITIONS: Set[str] = {
    "με", "για", "από", "απο", "σε",
    "στο", "στη", "στην", "στον", "στους", "στις", "στα",
    "πριν", "μετά", "μετα", "κατά", "κατα",
    "μέχρι", "μεχρι", "χωρίς", "χωρις",
    "πάνω", "πανω", "κάτω", "κατω", "πίσω", "πισω",
    "μεταξύ", "μεταξυ", "κοντά", "κοντα",
}

# Interrogative words
INTERROGATIVE_WORDS: Set[str] = {
    "τι", "τί", "ποιος", "ποια", "ποιο", "ποιοι", "ποιες", "ποια",
    "πού", "που", "πότε", "ποτε", "πώς", "πως", "γιατί", "γιατι",
    "πόσο", "ποσο", "πόσα", "ποσα", "πόσοι", "ποσοι", "πόσες", "ποσες",
    "μήπως", "μηπως",
}

# Greek future markers
FUTURE_MARKERS: Set[str] = {"θα"}

# Past tense markers / common past-tense verb patterns
# In Greek, past tense (aorist) often has an augment (ε- prefix) or specific endings
# We use heuristics: augmented verbs, ήταν, past helper forms
PAST_MARKERS: Set[str] = {
    # είμαι past forms
    "ήταν", "ηταν", "ήμουν", "ημουν", "ήσουν", "ησουν",
    "ήμαστε", "ημαστε", "ήσαστε", "ησαστε", "ήτανε", "ητανε",
    # Common irregular past forms
    "πήγα", "πηγα", "πήγε", "πηγε", "πήγαμε", "πηγαμε",
    "πήγαν", "πηγαν", "πήγαινα", "πηγαινα", "πήγαινε", "πηγαινε",
    "έκανα", "εκανα", "έκανε", "εκανε", "κάναμε", "καναμε",
    "είδα", "ειδα", "είδε", "ειδε", "είδαμε", "ειδαμε",
    "ήρθα", "ηρθα", "ήρθε", "ηρθε", "ήρθαμε", "ηρθαμε",
    "είπα", "ειπα", "είπε", "ειπε", "είπαμε", "ειπαμε",
    "ήθελα", "ηθελα", "ήθελε", "ηθελε",
    "έμαθα", "εμαθα", "έμαθε", "εμαθε",
    "έγραψα", "εγραψα", "έγραψε", "εγραψε",
    "διάβασα", "διαβασα", "διάβασε", "διαβασε",
    "έπαιξα", "επαιξα", "έπαιξε", "επαιξε",
    "αγόρασα", "αγορασα", "αγόρασε", "αγορασε",
    "έβλεπα", "εβλεπα", "έβλεπε", "εβλεπε",
    "έγραφα", "εγραφα", "έγραφε", "εγραφε",
    "έφαγα", "εφαγα", "έφαγε", "εφαγε",
    "ήπια", "ηπια", "ήπιε", "ηπιε",
}

# Present-tense indicators: verbs like είναι (present), 1st/2nd person present
PRESENT_MARKERS: Set[str] = {
    "είναι", "ειναι", "είμαι", "ειμαι", "είσαι", "εισαι",
    "είμαστε", "ειμαστε", "είστε", "ειστε",
}

# Common Greek plural noun/adj endings (heuristic)
PLURAL_NOUN_ENDINGS = ["οι", "ες", "ια", "ά", "ών", "ους", "εις"]

# Common Greek plural article forms
PLURAL_ARTICLES = {"οι", "τα", "τις", "τους", "των"}


def _normalize(text: str) -> str:
    """Lowercase + strip accents."""
    nfkd = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def sentence_contains_any(sentence: str, word_set: Set[str]) -> List[str]:
    """Return list of tokens from sentence that appear in word_set."""
    tokens = _tokenize_sentence(sentence)
    found = []
    for tok in tokens:
        if tok in word_set or _strip_accents(tok) in word_set:
            found.append(tok)
    return found


def sentence_has_future(sentence: str) -> bool:
    """Check if sentence contains the future particle θα."""
    tokens = _tokenize_sentence(sentence)
    return any(t in FUTURE_MARKERS for t in tokens)


def sentence_has_past(sentence: str) -> bool:
    """
    Heuristic check for past tense in Greek.
    Looks for: past forms of είμαι, common irregular past forms,
    and common aorist/imperfect endings.
    """
    tokens = _tokenize_sentence(sentence)
    # Check for explicit past markers (including irregular forms)
    for tok in tokens:
        t_stripped = _strip_accents(tok)
        if tok in PAST_MARKERS or t_stripped in {_strip_accents(m) for m in PAST_MARKERS}:
            return True
    # Check for common aorist/imperfect endings
    for tok in tokens:
        if len(tok) <= 3:
            continue
        t = _strip_accents(tok)
        if any(t.endswith(suf) for suf in [
            # Aorist active
            "σα", "σες", "σε", "σαμε", "σατε", "σαν",
            "ξα", "ξες", "ξε", "ξαμε", "ξατε", "ξαν",
            "ψα", "ψες", "ψε", "ψαμε", "ψατε", "ψαν",
            # Imperfect
            "ουσα", "ουσες", "ουσε", "ουσαμε", "ουσατε", "ουσαν",
            "αγα", "αγες", "αγε", "αγαμε", "αγατε", "αγαν",
            # Aorist passive
            "ηκα", "ηκες", "ηκε", "ηκαμε", "ηκατε", "ηκαν",
            "θηκα", "θηκες", "θηκε", "θηκαμε", "θηκατε", "θηκαν",
            # Imperfect -αινα pattern
            "αινα", "αινες", "αινε",
        ]):
            return True
    return False


def sentence_has_present(sentence: str) -> bool:
    """
    Heuristic: present tense if no θα and no past markers,
    or if explicit present-tense forms like είναι/είμαι exist.
    """
    tokens = _tokenize_sentence(sentence)
    for tok in tokens:
        if tok in PRESENT_MARKERS or _strip_accents(tok) in {_strip_accents(m) for m in PRESENT_MARKERS}:
            return True
    # Check common present endings: -ω, -εις, -ει, -ουμε, -ετε, -ουν
    for tok in tokens:
        t = _strip_accents(tok)
        if any(t.endswith(suf) for suf in ["ω", "εις", "ει", "ουμε", "ετε", "ουν", "αω", "αει", "αμε", "ατε"]):
            if not sentence_has_past(sentence) and not sentence_has_future(sentence):
                return True
    return False


def sentence_has_plural(sentence: str) -> bool:
    """Heuristic: check for plural articles or plural word endings."""
    tokens = _tokenize_sentence(sentence)
    for tok in tokens:
        if tok in PLURAL_ARTICLES:
            return True
    return False


def is_question(sentence: str) -> bool:
    """Check if the sentence is a question (contains ? or interrogative words)."""
    if ";" in sentence or "?" in sentence:
        return True
    return len(sentence_contains_any(sentence, INTERROGATIVE_WORDS)) > 0


# ──────────────────────────────────────────────────────────────────────────────
# Test result
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SettingTestResult:
    setting_name: str
    test_name: str
    sentence: Optional[str]
    translation: Optional[str]
    passed: bool
    reason: str
    details: Dict = field(default_factory=dict)

    def summary_line(self) -> str:
        icon = "✅" if self.passed else "❌"
        sent_preview = (self.sentence[:60] + "…") if self.sentence and len(self.sentence) > 60 else (self.sentence or "—")
        return f"{icon} [{self.test_name}]  {sent_preview}  ({self.reason})"


# ──────────────────────────────────────────────────────────────────────────────
# Core test runner
# ──────────────────────────────────────────────────────────────────────────────

async def generate_sentence_with_settings(
    service: AIService,
    mandatory_words: List[str],
    difficulty: int = 1,
    plural: bool = True,
    tenses: List[str] = None,
    personal_pronouns: bool = True,
    possessive_pronouns: bool = True,
    prepositions: bool = True,
    interrogative_words: bool = True,
) -> Optional[Dict]:
    """Generate a sentence using the AI service with given settings."""
    if tenses is None:
        tenses = ["present", "past", "future"]

    all_words = WORD_LIST

    system_prompt = service.generate_system_prompt(
        all_words=all_words,
        plural=plural,
        tenses=tenses,
        personal_pronouns=personal_pronouns,
        possessive_pronouns=possessive_pronouns,
        prepositions=prepositions,
        interrogative_words=interrogative_words,
    )

    general = [w for w in all_words if w not in mandatory_words]

    result = await service.generate_sentence(
        review_words=mandatory_words,
        general_words=general,
        difficulty=difficulty,
        system_prompt=system_prompt,
        plural=plural,
        tenses=tenses,
        personal_pronouns=personal_pronouns,
        possessive_pronouns=possessive_pronouns,
        prepositions=prepositions,
        interrogative_words=interrogative_words,
        all_user_words=all_words,
    )
    return result


# ──────────────────────────────────────────────────────────────────────────────
# 1. DIFFICULTY TESTS
# ──────────────────────────────────────────────────────────────────────────────

async def test_difficulty(service: AIService, runs: int, verbose: bool) -> List[SettingTestResult]:
    """Test that difficulty levels produce correct word counts.
    Note: AI may occasionally produce slightly out-of-range sentences;
    we use +2 tolerance on the upper bound as a practical measure."""
    results = []
    difficulty_ranges = {1: (3, 5), 2: (6, 9), 3: (10, 15)}

    for diff, (lo, hi) in difficulty_ranges.items():
        for run in range(runs):
            test_name = f"Difficulty {diff} (run {run + 1})"
            mandatory = ["πηγαίνω", "το μουσείο"] if diff >= 2 else ["πηγαίνω"]
            if diff == 3:
                mandatory = ["πηγαίνω", "το μουσείο", "ο φίλος"]

            result = await generate_sentence_with_settings(
                service, mandatory_words=mandatory, difficulty=diff,
            )

            if not result:
                results.append(SettingTestResult(
                    setting_name="difficulty", test_name=test_name,
                    sentence=None, translation=None, passed=False,
                    reason="No sentence generated",
                ))
                continue

            sentence = result["greek"]
            wc = len(sentence.split())
            # Allow +2 tolerance on upper bound (AI sometimes exceeds slightly)
            passed = lo <= wc <= hi + 2

            results.append(SettingTestResult(
                setting_name="difficulty", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason=f"word_count={wc}, expected {lo}–{hi}" + (" ✓" if passed else " ✗"),
                details={"word_count": wc, "expected_range": (lo, hi)},
            ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# 2. PLURAL TESTS
# ──────────────────────────────────────────────────────────────────────────────

async def test_plural(service: AIService, runs: int, verbose: bool) -> List[SettingTestResult]:
    """Test plural setting: singular-only should not produce plural forms."""
    results = []

    for run in range(runs):
        # --- Singular only ---
        test_name = f"Singular only (run {run + 1})"
        result = await generate_sentence_with_settings(
            service, mandatory_words=["βλέπω", "ο φίλος"],
            difficulty=2, plural=False,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="plural", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            has_plural = sentence_has_plural(sentence)
            passed = not has_plural  # singular mode → should NOT have plural
            results.append(SettingTestResult(
                setting_name="plural", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason=f"has_plural={has_plural}" + (" ✗ (should be singular)" if not passed else " ✓"),
                details={"has_plural": has_plural},
            ))

        # --- Plural allowed ---
        test_name = f"Plural allowed (run {run + 1})"
        # Use words from the dictionary — plural forms are allowed
        result = await generate_sentence_with_settings(
            service, mandatory_words=["οι γονείς", "τα αδέλφια"],
            difficulty=2, plural=True,
        )
        # We just need to check it generates OK; it may or may not use plural
        if not result:
            results.append(SettingTestResult(
                setting_name="plural", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            results.append(SettingTestResult(
                setting_name="plural", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=True,
                reason="Generated OK (plural allowed)",
            ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# 3. TENSE TESTS
# ──────────────────────────────────────────────────────────────────────────────

async def test_tenses(service: AIService, runs: int, verbose: bool) -> List[SettingTestResult]:
    """Test tense restrictions: future-only should use θα, past-only should use past forms, etc."""
    results = []

    tense_configs = [
        ("Future only", ["future"], True, False, True),    # must have θα, must not have past
        ("Past only", ["past"], False, True, False),        # must have past, must not have θα
        ("Present only", ["present"], False, False, False), # no θα, no past markers
        ("Present+Future", ["present", "future"], None, None, None),  # either is OK
        ("All tenses", ["present", "past", "future"], None, None, None),
    ]

    verbs_for_tense = ["πηγαίνω", "κάνω"]

    for tense_label, tenses, expect_future, expect_past, must_have_future in tense_configs:
        for run in range(runs):
            test_name = f"{tense_label} (run {run + 1})"
            result = await generate_sentence_with_settings(
                service,
                mandatory_words=verbs_for_tense,
                difficulty=2,
                tenses=tenses,
            )

            if not result:
                results.append(SettingTestResult(
                    setting_name="tenses", test_name=test_name,
                    sentence=None, translation=None, passed=False,
                    reason="No sentence generated",
                ))
                continue

            sentence = result["greek"]
            has_future = sentence_has_future(sentence)
            has_past = sentence_has_past(sentence)
            has_present = sentence_has_present(sentence)

            issues = []

            # Future-only: MUST have θα, MUST NOT have past forms
            if tenses == ["future"]:
                if not has_future:
                    issues.append("missing θα (future marker)")
                if has_past:
                    issues.append(f"has past-tense forms (forbidden)")

            # Past-only: MUST NOT have θα, SHOULD have past forms
            elif tenses == ["past"]:
                if has_future:
                    issues.append("has θα (future forbidden)")
                if not has_past:
                    issues.append("no past-tense markers detected (expected past)")

            # Present-only: MUST NOT have θα, MUST NOT have past forms
            elif tenses == ["present"]:
                if has_future:
                    issues.append("has θα (future forbidden)")
                if has_past:
                    issues.append("has past-tense forms (forbidden)")

            passed = len(issues) == 0
            reason = "; ".join(issues) if issues else "OK"

            results.append(SettingTestResult(
                setting_name="tenses", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason=f"future={has_future}, past={has_past}, present={has_present} → {reason}",
                details={"has_future": has_future, "has_past": has_past, "has_present": has_present,
                         "allowed_tenses": tenses},
            ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# 4. PERSONAL PRONOUNS TESTS
# ──────────────────────────────────────────────────────────────────────────────

async def test_personal_pronouns(service: AIService, runs: int, verbose: bool) -> List[SettingTestResult]:
    """Test that disabling personal pronouns means no εγώ/εσύ/αυτός etc. in output."""
    results = []

    # Set of strictly personal (nominative) pronouns to check
    strict_personal = {
        "εγώ", "εγω", "εσύ", "εσυ",
        "αυτός", "αυτος", "αυτή", "αυτη", "αυτό", "αυτο",
        "εμείς", "εμεις", "εσείς", "εσεις",
        "αυτοί", "αυτοι", "αυτές", "αυτες", "αυτά", "αυτα",
    }

    for run in range(runs):
        # --- Disabled ---
        test_name = f"Pronouns OFF (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["θέλω", "η δουλειά"],
            difficulty=2,
            personal_pronouns=False,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="personal_pronouns", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            found = sentence_contains_any(sentence, strict_personal)
            passed = len(found) == 0
            results.append(SettingTestResult(
                setting_name="personal_pronouns", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason=f"found pronouns: {found}" if found else "OK (no pronouns)",
            ))

        # --- Enabled ---
        test_name = f"Pronouns ON (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["θέλω", "η δουλειά"],
            difficulty=2,
            personal_pronouns=True,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="personal_pronouns", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            # When enabled, we just verify generation succeeds; pronouns are optional
            results.append(SettingTestResult(
                setting_name="personal_pronouns", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=True,
                reason="Generated OK (pronouns allowed)",
            ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# 5. POSSESSIVE PRONOUNS TESTS
# ──────────────────────────────────────────────────────────────────────────────

async def test_possessive_pronouns(service: AIService, runs: int, verbose: bool) -> List[SettingTestResult]:
    """Test that disabling possessive pronouns removes μου/σου/etc. from output."""
    results = []

    for run in range(runs):
        # --- Disabled ---
        test_name = f"Possessive OFF (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["αγαπώ / αγαπάω", "η μαμά"],
            difficulty=2,
            possessive_pronouns=False,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="possessive_pronouns", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            found = sentence_contains_any(sentence, POSSESSIVE_PRONOUNS)
            passed = len(found) == 0
            results.append(SettingTestResult(
                setting_name="possessive_pronouns", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason=f"found possessives: {found}" if found else "OK (no possessives)",
            ))

        # --- Enabled ---
        test_name = f"Possessive ON (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["αγαπώ / αγαπάω", "η μαμά"],
            difficulty=2,
            possessive_pronouns=True,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="possessive_pronouns", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            results.append(SettingTestResult(
                setting_name="possessive_pronouns", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=True,
                reason="Generated OK (possessives allowed)",
            ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# 6. PREPOSITIONS TESTS
# ──────────────────────────────────────────────────────────────────────────────

async def test_prepositions(service: AIService, runs: int, verbose: bool) -> List[SettingTestResult]:
    """Test that disabling prepositions removes με/για/από/σε/etc. from output."""
    results = []

    # Strict prepositions (excluding 'σε' which may be a particle — use longer ones)
    strict_prepositions = {
        "για", "από", "απο",
        "στο", "στη", "στην", "στον", "στους", "στις", "στα",
        "πριν", "μετά", "μετα", "κατά", "κατα",
        "μέχρι", "μεχρι",
    }

    for run in range(runs):
        # --- Disabled ---
        test_name = f"Prepositions OFF (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["πηγαίνω", "το μουσείο"],
            difficulty=2,
            prepositions=False,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="prepositions", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            found = sentence_contains_any(sentence, strict_prepositions)
            passed = len(found) == 0
            results.append(SettingTestResult(
                setting_name="prepositions", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason=f"found prepositions: {found}" if found else "OK (no prepositions)",
            ))

        # --- Enabled ---
        test_name = f"Prepositions ON (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["πηγαίνω", "το μουσείο"],
            difficulty=2,
            prepositions=True,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="prepositions", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            results.append(SettingTestResult(
                setting_name="prepositions", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=True,
                reason="Generated OK (prepositions allowed)",
            ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# 7. INTERROGATIVE WORDS TESTS
# ──────────────────────────────────────────────────────────────────────────────

async def test_interrogative(service: AIService, runs: int, verbose: bool) -> List[SettingTestResult]:
    """Test that disabling interrogative words removes τι/πού/πώς/etc. from output."""
    results = []

    # Strict interrogative words (exclude "που" since it's also a relative pronoun)
    strict_interrogative = {
        "τι", "τί", "ποιος", "ποια", "ποιο", "ποιοι", "ποιες",
        "πότε", "ποτε", "πώς", "πως",
        "πόσο", "ποσο", "πόσα", "ποσα", "πόσοι", "ποσοι", "πόσες", "ποσες",
    }

    for run in range(runs):
        # --- Disabled ---
        test_name = f"Interrogative OFF (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["θέλω", "μαθαίνω"],
            difficulty=2,
            interrogative_words=False,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="interrogative", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            found = sentence_contains_any(sentence, strict_interrogative)
            is_q = is_question(sentence)
            issues = []
            if found:
                issues.append(f"interrogative words found: {found}")
            if is_q:
                issues.append("sentence is a question")
            passed = len(issues) == 0
            results.append(SettingTestResult(
                setting_name="interrogative", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason="; ".join(issues) if issues else "OK (no interrogatives)",
            ))

        # --- Enabled ---
        test_name = f"Interrogative ON (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["θέλω", "μαθαίνω"],
            difficulty=2,
            interrogative_words=True,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="interrogative", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            results.append(SettingTestResult(
                setting_name="interrogative", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=True,
                reason="Generated OK (interrogatives allowed)",
            ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# 8. COMBINED SETTINGS TESTS (multiple settings at once)
# ──────────────────────────────────────────────────────────────────────────────

async def test_combined(service: AIService, runs: int, verbose: bool) -> List[SettingTestResult]:
    """Test multiple settings combined to ensure they don't conflict."""
    results = []

    strict_personal = {
        "εγώ", "εγω", "εσύ", "εσυ",
        "αυτός", "αυτος", "αυτή", "αυτη", "αυτό", "αυτο",
        "εμείς", "εμεις", "εσείς", "εσεις",
        "αυτοί", "αυτοι", "αυτές", "αυτες", "αυτά", "αυτα",
    }

    for run in range(runs):
        # --- Future + singular + no pronouns ---
        test_name = f"Future+Singular+NoPronouns (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["κάνω", "η δουλειά"],
            difficulty=2,
            plural=False,
            tenses=["future"],
            personal_pronouns=False,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="combined", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            issues = []

            has_future = sentence_has_future(sentence)
            if not has_future:
                issues.append("missing θα")

            has_plural = sentence_has_plural(sentence)
            if has_plural:
                issues.append("has plural forms")

            found_pronouns = sentence_contains_any(sentence, strict_personal)
            if found_pronouns:
                issues.append(f"has pronouns: {found_pronouns}")

            has_past = sentence_has_past(sentence)
            if has_past:
                issues.append("has past forms")

            passed = len(issues) == 0

            results.append(SettingTestResult(
                setting_name="combined", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason="; ".join(issues) if issues else "OK",
                details={"has_future": has_future, "has_plural": has_plural,
                         "found_pronouns": found_pronouns},
            ))

        # --- Past + no possessives + no prepositions ---
        test_name = f"Past+NoPossessives+NoPrepositions (run {run + 1})"
        result = await generate_sentence_with_settings(
            service,
            mandatory_words=["βλέπω", "ο φίλος"],
            difficulty=2,
            tenses=["past"],
            possessive_pronouns=False,
            prepositions=False,
        )

        if not result:
            results.append(SettingTestResult(
                setting_name="combined", test_name=test_name,
                sentence=None, translation=None, passed=False,
                reason="No sentence generated",
            ))
        else:
            sentence = result["greek"]
            issues = []

            has_past_flag = sentence_has_past(sentence)
            has_future = sentence_has_future(sentence)
            if has_future:
                issues.append("has θα (future forbidden)")
            if not has_past_flag:
                issues.append("no past tense detected")

            found_possessives = sentence_contains_any(sentence, POSSESSIVE_PRONOUNS)
            if found_possessives:
                issues.append(f"has possessives: {found_possessives}")

            strict_preps = {
                "για", "από", "απο",
                "στο", "στη", "στην", "στον", "στους", "στις", "στα",
            }
            found_preps = sentence_contains_any(sentence, strict_preps)
            if found_preps:
                issues.append(f"has prepositions: {found_preps}")

            passed = len(issues) == 0

            results.append(SettingTestResult(
                setting_name="combined", test_name=test_name,
                sentence=sentence, translation=result.get("russian"),
                passed=passed,
                reason="; ".join(issues) if issues else "OK",
            ))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

SETTING_TESTS = {
    "difficulty": test_difficulty,
    "plural": test_plural,
    "tenses": test_tenses,
    "personal_pronouns": test_personal_pronouns,
    "possessive_pronouns": test_possessive_pronouns,
    "prepositions": test_prepositions,
    "interrogative": test_interrogative,
    "combined": test_combined,
}


async def main(verbose: bool, runs: int, setting: Optional[str]):
    print("═" * 70)
    print("  Greek Bot — Settings Validation Test Suite  [LIVE LM Studio]")
    print("═" * 70)

    url = os.environ.get("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
    print(f"  LM Studio URL : {url}")
    print(f"  Runs per case  : {runs}")
    print(f"  Test filter    : {setting or 'ALL'}")
    print(f"  Started at     : {datetime.now().strftime('%H:%M:%S')}")
    print()

    service = AIService()

    tests_to_run = {}
    if setting:
        if setting in SETTING_TESTS:
            tests_to_run = {setting: SETTING_TESTS[setting]}
        else:
            print(f"  ❌ Unknown setting: '{setting}'")
            print(f"  Available: {', '.join(SETTING_TESTS.keys())}")
            sys.exit(1)
    else:
        tests_to_run = SETTING_TESTS

    all_results: List[SettingTestResult] = []
    group_stats: Dict[str, Tuple[int, int]] = {}

    for group_name, test_fn in tests_to_run.items():
        print(f"\n{'─' * 70}")
        print(f"  ▶ Testing: {group_name.upper().replace('_', ' ')}")
        print(f"{'─' * 70}")

        group_results = await test_fn(service, runs, verbose)
        all_results.extend(group_results)

        ok = sum(1 for r in group_results if r.passed)
        total = len(group_results)
        group_stats[group_name] = (ok, total)

        for r in group_results:
            if verbose:
                print(f"\n  {r.summary_line()}")
                if r.sentence:
                    print(f"    🇬🇷 {r.sentence}")
                    print(f"    🇷🇺 {r.translation or '—'}")
            else:
                print(f"  {r.summary_line()}")

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'═' * 70}")
    print("  SUMMARY")
    print(f"{'═' * 70}")

    total_ok = sum(ok for ok, _ in group_stats.values())
    total_all = sum(total for _, total in group_stats.values())

    for group_name, (ok, total) in group_stats.items():
        pct = int(100 * ok / total) if total else 0
        icon = "✅" if ok == total else ("⚠️" if pct >= 50 else "❌")
        label = group_name.replace("_", " ").title()
        print(f"  {icon} {label:30s}: {ok}/{total} ({pct}%)")

    print(f"\n  Total: {total_ok}/{total_all}")

    failed = [r for r in all_results if not r.passed]
    if failed:
        print(f"\n  Failed tests ({len(failed)}):")
        for r in failed:
            print(f"    ❌ [{r.setting_name}] {r.test_name}: {r.reason}")
            if r.sentence:
                print(f"       Sentence: {r.sentence}")
        sys.exit(1)
    else:
        print(f"\n  ✅ All tests passed!")

    print(f"\n  Finished at: {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Settings validation tests for greek-bot AI service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show full sentence details per test")
    parser.add_argument("--runs", type=int, default=2,
                        help="How many times to run each case (default: 2)")
    parser.add_argument("--setting", "-s", type=str, default=None,
                        choices=list(SETTING_TESTS.keys()),
                        help="Run only a specific setting group")
    args = parser.parse_args()
    asyncio.run(main(verbose=args.verbose, runs=args.runs, setting=args.setting))
