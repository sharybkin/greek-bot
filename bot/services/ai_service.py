"""
AI service for sentence generation with strict vocabulary adherence.
Only words from the user's word list and the verb 'είναι' are allowed.
"""

import json
import re
import unicodedata
from typing import List, Dict, Optional
from groq import AsyncGroq
from bot.config import config
from bot.utils.logger import logger


# ---------------------------------------------------------------------------
# Greek grammar helpers — hardcoded "allowed filler" tokens
# ---------------------------------------------------------------------------

# Allowed articles (all forms)
_ARTICLES: set[str] = {
    "ο", "η", "το", "οι", "τα",
    "τον", "την", "τη", "του", "της", "των",
    "τους", "τις",
}

# The only allowed helper verb
_HELPER_VERB: set[str] = {
    "είναι", "ειναι",       # 3rd person present
    "είμαι", "ειμαι",       # 1st person
    "είσαι", "εισαι",       # 2nd person
    "είμαστε", "ειμαστε",   # 1st plural
    "είστε", "ειστε",       # 2nd plural
    "είναι",                # 3rd plural (same form)
    "ήταν", "ηταν",         # past
    "θα είναι", "θα ειναι", # future (as phrase)
    "θα είμαι", "θα ειμαι",
    "θα είσαι", "θα εισαι",
    "ήμουν", "ημουν",
    "ήσουν", "ησουν",
    "ήτανε", "ητανε",
    "ήμαστε", "ημαστε",
    "ήσαστε", "ησαστε",
    "ήσασταν", "ησασταν",
    # supporting word θα (will)
    "θα",
}

# Allowed conjunctions and particles
_CONJUNCTIONS: set[str] = {
    "και", "ή", "αλλά", "αλλα", "όμως", "ομως",
    "που", "ότι", "οτι", "ώστε", "ωστε",
    "αν", "όταν", "οταν", "ενώ", "ενω",
    "γιατί", "γιατι", "επειδή", "επειδη",
    "ναι", "όχι", "οχι",
    "με", "για", "από", "απο", "σε", "στο", "στη", "στην",
    "στον", "στους", "στις", "στα",
    "πριν", "μετά", "μετα", "κατά", "κατα",
    "μέχρι", "μεχρι", "πάνω", "πανω", "κάτω", "κατω",
    "πίσω", "πισω", "εδώ", "εδω", "εκεί", "εκει",
    "πάντα", "παντα", "ποτέ", "ποτε", "τώρα", "τωρα",
    "πολύ", "πολυ", "λίγο", "λιγο",
    "κάθε", "καθε",
    # Negative / modal
    "δεν", "μην", "μη",
    "να", "ας",
    # Personal pronouns (if enabled they pass through)
    "εγώ", "εγω", "εσύ", "εσυ", "αυτός", "αυτος",
    "αυτή", "αυτη", "αυτό", "αυτο",
    "εμείς", "εμεις", "εσείς", "εσεις",
    "αυτοί", "αυτοι", "αυτές", "αυτες", "αυτά", "αυτα",
    # Possessive short forms
    "μου", "σου", "του", "της", "μας", "σας", "τους",
    # Interrogative
    "τι", "τί", "ποιος", "ποια", "ποιο",
    "πού", "που", "πότε", "ποτε", "πώς", "πως", "γιατί",
}

# Punctuation characters to strip when tokenising
_PUNCT_RE = re.compile(r"[^\w\u0370-\u03FF\u1F00-\u1FFF]", re.UNICODE)


def _strip_accents(text: str) -> str:
    """Return text with all diacritics removed (for accent-insensitive matching)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokenize_sentence(sentence: str) -> list[str]:
    """Split a sentence into lowercase word tokens, stripping punctuation."""
    tokens = []
    for word in sentence.split():
        cleaned = _PUNCT_RE.sub("", word).lower().strip()
        if cleaned:
            tokens.append(cleaned)
    return tokens


def _expand_word_forms(word_entry: str) -> set[str]:
    """
    Expand a dictionary entry like 'περίμενε / περιμένετε' or 'ο / η κτηνίατρος'
    into a set of lowercase base tokens.  Also adds the accent-stripped variant
    so that ε vs έ differences do not cause false negatives.
    """
    forms: set[str] = set()
    parts = re.split(r"[/,]", word_entry)
    for part in parts:
        token = part.strip().lower()
        # Remove parenthetical notes like "(μου)"
        token = re.sub(r"\s*\(.*?\)", "", token).strip()
        if not token:
            continue
        forms.add(token)
        forms.add(_strip_accents(token))
        # For compound entries like "ο κτηνίατρος" keep the last word as well
        sub_tokens = token.split()
        for st in sub_tokens:
            forms.add(st)
            forms.add(_strip_accents(st))
    return forms


# Minimum stem length for prefix matching (avoids matching short unrelated words)
_MIN_STEM_LEN = 4


def _build_stem_set(allowed_tokens: set[str]) -> set[str]:
    """
    Build a set of 5-char prefixes (stems) from all allowed tokens.
    Used for leniently matching conjugated/declined forms.
    """
    stems: set[str] = set()
    for tok in allowed_tokens:
        if len(tok) >= _MIN_STEM_LEN:
            stems.add(tok[:_MIN_STEM_LEN])
    return stems


class AIService:
    """Service for AI-powered sentence generation using Groq API.
    
    Vocabulary policy
    -----------------
    The generated sentence may ONLY contain:
      - Words from the user's full word list (all lessons, all forms).
      - Articles (ο/η/το/οι/τα and their declensions).
      - The verb είναι and all its conjugated forms.
      - Standard conjunctions, prepositions, particles, and pronouns.
    Any other word causes the attempt to be retried.
    """

    def __init__(self):
        self.client = AsyncGroq(api_key=config.groq_api_key)
        self.model = config.groq_model
        self.max_retries = 5

    # ------------------------------------------------------------------
    # Allowed-token set builder
    # ------------------------------------------------------------------

    def _build_allowed_tokens(
        self, all_words: List[str]
    ) -> tuple[set[str], set[str]]:
        """
        Build the complete set of allowed lowercase tokens from the user's word list,
        articles, the verb είναι, and Greek grammar fillers.

        Returns (allowed_exact, allowed_stems) where:
          - allowed_exact: full token set for exact matching
          - allowed_stems: 5-char prefix set for stem/conjugation matching
        """
        allowed: set[str] = set()

        # Filler tokens that are always allowed
        for grp in (_ARTICLES, _HELPER_VERB, _CONJUNCTIONS):
            for tok in grp:
                allowed.add(tok.lower())
                allowed.add(_strip_accents(tok.lower()))

        # Expand every user word entry
        for entry in all_words:
            allowed.update(_expand_word_forms(entry))

        stems = _build_stem_set(allowed)
        return allowed, stems

    def _sentence_has_unknown_words(
        self,
        sentence: str,
        allowed_tokens: set[str],
        allowed_stems: set[str],
    ) -> list[str]:
        """
        Return a list of tokens in the sentence that are NOT in `allowed_tokens`.
        Also accepts tokens whose 5-char prefix matches a known stem (handles
        Greek conjugation/declension).
        Empty list means the sentence is clean.
        """
        unknown = []
        for token in _tokenize_sentence(sentence):
            if not token:
                continue
            # Exact match
            if token in allowed_tokens:
                continue
            stripped = _strip_accents(token)
            if stripped in allowed_tokens:
                continue
            # Stem/prefix match (handles conjugated forms)
            if len(token) >= _MIN_STEM_LEN and token[:_MIN_STEM_LEN] in allowed_stems:
                continue
            if len(stripped) >= _MIN_STEM_LEN and stripped[:_MIN_STEM_LEN] in allowed_stems:
                continue
            unknown.append(token)
        return unknown

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def generate_system_prompt(
        self,
        all_words: List[str],
        plural: bool = True,
        tenses: List[str] = None,
        personal_pronouns: bool = True,
        possessive_pronouns: bool = True,
        prepositions: bool = True,
        interrogative_words: bool = True,
    ) -> str:
        """
        Generate a system prompt that strictly limits the AI to the provided word list.

        `all_words` must be the COMPLETE flat list of words the user knows
        (mandatory + general combined).  The system prompt enumerates them
        explicitly so the model cannot use any other content words.
        """
        if tenses is None:
            tenses = ["present", "past", "future"]

        # --- Tenses (with explicit Greek examples) ---
        tense_blocks = []
        if len(tenses) < 3:
            forbidden_tenses = []
            if "future" in tenses:
                tense_blocks.append(
                    "✅ FUTURE TENSE (Μέλλοντας): You MUST use 'θα' + verb.\n"
                    "   Examples: θα πάω, θα κάνω, θα δω, θα μάθω, θα γράψω.\n"
                    "   EVERY verb in the sentence MUST have 'θα' before it."
                )
            if "past" in tenses:
                tense_blocks.append(
                    "✅ PAST TENSE (Αόριστος/Παρατατικός): You MUST use past verb forms.\n"
                    "   Aorist examples: πήγα, έκανα, είδα, έμαθα, έγραψα, διάβασα, ήρθα.\n"
                    "   Imperfect examples: πήγαινα, έκανα, έβλεπα, ήθελα, έγραφα.\n"
                    "   Past of είμαι: ήμουν, ήσουν, ήταν, ήμαστε, ήσαστε.\n"
                    "   NEVER use present-tense endings (-ω, -εις, -ει, -ουμε, -ετε, -ουν) for verbs."
                )
            if "present" in tenses:
                tense_blocks.append(
                    "✅ PRESENT TENSE (Ενεστώτας): Use present verb forms.\n"
                    "   Examples: πηγαίνω, κάνω, βλέπω, θέλω, γράφω, μαθαίνω."
                )

            # Explicitly list FORBIDDEN tenses
            if "future" not in tenses:
                forbidden_tenses.append("❌ FUTURE TENSE IS FORBIDDEN — do NOT use 'θα' before any verb.")
            if "past" not in tenses:
                forbidden_tenses.append("❌ PAST TENSE IS FORBIDDEN — do NOT use aorist/imperfect verb forms (πήγα, έκανα, etc.).")
            if "present" not in tenses:
                forbidden_tenses.append("❌ PRESENT TENSE IS FORBIDDEN — do NOT use present endings (-ω, -εις, -ει, -ουμε, -ετε, -ουν).")

            tense_instruction = "\n".join(tense_blocks)
            if forbidden_tenses:
                tense_instruction += "\n" + "\n".join(forbidden_tenses)
        else:
            tense_instruction = "- All tenses (present, past, future) are allowed."

        # --- Number ---
        if not plural:
            plural_instruction = (
                "- STRICTLY singular forms ONLY. No plural nouns, adjectives, or verbs.\n"
                "  Do NOT use plural articles: οι, τα (as plural). Use only: ο, η, το, τον, την."
            )
        else:
            plural_instruction = "- Both singular and plural are allowed."

        # --- Extra restrictions (explicit forbidden word lists) ---
        extras = []
        if not personal_pronouns:
            extras.append(
                "❌ PERSONAL PRONOUNS ARE FORBIDDEN. Do NOT use any of these words:\n"
                "   εγώ, εσύ, αυτός, αυτή, αυτό, εμείς, εσείς, αυτοί, αυτές, αυτά\n"
                "   None of these words may appear in the sentence."
            )
        if not possessive_pronouns:
            extras.append(
                "❌ POSSESSIVE PRONOUNS ARE FORBIDDEN. Do NOT use any of these words:\n"
                "   μου, σου, του, της, μας, σας, τους\n"
                "   Example: say 'η μαμά' NOT 'η μαμά μου'. No possessives at all."
            )
        if not prepositions:
            extras.append(
                "❌ PREPOSITIONS ARE FORBIDDEN. Do NOT use any of these words:\n"
                "   με, για, από, σε, στο, στη, στην, στον, στους, στις, στα, πριν, μετά, κατά, μέχρι, χωρίς\n"
                "   Build sentences without any prepositional phrases.\n"
                "   Example: say 'Πηγαίνω, βλέπω το μουσείο' NOT 'Πηγαίνω στο μουσείο'."
            )
        if not interrogative_words:
            extras.append(
                "❌ INTERROGATIVE WORDS ARE FORBIDDEN. Do NOT use any of these words:\n"
                "   τι, ποιος, ποια, ποιο, πού, πότε, πώς, γιατί, πόσο, πόσα, μήπως\n"
                "   Do NOT create questions. Only declarative/affirmative sentences."
            )

        extra_block = ""
        for e in extras:
            extra_block += f"{e}\n"

        # --- Word list ---
        word_flat = ", ".join(all_words)

        # --- Build dynamic "freely use" section ---
        freely_use_lines = [
            "  • Articles:      ο, η, το, τα, τον, την, του, της, των, τους, τις",
            "  • The verb είναι in any form: είμαι, είσαι, είναι, είμαστε, είστε, ήταν, ήμουν",
            "  • Short conjunctions: και, ή, αλλά, ότι, που, αν, όταν, ενώ, επειδή",
            "  • Negation and modals: δεν, μην, να, θα",
            "  • Basic filler words: πολύ, λίγο, κάθε",
        ]
        if personal_pronouns:
            freely_use_lines.append(
                "  • Personal pronouns: εγώ, εσύ, αυτός, αυτή, αυτό, εμείς, εσείς, αυτοί, αυτές, αυτά"
            )
        if possessive_pronouns:
            freely_use_lines.append(
                "  • Possessive short forms: μου, σου, του, της, μας, σας, τους"
            )
        if prepositions:
            freely_use_lines.append(
                "  • Prepositions: με, για, από, σε, στο, στη, στην, στον, στους, στις, στα"
            )
        if interrogative_words:
            freely_use_lines.append(
                "  • Interrogative words: τι, ποιος, ποια, πού, πότε, πώς, γιατί, πόσο"
            )
        freely_use_block = "\n".join(freely_use_lines)

        return f"""You are a strict Greek language teacher creating educational sentences.

═══════════════════════════════════════════════════════════
ABSOLUTE VOCABULARY RULE  — READ CAREFULLY
═══════════════════════════════════════════════════════════
You may ONLY use the following words as content words
(nouns, verbs other than είναι, adjectives, adverbs):

[ {word_flat} ]

You may ALSO freely use:
{freely_use_block}

ANY other noun, verb, adjective, or adverb NOT in the word list above is STRICTLY FORBIDDEN.
Do NOT add extra content words even if they make the sentence more natural.
═══════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════
GRAMMAR AND SETTINGS RULES (MUST FOLLOW EXACTLY)
═══════════════════════════════════════════════════════════
{plural_instruction}
{tense_instruction}
{extra_block.rstrip()}
═══════════════════════════════════════════════════════════

- Word forms may change (case, number, tense) but the ROOT must match a word in the list.
- Your answer MUST be valid JSON. No markdown, no prose.
- FOLLOW ALL RULES WITHOUT EXCEPTION."""

    def _create_user_prompt(
        self, mandatory_words: List[str], difficulty: int,
        tenses: List[str] = None,
    ) -> tuple[str, str]:
        """Create user prompt for sentence generation."""
        if tenses is None:
            tenses = ["present", "past", "future"]

        word_count_map = {
            1: (3, 5),
            2: (6, 9),
            3: (10, 15),
        }
        min_words, max_words = word_count_map.get(difficulty, (3, 5))

        if difficulty == 1:
            instruction = "Create ONE simple, short, natural Greek sentence."
            complexity_note = "- Must be a simple sentence suitable for beginners."
        elif difficulty == 2:
            instruction = "Create ONE complete and natural Greek sentence."
            complexity_note = "- Must be a medium-complexity sentence."
        else:
            instruction = "Create ONE complete, longer and natural Greek sentence."
            complexity_note = "- Must be a grammatically rich sentence with details."

        # Build tense-specific reminder for the user prompt
        tense_reminder = ""
        if len(tenses) == 1:
            if tenses[0] == "future":
                tense_reminder = (
                    "\n⚠️ TENSE: FUTURE ONLY — Every verb MUST have 'θα' before it. "
                    "Example: 'Θα πάω στο μαγαζί' NOT 'Πηγαίνω στο μαγαζί'."
                )
            elif tenses[0] == "past":
                tense_reminder = (
                    "\n⚠️ TENSE: PAST ONLY — Use ONLY past tense verb forms (aorist/imperfect). "
                    "Example: 'Πήγα στο μαγαζί' NOT 'Πηγαίνω στο μαγαζί'. "
                    "Use forms like: πήγα, έκανα, είδα, έμαθα, έγραψα, διάβασα, ήθελα."
                )
            elif tenses[0] == "present":
                tense_reminder = (
                    "\n⚠️ TENSE: PRESENT ONLY — Use ONLY present tense. "
                    "No θα, no past forms."
                )
        elif len(tenses) == 2:
            if "future" not in tenses:
                tense_reminder = "\n⚠️ No future tense — do NOT use 'θα'."
            elif "past" not in tenses:
                tense_reminder = "\n⚠️ No past tense — do NOT use aorist/imperfect forms."

        mandatory_list = ", ".join(mandatory_words)

        prompt = f"""{instruction}

MANDATORY WORDS (use AT LEAST ONE, ideally all):
{mandatory_list}

REQUIREMENTS:
- Length: EXACTLY {min_words} to {max_words} words. MUST contain at least {min_words} words.
{complexity_note}
- Use ONLY words from the VOCABULARY LIST in the system prompt + allowed filler.
- Do NOT add content words not in the vocabulary list.{tense_reminder}
{{retry_hint}}

RESPONSE FORMAT (strict JSON, no markdown):
{{
  "greek": "full Greek sentence",
  "russian": "Russian translation of the sentence",
  "used_greek_words": ["word1", "word2"]
}}"""
        return prompt, ""

    # ------------------------------------------------------------------
    # Main generation method
    # ------------------------------------------------------------------

    async def generate_sentence(
        self,
        review_words: List[str],
        general_words: List[str],
        difficulty: int,
        system_prompt: Optional[str] = None,
        plural: bool = True,
        tenses: List[str] = None,
        personal_pronouns: bool = True,
        possessive_pronouns: bool = True,
        prepositions: bool = True,
        interrogative_words: bool = True,
        # Full word list used for strict token validation.
        # Pass all user words here; if omitted, review + general are used.
        all_user_words: Optional[List[str]] = None,
    ) -> Optional[Dict[str, any]]:
        """
        Generate a Greek sentence that uses ONLY words from the user's word list.

        Args:
            review_words:   Mandatory words to use (highest priority).
            general_words:  All other words the user knows (for context/fillers).
            difficulty:     1 (easy/3-5 words) | 2 (medium/6-9) | 3 (hard/10-15).
            system_prompt:  Pre-built cached system prompt.  When provided,
                            `all_user_words` is required for validation.
            all_user_words: Complete flat word list (review + general) used to
                            validate that the generated sentence stays on-dict.
        """
        if tenses is None:
            tenses = ["present", "past", "future"]

        if not review_words and not general_words and not system_prompt:
            logger.error("No words provided for sentence generation")
            return None

        # Prompt context words
        prompt_words = list(review_words) + [
            w for w in general_words if w not in review_words
        ]
        
        # Word list for strict validation
        validation_words = all_user_words if all_user_words else prompt_words

        # Build or use cached system prompt
        if not system_prompt:
            system_prompt = self.generate_system_prompt(
                all_words=prompt_words,
                plural=plural,
                tenses=tenses,
                personal_pronouns=personal_pronouns,
                possessive_pronouns=possessive_pronouns,
                prepositions=prepositions,
                interrogative_words=interrogative_words,
            )

        # Pre-compute allowed token set once (Python-side validation)
        allowed_tokens, allowed_stems = self._build_allowed_tokens(validation_words)

        prompt_template, _ = self._create_user_prompt(review_words, difficulty, tenses=tenses)
        word_count_map = {1: (3, 5), 2: (6, 9), 3: (10, 15)}
        min_w, max_w = word_count_map.get(difficulty, (3, 5))

        temperatures = [0.3, 0.5, 0.8]
        self.max_retries = len(temperatures)
        best_fallback: Optional[Dict] = None   # best sentence even if imperfect
        best_fallback_violations: int = 999     # track severity for fallback selection
        best_fallback_distance: int = 999       # distance of word count to target range
        retry_hint_text = ""

        def _word_count_distance(wc: int) -> int:
            """Return 0 when wc is inside [min_w, max_w], else the distance to the nearest boundary."""
            if wc < min_w:
                return min_w - wc
            if wc > max_w:
                return wc - max_w
            return 0

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Generating sentence (attempt {attempt + 1}/{self.max_retries}), "
                    f"difficulty={difficulty}, tenses={tenses}"
                )

                prompt = prompt_template.replace("{retry_hint}", retry_hint_text)
                logger.debug(f"User prompt:\n{prompt}")
                logger.debug(f"Mandatory words: {review_words}")
                logger.debug(f"All user words count: {len(validation_words)}")

                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=temperatures[attempt],
                    max_tokens=500,
                )

                content = response.choices[0].message.content or ""
                logger.debug(f"Raw AI response: {content}")

                cleaned = self._clean_json_response(content)
                if not cleaned:
                    logger.warning(f"Empty/no JSON on attempt {attempt + 1}")
                    continue

                result = json.loads(cleaned)

                if "greek" not in result or "russian" not in result:
                    logger.warning(
                        f"Missing 'greek'/'russian' key on attempt {attempt + 1}"
                    )
                    continue

                greek_sentence = result["greek"].strip()
                russian_translation = result["russian"].strip()
                used_words_raw = result.get("used_greek_words", [])

                if not greek_sentence or not russian_translation:
                    continue

                word_count = len(greek_sentence.split())

                # --- Check 1: too short → retry ---
                if word_count < min_w:
                    logger.warning(
                        f"Sentence too short ({word_count} < {min_w}): {greek_sentence}"
                    )
                    dist = _word_count_distance(word_count)
                    if dist < best_fallback_distance:
                        best_fallback_distance = dist
                        best_fallback = {
                            "greek": greek_sentence,
                            "russian": russian_translation,
                            "used_greek_words": used_words_raw,
                        }
                    retry_hint_text = (
                        f"\n> IMPORTANT: The previous attempt produced only {word_count} words. "
                        f"Add more detail to reach at least {min_w} words."
                    )
                    continue

                # --- Check 2: too long → retry ---
                if word_count > max_w:
                    logger.warning(
                        f"Sentence too long ({word_count} > {max_w}): {greek_sentence}"
                    )
                    dist = _word_count_distance(word_count)
                    if dist < best_fallback_distance:
                        best_fallback_distance = dist
                        best_fallback = {
                            "greek": greek_sentence,
                            "russian": russian_translation,
                            "used_greek_words": used_words_raw,
                        }
                    retry_hint_text = (
                        f"\n> IMPORTANT: The previous attempt produced {word_count} words. "
                        f"Make it shorter: EXACTLY {min_w}–{max_w} words."
                    )
                    continue

                # --- Check 3: unknown words → retry (STRICT) ---
                unknown = self._sentence_has_unknown_words(greek_sentence, allowed_tokens, allowed_stems)
                if unknown:
                    logger.warning(
                        f"Sentence contains words NOT in the user's list: {unknown}. "
                        f"Sentence: '{greek_sentence}'"
                    )
                    violation_count = len(unknown)
                    dist = _word_count_distance(word_count)
                    if (violation_count < best_fallback_violations
                            or (violation_count == best_fallback_violations and dist < best_fallback_distance)
                            or best_fallback is None):
                        best_fallback_violations = violation_count
                        best_fallback_distance = dist
                        best_fallback = {
                            "greek": greek_sentence,
                            "russian": russian_translation,
                            "used_greek_words": used_words_raw,
                            "_unknown_words": unknown,
                        }
                    retry_hint_text = (
                        f"\n> IMPORTANT: The previous attempt used words NOT in the vocabulary list: "
                        f"{', '.join(unknown)}. "
                        f"Replace them with words from the vocabulary list ONLY."
                    )
                    continue

                # --- Check 4: settings violations → retry ---
                settings_issues = self._check_settings_violations(
                    greek_sentence, tenses=tenses, plural=plural,
                    personal_pronouns=personal_pronouns,
                    possessive_pronouns=possessive_pronouns,
                    prepositions=prepositions,
                    interrogative_words=interrogative_words,
                )
                if settings_issues:
                    issues_str = "; ".join(settings_issues)
                    logger.warning(
                        f"Sentence violates settings: {issues_str}. "
                        f"Sentence: '{greek_sentence}'"
                    )
                    violation_count = len(settings_issues)
                    dist = _word_count_distance(word_count)
                    if (violation_count < best_fallback_violations
                            or (violation_count == best_fallback_violations and dist < best_fallback_distance)
                            or best_fallback is None):
                        best_fallback_violations = violation_count
                        best_fallback_distance = dist
                        best_fallback = {
                            "greek": greek_sentence,
                            "russian": russian_translation,
                            "used_greek_words": used_words_raw,
                        }
                    retry_hint_text = (
                        f"\n> CRITICAL ERROR: The sentence violates these rules: {issues_str}. "
                        f"You MUST fix all of these issues. Re-read the grammar rules carefully."
                    )
                    continue

                # --- All checks passed ---
                logger.info(f"Sentence OK ({word_count} words): {greek_sentence}")
                return {
                    "greek": greek_sentence,
                    "russian": russian_translation,
                    "used_greek_words": used_words_raw,
                }

            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Error on attempt {attempt + 1}: {e}")

        # Return best fallback with warning
        if best_fallback:
            unknown_in_fb = best_fallback.pop("_unknown_words", [])
            logger.warning(
                f"All {self.max_retries} attempts failed checks. "
                f"Returning best fallback: '{best_fallback['greek']}'"
                + (f" (unknown words: {unknown_in_fb})" if unknown_in_fb else "")
            )
            return best_fallback

        logger.error("Failed to generate a sentence after all retries")
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    # --- Token sets for post-validation ---
    _PERSONAL_PRONOUNS = {
        "εγώ", "εγω", "εσύ", "εσυ",
        "αυτός", "αυτος", "αυτή", "αυτη", "αυτό", "αυτο",
        "εμείς", "εμεις", "εσείς", "εσεις",
        "αυτοί", "αυτοι", "αυτές", "αυτες", "αυτά", "αυτα",
    }
    _POSSESSIVE_PRONOUNS = {"μου", "σου", "του", "της", "μας", "σας", "τους"}
    _PREPOSITIONS = {
        "με", "για", "από", "απο", "σε",
        "στο", "στη", "στην", "στον", "στους", "στις", "στα",
        "πριν", "μετά", "μετα", "κατά", "κατα",
        "μέχρι", "μεχρι", "χωρίς", "χωρις",
    }
    _INTERROGATIVE_WORDS = {
        "τι", "τί", "ποιος", "ποια", "ποιο", "ποιοι", "ποιες",
        "πού", "πότε", "ποτε", "πώς", "πως",
        "πόσο", "ποσο", "πόσα", "ποσα", "πόσοι", "ποσοι", "πόσες", "ποσες",
        "μήπως", "μηπως",
    }
    _PLURAL_ARTICLES = {"οι", "τα", "τις", "τους", "των"}

    # Past-tense verb suffixes (aorist / imperfect)
    _PAST_SUFFIXES = [
        # Aorist active
        "σα", "σες", "σε", "σαμε", "σατε", "σαν",
        "ξα", "ξες", "ξε", "ξαμε", "ξατε", "ξαν",
        "ψα", "ψες", "ψε", "ψαμε", "ψατε", "ψαν",
        # Imperfect
        "ουσα", "ουσες", "ουσε", "ουσαμε", "ουσατε", "ουσαν",
        "αγα", "αγες", "αγε", "αγαμε", "αγατε", "αγαν",
        # Aorist passive-like
        "ηκα", "ηκες", "ηκε", "ηκαμε", "ηκατε", "ηκαν",
        "θηκα", "θηκες", "θηκε", "θηκαμε", "θηκατε", "θηκαν",
        # Imperfect -αινα pattern (e.g., πήγαινα)
        "αινα", "αινες", "αινε",
    ]
    _PAST_MARKERS = {
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

    def _check_settings_violations(
        self,
        sentence: str,
        tenses: List[str],
        plural: bool,
        personal_pronouns: bool,
        possessive_pronouns: bool,
        prepositions: bool,
        interrogative_words: bool,
    ) -> List[str]:
        """
        Check a generated sentence against the user's settings.
        Returns a list of violation descriptions (empty = OK).
        """
        issues = []
        tokens = _tokenize_sentence(sentence)
        tokens_stripped = [_strip_accents(t) for t in tokens]

        # --- Tense checks ---
        has_tha = "θα" in tokens or "θα" in tokens_stripped
        has_past_marker = any(
            t in self._PAST_MARKERS or _strip_accents(t) in {_strip_accents(m) for m in self._PAST_MARKERS}
            for t in tokens
        )
        has_past_suffix = any(
            any(_strip_accents(t).endswith(suf) for suf in self._PAST_SUFFIXES)
            for t in tokens if len(t) > 3  # avoid matching tiny words
        )
        has_past = has_past_marker or has_past_suffix

        if "future" not in tenses and has_tha:
            issues.append("FUTURE FORBIDDEN but 'θα' is present")

        if "future" in tenses and len(tenses) == 1 and not has_tha:
            issues.append("FUTURE ONLY but 'θα' is missing")

        if "past" not in tenses and has_past:
            issues.append("PAST FORBIDDEN but past-tense forms detected")

        if "past" in tenses and len(tenses) == 1 and not has_past:
            issues.append("PAST ONLY but no past-tense forms detected")

        # --- Plural check ---
        if not plural:
            found_plural = [t for t in tokens if t in self._PLURAL_ARTICLES]
            if found_plural:
                issues.append(f"PLURAL FORBIDDEN but plural articles found: {found_plural}")

        # --- Personal pronouns check ---
        if not personal_pronouns:
            found = [t for t in tokens if t in self._PERSONAL_PRONOUNS
                     or _strip_accents(t) in {_strip_accents(p) for p in self._PERSONAL_PRONOUNS}]
            if found:
                issues.append(f"PERSONAL PRONOUNS FORBIDDEN but found: {found}")

        # --- Possessive pronouns check ---
        if not possessive_pronouns:
            found = [t for t in tokens if t in self._POSSESSIVE_PRONOUNS]
            if found:
                issues.append(f"POSSESSIVE PRONOUNS FORBIDDEN but found: {found}")

        # --- Prepositions check ---
        if not prepositions:
            found = [t for t in tokens if t in self._PREPOSITIONS
                     or _strip_accents(t) in {_strip_accents(p) for p in self._PREPOSITIONS}]
            if found:
                issues.append(f"PREPOSITIONS FORBIDDEN but found: {found}")

        # --- Interrogative words check ---
        if not interrogative_words:
            found = [t for t in tokens if t in self._INTERROGATIVE_WORDS
                     or _strip_accents(t) in {_strip_accents(q) for q in self._INTERROGATIVE_WORDS}]
            if found:
                issues.append(f"INTERROGATIVE WORDS FORBIDDEN but found: {found}")
            if ";" in sentence or "?" in sentence:
                issues.append("QUESTIONS FORBIDDEN but sentence is a question")

        return issues


    def _clean_json_response(self, text: str) -> str:
        """Strip markdown fences and return the inner JSON string."""
        if not text:
            return ""
        # Remove ```json ... ``` or ``` ... ```
        text = re.sub(r"```(?:json)?\s*(.*?)\s*```", r"\1", text, flags=re.DOTALL)
        text = text.strip()
        if not (text.startswith("{") and text.endswith("}")):
            match = re.search(r"(\{.*\})", text, re.DOTALL)
            if match:
                text = match.group(1)
        return text

    # Keep legacy method name for backward compatibility
    def _extract_word_forms(self, words: List[str]) -> set:
        """Legacy helper – use _expand_word_forms instead."""
        forms = set()
        for entry in words:
            forms.update(_expand_word_forms(entry))
        return forms

    def _validate_used_words(
        self, used_words: List[str], review_words: List[str], general_words: List[str]
    ) -> list:
        """Legacy method kept for backward compatibility."""
        allowed = self._build_allowed_tokens(review_words + general_words)
        return [
            w for w in used_words
            if w.strip().lower() not in allowed
            and _strip_accents(w.strip().lower()) not in allowed
        ]
