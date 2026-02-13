"""
Lesson and Word repository for database operations.
"""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from bot.database.models import Lesson, Word


class LessonRepository:
    """Repository for Lesson and Word model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_all_lessons(self) -> List[Lesson]:
        """Get all lessons ordered by order_number."""
        result = await self.session.execute(
            select(Lesson).order_by(Lesson.order_number)
        )
        return list(result.scalars().all())
    
    async def get_lesson_by_id(self, lesson_id: int) -> Optional[Lesson]:
        """Get lesson by ID."""
        result = await self.session.execute(
            select(Lesson).where(Lesson.id == lesson_id)
        )
        return result.scalar_one_or_none()
    
    async def get_words_by_lesson_ids(self, lesson_ids: List[int]) -> List[Word]:
        """
        Get all words from multiple lessons.
        
        Args:
            lesson_ids: List of lesson IDs
            
        Returns:
            List of Word models
        """
        if not lesson_ids:
            return []
        
        result = await self.session.execute(
            select(Word)
            .where(Word.lesson_id.in_(lesson_ids))
            .options(selectinload(Word.lesson))
        )
        return list(result.scalars().all())
    
    async def get_word_by_id(self, word_id: int) -> Optional[Word]:
        """Get word by ID."""
        result = await self.session.execute(
            select(Word).where(Word.id == word_id)
        )
        return result.scalar_one_or_none()
    
    async def get_words_by_ids(self, word_ids: List[int]) -> List[Word]:
        """Get multiple words by their IDs."""
        if not word_ids:
            return []
        
        result = await self.session.execute(
            select(Word).where(Word.id.in_(word_ids))
        )
        return list(result.scalars().all())
