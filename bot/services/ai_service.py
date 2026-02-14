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
    
    def _create_prompt(self, words: List[str], difficulty: int) -> str:
        """
        Create prompt for sentence generation.
        
        Args:
            words: List of Greek words to use
            difficulty: Difficulty level (1=easy, 2=medium, 3=hard)
            
        Returns:
            Formatted prompt string
        """
        word_count_map = {
            1: (4, 10),
            2: (7, 15),
            3: (12, 25)
        }
        min_words, max_words = word_count_map.get(difficulty, (4, 10))
        
        word_list = ", ".join(words)
        
        prompt = f"""Составь ОДНО полноценное, длинное и естественное предложение на греческом языке.

**ОСНОВНЫЕ СЛОВА ДЛЯ ПРЕДЛОЖЕНИЯ:**
{word_list}

**ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:**
1. Длина предложения: СТРОГО ОТ {min_words} ДО {max_words} слов.
2. Это должно быть ПОЛНОЕ ПРЕДЛОЖЕНИЕ со смыслом (развернутая мысль), а не просто фраза из двух слов.
3. Используй слова из списка выше как основу (можно менять их формы: падеж, число, время глагола).
4. ОБЯЗАТЕЛЬНО добавляй артикли, предлоги, союзы и другие связующие слова (π.χ. γιατί, όταν, μετά...).
5. Даже если в списке мало слов, придумай контекст вокруг них, чтобы предложение было интересным и полезным для обучения.

**ФОРМАТ ОТВЕТА (строго JSON):**
{{
  "greek": "полное греческое предложение",
  "russian": "перевод всего предложения на русский"
}}"""
        
        return prompt
    
    async def generate_sentence(
        self,
        words: List[str],
        difficulty: int
    ) -> Optional[Dict[str, str]]:
        """
        Generate a sentence using given words.
        
        Args:
            words: List of Greek words to use
            difficulty: Difficulty level (1-3)
            
        Returns:
            Dictionary with 'greek' and 'russian' keys or None if failed
        """
        if not words:
            logger.error("No words provided for sentence generation")
            return None
        
        prompt = self._create_prompt(words, difficulty)
        system_prompt = "Ты - опытный лингвист и преподаватель греческого. Ты умеешь составлять глубокие, грамматически богатые предложения (с использованием придаточных предложений, союзов и артиклей), используя заданный набор слов. Твои ответы всегда в формате JSON."
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Generating sentence (attempt {attempt + 1}/{self.max_retries}) using words: {words}")
                
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
                        if word_count < 3:
                            logger.warning(f"AI returned too short sentence ({word_count} words), retrying: {greek_sentence}")
                            continue

                        logger.info(f"Successfully generated sentence: {greek_sentence}")
                        return {
                            "greek": greek_sentence,
                            "russian": russian_translation
                        }
                
                logger.warning(f"Invalid response format or too short on attempt {attempt + 1}")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Error generating sentence on attempt {attempt + 1}: {e}")
        
        logger.error("Failed to generate sentence after all retries")
        return None
