"""
Sentence history repository.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import SentenceHistory
from bot.utils.logger import logger


class SentenceRepository:
    """Repository for SentenceHistory model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def create(
        self,
        user_telegram_id: int,
        greek_sentence: str,
        russian_translation: str,
        word_ids: List[int],
        difficulty_level: int,
        audio_file_id: Optional[str] = None
    ) -> SentenceHistory:
        """
        Create new sentence history entry.
        
        Args:
            user_telegram_id: Telegram user ID
            greek_sentence: Greek sentence text
            russian_translation: Russian translation
            word_ids: List of word IDs used in sentence
            difficulty_level: Difficulty level (1-3)
            audio_file_id: Telegram file ID for audio
            
        Returns:
            Created SentenceHistory model
        """
        sentence = SentenceHistory(
            user_telegram_id=user_telegram_id,
            greek_sentence=greek_sentence,
            russian_translation=russian_translation,
            word_ids=word_ids,
            difficulty_level=difficulty_level,
            audio_file_id=audio_file_id
        )
        self.session.add(sentence)
        await self.session.commit()
        await self.session.refresh(sentence)
        logger.info(f"Created sentence history for user {user_telegram_id}")
        return sentence
    
    async def get_recent_sentences(
        self,
        user_telegram_id: int,
        limit: int = 10
    ) -> List[SentenceHistory]:
        """
        Get recent sentences for user.
        
        Args:
            user_telegram_id: Telegram user ID
            limit: Maximum number of sentences to return
            
        Returns:
            List of SentenceHistory models
        """
        result = await self.session.execute(
            select(SentenceHistory)
            .where(SentenceHistory.user_telegram_id == user_telegram_id)
            .order_by(SentenceHistory.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
    
    async def get_last_sentence(self, user_telegram_id: int) -> Optional[SentenceHistory]:
        """
        Get the most recent sentence for user.
        
        Args:
            user_telegram_id: Telegram user ID
            
        Returns:
            SentenceHistory model or None
        """
        result = await self.session.execute(
            select(SentenceHistory)
            .where(SentenceHistory.user_telegram_id == user_telegram_id)
            .order_by(SentenceHistory.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_word_last_usage(self, user_telegram_id: int) -> dict[int, datetime]:
        """
        Get last usage time for each word.
        
        Args:
            user_telegram_id: Telegram user ID
            
        Returns:
            Dictionary {word_id: last_used_datetime}
        """
        # We need to unnest the array of word_ids and find max created_at for each
        stmt = (
            select(
                func.unnest(SentenceHistory.word_ids).label('word_id'),
                func.max(SentenceHistory.created_at).label('last_used')
            )
            .where(SentenceHistory.user_telegram_id == user_telegram_id)
            .group_by('word_id')
        )
        
        result = await self.session.execute(stmt)
        return {row.word_id: row.last_used for row in result}

