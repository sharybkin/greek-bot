"""
Groq AI service for sentence generation.
"""

import json
from typing import List, Dict, Optional
from groq import Groq
from bot.config import config
from bot.utils.logger import logger


class AIService:
    """Service for AI-powered sentence generation using Groq API."""
    
    def __init__(self):
        """Initialize Groq client."""
        self.client = Groq(api_key=config.groq_api_key)
        self.model = "llama-3.3-70b-versatile"
        self.max_retries = 3
    
    def _create_prompt(
        self, 
        review_words: List[str], 
        general_words: List[str], 
        difficulty: int, 
        plural: bool = True, 
        tenses: List[str] = None,
        personal_pronouns: bool = True,
        possessive_pronouns: bool = True,
        prepositions: bool = True,
        interrogative_words: bool = True
    ) -> str:
        """
        Create prompt for sentence generation.
        
        Args:
            review_words: List of mandatory Greek words (must be used)
            general_words: List of optional Greek words (can be used)
            difficulty: Difficulty level (1=easy, 2=medium, 3=hard)
            plural: Whether plural is enabled
            tenses: List of allowed tenses (present, past, future)
            personal_pronouns: Whether personal pronouns are enabled
            possessive_pronouns: Whether possessive pronouns are enabled
            prepositions: Whether prepositions are enabled
            interrogative_words: Whether interrogative words are enabled
            
        Returns:
            Formatted prompt string
        """
        if tenses is None:
            tenses = ["present", "past", "future"]
            
        word_count_map = {
            1: (3, 5),
            2: (6, 9),
            3: (10, 15)
        }
        min_words, max_words = word_count_map.get(difficulty, (3, 5))
        
        if difficulty == 1:
            instruction = "Create ONE simple, short, and natural sentence in Greek."
            complexity_note = "- Must be a simple sentence, suitable for beginners."
        elif difficulty == 2:
            instruction = "Create ONE complete and natural sentence in Greek."
            complexity_note = "- Must be a sentence of medium complexity."
        else:
            instruction = "Create ONE complete, long, and natural sentence in Greek."
            complexity_note = "- Must be a grammatically rich sentence (detailed thought)."

        # Settings Logic
        plural_instruction = ""
        if not plural:
            plural_instruction = "- CRITICAL: NO plurals. Use ONLY singular form for nouns, adjectives, and verbs."
        else:
            plural_instruction = "- Plural and singular forms are both allowed."
            
        tense_instruction = ""
        allowed_tenses = []
        if "present" in tenses:
            allowed_tenses.append("Present")
        if "past" in tenses:
            allowed_tenses.append("Past")
        if "future" in tenses:
            allowed_tenses.append("Future")
            
        if len(allowed_tenses) < 3:
            tenses_str = " OR ".join(allowed_tenses)
            tense_instruction = f"- CRITICAL: Use ONLY these tenses: {tenses_str}. Other verb tenses are FORBIDDEN."
        else:
            tense_instruction = "- All verb tenses allowed (Present, Past, Future)."

        extra_instructions = []
        if not personal_pronouns:
            extra_instructions.append("NO personal pronouns (εγώ, εσύ, αυτός, etc.).")
        if not possessive_pronouns:
            extra_instructions.append("NO possessive pronouns (μου, σου, etc.).")
        if not prepositions:
            extra_instructions.append("NO prepositions.")
        if not interrogative_words:
            extra_instructions.append("NO questions or interrogative words.")
        
        extra_instr_str = ""
        for instr in extra_instructions:
            extra_instr_str += f"- IMPORTANT: {instr}\n"

        # Using space separation to compress tokens
        review_list = " ".join(review_words)
        general_list = " ".join(general_words)

        retry_hint = ""

        prompt = f"""{instruction}

**MANDATORY WORDS (use at least one, preferably all):**
{review_list}

**ADDITIONAL WORDS (can use for context):**
{general_list}

**REQUIREMENTS:**
- Length: STRICTLY {min_words} to {max_words} words.
{complexity_note}
- Try using MANDATORY WORDS. Use ADDITIONAL WORDS as needed.
- Word forms can be changed (case, number, tense).
- Free to add articles (ο/η/το/τα), prepositions (σε/από/με/για/στο), conjunctions (και/ή/αλλά/που/ότι), and auxiliary verbs (είναι/έχω/θα/δεν).
- Provide a suitable learning context.
{{retry_hint}}
{plural_instruction}
{tense_instruction}
{extra_instr_str.rstrip()}

**RESPONSE FORMAT (strict JSON):**
{{
  "greek": "full Greek sentence",
  "russian": "Russian translation of the sentence",
  "used_greek_words": ["word1", "word2"]
}}"""
        return prompt, retry_hint


    def _extract_word_forms(self, words: List[str]) -> set:
        """
        Build a set of all lowercase tokens derived from the provided word list.
        Handles entries like 'περίμενε / περιμένετε' or 'ο / η κτηνίατρος'.
        """
        import re
        forms = set()
        for entry in words:
            parts = re.split(r"[/,]", entry)
            for part in parts:
                token = part.strip().lower()
                token = re.sub(r"\s*\(.*?\)", "", token).strip()
                if token:
                    forms.add(token)
        return forms

    def _validate_used_words(
        self, used_words: List[str], review_words: List[str], general_words: List[str]
    ) -> list:
        """
        Check that every word AI reports as 'used' is present in the provided lists.
        Returns a list of words that are NOT in the provided lists (empty → OK).
        """
        allowed = self._extract_word_forms(review_words + general_words)
        return [
            w for w in used_words
            if w.strip().lower() not in allowed
        ]
    async def generate_sentence(
        self,
        review_words: List[str],
        general_words: List[str],
        difficulty: int,
        plural: bool = True,
        tenses: List[str] = None,
        personal_pronouns: bool = True,
        possessive_pronouns: bool = True,
        prepositions: bool = True,
        interrogative_words: bool = True
    ) -> Optional[Dict[str, any]]:
        """
        Generate a sentence using given words.
        
        Args:
            review_words: List of mandatory Greek words
            general_words: List of optional Greek words
            difficulty: Difficulty level (1-3)
            plural: Whether plural is enabled
            tenses: List of allowed tenses
            
        Returns:
            Dictionary with 'greek', 'russian', and 'used_greek_words' keys or None if failed
        """
        if tenses is None:
            tenses = ["present", "past", "future"]
            
        if not review_words and not general_words:
            logger.error("No words provided for sentence generation")
            return None

        prompt_template, _ = self._create_prompt(
            review_words,
            general_words,
            difficulty,
            plural,
            tenses,
            personal_pronouns,
            possessive_pronouns,
            prepositions,
            interrogative_words
        )
        system_prompt = "You are an expert linguist and Greek language teacher. You create natural, grammatically rich sentences using a given set of words. Your responses are always in strict JSON format."
        
        temperatures = [0.8, 1.0, 1.2]
        longest_fallback = None  # best result seen even if it didn't pass all checks
        longest_fallback_wc = -1
        retry_hint_text = ""

        for attempt in range(self.max_retries):
            try:
                logger.info(f"Generating sentence (attempt {attempt + 1}/{self.max_retries})")
                logger.info(f"Tenses passed to AI: {tenses}")

                # Inject retry feedback into the prompt
                prompt = prompt_template.replace("{retry_hint}", retry_hint_text)

                logger.debug(f"Full Prompt: {prompt}")
                logger.debug(f"Review words: {review_words}, General words: {general_words}")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temperatures[attempt],
                    max_tokens=500,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                logger.debug(f"AI Response content: {content}")
                result = json.loads(content)
                
                # Validate response
                if "greek" in result and "russian" in result:
                    greek_sentence = result["greek"].strip()
                    russian_translation = result["russian"].strip()
                    used_words_raw = result.get("used_greek_words", [])
                    
                    if greek_sentence and russian_translation:
                        word_count = len(greek_sentence.split())
                        
                        # Get boundaries for validation
                        word_count_map = {1: (3, 5), 2: (6, 9), 3: (10, 15)}
                        min_w, max_w = word_count_map.get(difficulty, (3, 5))

                        # --- Check 1: word count ---
                        length_ok = min_w <= word_count <= max_w
                        if not length_ok:
                            logger.warning(
                                f"AI returned sentence with wrong length ({word_count} words, expected {min_w}-{max_w}), "
                                f"retrying: {greek_sentence}"
                            )
                            # Keep the longest sentence as fallback
                            if word_count > longest_fallback_wc:
                                longest_fallback_wc = word_count
                                longest_fallback = {
                                    "greek": greek_sentence,
                                    "russian": russian_translation,
                                    "used_greek_words": used_words_raw
                                }
                            retry_hint_text = (
                                f"\n> IMPORTANT: Previous attempt produced {word_count} words instead of {min_w}-{max_w}. "
                                "Add a subordinate clause, time/place expressions, or an additional object."
                            )
                            continue

                        # --- Check 2: used words must be from the provided lists ---
                        invalid_words = self._validate_used_words(
                            used_words_raw, review_words, general_words
                        )
                        if invalid_words:
                            logger.warning(
                                f"AI used words NOT in the provided lists: {invalid_words}. "
                                f"Sentence: '{greek_sentence}'. Retrying."
                            )
                            # Still store as fallback (length is fine)
                            if word_count > longest_fallback_wc:
                                longest_fallback_wc = word_count
                                longest_fallback = {
                                    "greek": greek_sentence,
                                    "russian": russian_translation,
                                    "used_greek_words": used_words_raw
                                }
                            retry_hint_text = (
                                f"\n> IMPORTANT: In the previous attempt you used words "
                                f"{invalid_words} which are NOT in the provided lists. "
                                "Use ONLY words from the MANDATORY and ADDITIONAL word lists."
                            )
                            continue

                        logger.info(f"Successfully generated sentence: {greek_sentence}")
                        return {
                            "greek": greek_sentence,
                            "russian": russian_translation,
                            "used_greek_words": used_words_raw
                        }
                
                logger.warning(f"Invalid response format or too short on attempt {attempt + 1}")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Error generating sentence on attempt {attempt + 1}: {e}")
        
        if longest_fallback:
            logger.warning(
                f"All retries failed length/word checks. Returning longest sentence as fallback "
                f"({longest_fallback_wc} words): '{longest_fallback['greek']}'"
            )
            return longest_fallback

        logger.error("Failed to generate sentence after all retries")
        return None
