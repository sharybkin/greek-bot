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

        prompt = f"""{instruction}

**ОБЯЗАТЕЛЬНЫЕ СЛОВА (использовать минимум одно, лучше все):**
{review_list}

**ДОПОЛНИТЕЛЬНЫЕ СЛОВА (можно использовать для связности):**
{general_list}

**ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:**
1. Длина предложения: СТРОГО ОТ {min_words} ДО {max_words} слов.
2. {complexity_note}
3. Cтарайтесь использовать ОБЯЗАТЕЛЬНЫЕ СЛОВА. Дополнительные слова используйте по необходимости.
4. Можно менять формы слов (падеж, число, время глагола).
5. Добавляй артикли, предлоги и союзы для связности.
6. Придумай подходящий контекст для слов, чтобы предложение было полезным для обучения.
{plural_instruction}
{tense_instruction}
{extra_instr_str}

**ФОРМАТ ОТВЕТА (строго JSON):**
{{
  "greek": "полное греческое предложение",
  "russian": "перевод всего предложения на русский",
  "used_greek_words": ["слово1", "слово2"]  // Список греческих слов из переданных списков, которые реально были использованы (в их исходной форме из списка)
}}"""
        
        return prompt
    
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
        
        prompt = self._create_prompt(
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
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Generating sentence (attempt {attempt + 1}/{self.max_retries})")
                logger.info(f"Tenses passed to AI: {tenses}")
                logger.debug(f"Full Prompt: {prompt}")
                logger.debug(f"Review words: {review_words}, General words: {general_words}")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.8,
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
                    
                    if greek_sentence and russian_translation:
                        word_count = len(greek_sentence.split())
                        
                        # Get boundaries for validation
                        word_count_map = {1: (3, 5), 2: (6, 9), 3: (10, 15)}
                        min_w, max_w = word_count_map.get(difficulty, (3, 5))
                        
                        if word_count < min_w or word_count > max_w:
                            logger.warning(
                                f"AI returned sentence with wrong length ({word_count} words, expected {min_w}-{max_w}), "
                                f"retrying: {greek_sentence}"
                            )
                            continue

                        logger.info(f"Successfully generated sentence: {greek_sentence}")
                        return {
                            "greek": greek_sentence,
                            "russian": russian_translation,
                            "used_greek_words": result.get("used_greek_words", [])
                        }
                
                logger.warning(f"Invalid response format or too short on attempt {attempt + 1}")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Error generating sentence on attempt {attempt + 1}: {e}")
        
        logger.error("Failed to generate sentence after all retries")
        return None
