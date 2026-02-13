"""
Review words repository for spaced repetition.
"""

from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from bot.database.models import ReviewWord, Word
from bot.utils.logger import logger


class ReviewRepository:
    """Repository for ReviewWord model operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def add_words_to_review(
        self,
        user_telegram_id: int,
        word_ids: List[int]
    ) -> List[ReviewWord]:
        """
        Add words to review list for user.
        
        Args:
            user_telegram_id: Telegram user ID
            word_ids: List of word IDs to add
            
        Returns:
            List of created ReviewWord models
        """
        created_reviews = []
        now = datetime.now()
        
        for word_id in word_ids:
            # Check if already exists
            existing = await self.session.execute(
                select(ReviewWord).where(
                    and_(
                        ReviewWord.user_telegram_id == user_telegram_id,
                        ReviewWord.word_id == word_id
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue
            
            review = ReviewWord(
                user_telegram_id=user_telegram_id,
                word_id=word_id,
                next_review_at=now  # Available immediately
            )
            self.session.add(review)
            created_reviews.append(review)
        
        await self.session.commit()
        logger.info(f"Added {len(created_reviews)} words to review for user {user_telegram_id}")
        return created_reviews
    
    async def get_due_reviews(
        self,
        user_telegram_id: int,
        limit: int = 20
    ) -> List[ReviewWord]:
        """
        Get words due for review.
        
        Args:
            user_telegram_id: Telegram user ID
            limit: Maximum number of words to return
            
        Returns:
            List of ReviewWord models with Word relationship loaded
        """
        now = datetime.now()
        result = await self.session.execute(
            select(ReviewWord)
            .where(
                and_(
                    ReviewWord.user_telegram_id == user_telegram_id,
                    ReviewWord.mastered == False,
                    ReviewWord.next_review_at <= now
                )
            )
            .order_by(ReviewWord.next_review_at.asc())
            .limit(limit)
            .options(selectinload(ReviewWord.word))
        )
        return list(result.scalars().all())
    
    async def update_review_progress(
        self,
        review_id: int,
        success: bool = True
    ) -> None:
        """
        Update review progress after practice.
        
        Args:
            review_id: ReviewWord ID
            success: Whether the review was successful
        """
        review = await self.session.get(ReviewWord, review_id)
        if not review:
            return
        
        now = datetime.now()
        review.last_reviewed_at = now
        review.review_count += 1
        
        # Calculate next review time based on spaced repetition
        if review.review_count == 1:
            review.next_review_at = now + timedelta(hours=1)
        elif review.review_count == 2:
            review.next_review_at = now + timedelta(hours=4)
        elif review.review_count == 3:
            review.next_review_at = now + timedelta(days=1)
        elif review.review_count == 4:
            review.next_review_at = now + timedelta(days=3)
        elif review.review_count >= 5:
            review.next_review_at = now + timedelta(days=7)
            review.mastered = True
        
        await self.session.commit()
        logger.info(f"Updated review {review_id}: count={review.review_count}, mastered={review.mastered}")
    
    async def get_review_stats(self, user_telegram_id: int) -> dict:
        """
        Get review statistics for user.
        
        Args:
            user_telegram_id: Telegram user ID
            
        Returns:
            Dictionary with review statistics
        """
        # Total words in review
        total_result = await self.session.execute(
            select(ReviewWord).where(ReviewWord.user_telegram_id == user_telegram_id)
        )
        total = len(list(total_result.scalars().all()))
        
        # Mastered words
        mastered_result = await self.session.execute(
            select(ReviewWord).where(
                and_(
                    ReviewWord.user_telegram_id == user_telegram_id,
                    ReviewWord.mastered == True
                )
            )
        )
        mastered = len(list(mastered_result.scalars().all()))
        
        # Due for review
        now = datetime.now()
        due_result = await self.session.execute(
            select(ReviewWord).where(
                and_(
                    ReviewWord.user_telegram_id == user_telegram_id,
                    ReviewWord.mastered == False,
                    ReviewWord.next_review_at <= now
                )
            )
        )
        due = len(list(due_result.scalars().all()))
        
        return {
            "total": total,
            "mastered": mastered,
            "in_progress": total - mastered,
            "due_now": due
        }
