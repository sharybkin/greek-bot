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
        self.model = "llama-3.1-70b-versatile"
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
            1: (3, 5),
            2: (6, 9),
            3: (10, 15)
        }
        min_words, max_words = word_count_map.get(difficulty, (3, 5))
        
        word_list = ", ".join(words)
        
        prompt = f"""Ты - учитель греческого языка. Составь ОДНО естественное предложение на греческом языке.

**ОБЯЗАТЕЛЬНЫЕ ТРЕБОВАНИЯ:**
1. Длина предложения: {min_words}-{max_words} слов
2. Используй ТОЛЬКО эти слова (можно изменять формы): {word_list}
3. Предложение должно быть грамматически корректным
4. Предложение должно иметь практический смысл (повседневная ситуация)
5. Не используй слова НЕ из списка

**ФОРМАТ ОТВЕТА (строго JSON):**
{{
  "greek": "греческое предложение",
  "russian": "точный русский перевод"
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
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"Generating sentence (attempt {attempt + 1}/{self.max_retries})")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=300,
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
                result = json.loads(content)
                
                # Validate response
                if "greek" in result and "russian" in result:
                    greek_sentence = result["greek"].strip()
                    russian_translation = result["russian"].strip()
                    
                    if greek_sentence and russian_translation:
                        logger.info(f"Successfully generated sentence: {greek_sentence}")
                        return {
                            "greek": greek_sentence,
                            "russian": russian_translation
                        }
                
                logger.warning(f"Invalid response format on attempt {attempt + 1}")
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error on attempt {attempt + 1}: {e}")
            except Exception as e:
                logger.error(f"Error generating sentence on attempt {attempt + 1}: {e}")
        
        logger.error("Failed to generate sentence after all retries")
        return None
