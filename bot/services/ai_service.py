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
            instruction = f"Составь ОДНО простое, короткое и естественное предложение на греческом языке."
            complexity_note = "Это должно быть простое предложение, понятное новичку."
        elif difficulty == 2:
            instruction = f"Составь ОДНО полноценное и естественное предложение на греческом языке."
            complexity_note = "Это должно быть предложение средней сложности."
        else:
            instruction = f"Составь ОДНО полноценное, длинное и естественное предложение на греческом языке."
            complexity_note = "Это должно быть грамматически богатое предложение (развернутая мысль)."

        # Settings Logic
        plural_instruction = ""
        if not plural:
            plural_instruction = "7. !КРИТИЧЕСКИ ВАЖНО! ЗАПРЕЩЕНО использовать множественное число. Используй ТОЛЬКО единственное число для всех существительных, прилагательных и глаголов."
        else:
            plural_instruction = "7. Разрешено использовать как единственное, так и множественное число."
            
        tense_instruction = ""
        allowed_tenses = []
        if "present" in tenses:
            allowed_tenses.append("настоящее (Present)")
        if "past" in tenses:
            allowed_tenses.append("прошедшее (Past)")
        if "future" in tenses:
            allowed_tenses.append("будущее (Future)")
            
        if len(allowed_tenses) < 3:
            tenses_str = " ИЛИ ".join(allowed_tenses)
            tense_instruction = f"8. !КРИТИЧЕСКИ ВАЖНО! Используй ТОЛЬКО следующие времена: {tenses_str}. Любое другое время глагола ЗАПРЕЩЕНО."
        else:
            tense_instruction = "8. Разрешено использовать любые времена: настоящее, прошедшее и будущее."

        extra_instructions = []
        if not personal_pronouns:
            extra_instructions.append("ЗАПРЕЩЕНО использовать ЛИЧНЫЕ МЕСТОИМЕНИЯ (я, ты, он и т.д.).")
        if not possessive_pronouns:
            extra_instructions.append("ЗАПРЕЩЕНО использовать ПРИТЯЖАТЕЛЬНЫЕ МЕСТОИМЕНИЯ (мой, твой и т.д.).")
        if not prepositions:
            extra_instructions.append("ЗАПРЕЩЕНО использовать ПРЕДЛОГИ.")
        if not interrogative_words:
            extra_instructions.append("ЗАПРЕЩЕНО составлять вопросительные предложения и использовать ВОПРОСИТЕЛЬНЫЕ СЛОВА.")
        
        extra_instr_str = ""
        for i, instr in enumerate(extra_instructions, 9):
            extra_instr_str += f"{i}. !ВАЖНО! {instr}\n"

        review_list = ", ".join(review_words)
        general_list = ", ".join(general_words)

        retry_hint = ""

        prompt = f"""{instruction}

**ОБЯЗАТЕЛЬНЫЕ СЛОВА (использовать минимум одно, лучше все):**
{review_list}

**ДОПОЛНИТЕЛЬНЫЕ СЛОВА (можно использовать для связности):**
{general_list}

**ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:**
1. Длина предложения: СТРОГО ОТ {min_words} ДО {max_words} слов.
2. {complexity_note}
3. Старайтесь использовать ОБЯЗАТЕЛЬНЫЕ СЛОВА. Дополнительные слова используйте по необходимости.
4. Можно менять формы слов (падеж, число, время глагола).
5. Артикли (ο/η/το/τα и падежные формы), предлоги (σε/από/με/για/στο и т.д.), союзы (και/ή/αλλά/που/ότι и т.д.) и вспомогательные глаголы (είναι/έχω/θα/δεν) добавляй свободно — они не входят в основные списки.
6. Придумай подходящий контекст, чтобы предложение было полезным для обучения.
{{retry_hint}}
{plural_instruction}
{tense_instruction}
{extra_instr_str}

**ФОРМАТ ОТВЕТА (строго JSON):**
{{
  "greek": "полное греческое предложение",
  "russian": "перевод всего предложения на русский",
  "used_greek_words": ["слово1", "слово2"]  // Список слов из переданных списков в их исходной форме из списка
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
        interrogative_words: bool = True,
        general_words_extended: List[str] = None
    ) -> Optional[Dict[str, any]]:
        """
        Generate a sentence using given words.
        
        Args:
            review_words: List of mandatory Greek words
            general_words: List of optional Greek words (used on first attempt)
            difficulty: Difficulty level (1-3)
            plural: Whether plural is enabled
            tenses: List of allowed tenses
            general_words_extended: Larger pool used from attempt 2 onwards (2× general words).
                                    If None, general_words is reused on all retries.
            
        Returns:
            Dictionary with 'greek', 'russian', and 'used_greek_words' keys or None if failed
        """
        if tenses is None:
            tenses = ["present", "past", "future"]
            
        if not review_words and not general_words:
            logger.error("No words provided for sentence generation")
            return None

        # Build per-attempt general word pools
        # attempt 0  → general_words (original size, e.g. 60)
        # attempt 1+ → general_words_extended (double size, e.g. 120) if provided
        extended_pool = general_words_extended if general_words_extended else general_words

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
        system_prompt = "Ты - опытный лингвист и преподаватель греческого. Ты умеешь составлять глубокие, грамматически богатые предложения (с использованием придаточных предложений, союзов и артиклей), используя заданный набор слов. Твои ответы всегда в формате JSON."
        
        temperatures = [0.8, 1.0, 1.2]
        longest_fallback = None  # best result seen even if it didn't pass all checks
        longest_fallback_wc = -1
        retry_hint_text = ""

        for attempt in range(self.max_retries):
            try:
                # On retries (attempt > 0), rebuild the prompt with an extended general word list
                if attempt > 0 and extended_pool is not general_words:
                    prompt_template, _ = self._create_prompt(
                        review_words,
                        extended_pool,
                        difficulty,
                        plural,
                        tenses,
                        personal_pronouns,
                        possessive_pronouns,
                        prepositions,
                        interrogative_words
                    )
                    logger.info(
                        f"Retry {attempt}: expanded general words from {len(general_words)} "
                        f"to {len(extended_pool)}"
                    )

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
                                f"\n> ВАЖНО: Предыдущая попытка дала {word_count} слов, а нужно от {min_w} до {max_w}. "
                                "Добавь придаточное предложение, обстоятельства времени/места/причины или дополнительный объект."
                            )
                            continue

                        # --- Check 2: used words must be from the provided lists ---
                        current_general = extended_pool if attempt > 0 else general_words
                        invalid_words = self._validate_used_words(
                            used_words_raw, review_words, current_general
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
                                f"\n> ВАЖНО: В предыдущей попытке ты указал слова "
                                f"{invalid_words}, которых НЕТ в предоставленных списках. "
                                "Используй ТОЛЬКО слова из списков ОБЯЗАТЕЛЬНЫХ и ДОПОЛНИТЕЛЬНЫХ слов."
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
