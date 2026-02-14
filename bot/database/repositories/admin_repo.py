"""
Admin repository for user management and statistics.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User, UserStatistics, SentenceHistory, ReviewWord
from bot.utils.logger import logger


class AdminRepository:
    """Repository for admin operations."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: Async database session
        """
        self.session = session
    
    async def get_all_users_with_stats(self) -> List[Dict[str, Any]]:
        """
        Get all users with their statistics.
        
        Returns:
            List of user dictionaries with statistics
        """
        # Get all users
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = result.scalars().all()
        
        users_data = []
        for user in users:
            # Get total sentences generated
            sentences_result = await self.session.execute(
                select(func.count(SentenceHistory.id))
                .where(SentenceHistory.user_telegram_id == user.telegram_id)
            )
            total_sentences = sentences_result.scalar() or 0
            
            # Get total words in review
            words_result = await self.session.execute(
                select(func.count(ReviewWord.id))
                .where(ReviewWord.user_telegram_id == user.telegram_id)
            )
            total_review_words = words_result.scalar() or 0
            
            # Get last 7 days activity
            seven_days_ago = datetime.now() - timedelta(days=7)
            recent_activity = await self.session.execute(
                select(func.count(SentenceHistory.id))
                .where(
                    SentenceHistory.user_telegram_id == user.telegram_id,
                    SentenceHistory.created_at >= seven_days_ago
                )
            )
            recent_sentences = recent_activity.scalar() or 0
            
            users_data.append({
                "telegram_id": user.telegram_id,
                "username": user.username or "N/A",
                "first_name": user.first_name or "N/A",
                "is_premium": user.is_premium,
                "daily_generation_count": user.daily_generation_count,
                "difficulty_level": user.difficulty_level,
                "total_sentences": total_sentences,
                "total_review_words": total_review_words,
                "recent_sentences_7d": recent_sentences,
                "created_at": user.created_at.isoformat(),
                "last_active_at": user.last_active_at.isoformat()
            })
        
        return users_data
    
    async def get_global_statistics(self) -> Dict[str, Any]:
        """
        Get global statistics across all users.
        
        Returns:
            Dictionary with global statistics
        """
        # Total users
        total_users_result = await self.session.execute(
            select(func.count(User.telegram_id))
        )
        total_users = total_users_result.scalar() or 0
        
        # Premium users
        premium_users_result = await self.session.execute(
            select(func.count(User.telegram_id))
            .where(User.is_premium == True)
        )
        premium_users = premium_users_result.scalar() or 0
        
        # Total sentences generated
        total_sentences_result = await self.session.execute(
            select(func.count(SentenceHistory.id))
        )
        total_sentences = total_sentences_result.scalar() or 0
        
        # Active users (last 7 days)
        seven_days_ago = datetime.now() - timedelta(days=7)
        active_users_result = await self.session.execute(
            select(func.count(func.distinct(User.telegram_id)))
            .where(User.last_active_at >= seven_days_ago)
        )
        active_users = active_users_result.scalar() or 0
        
        # Sentences generated today
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_sentences_result = await self.session.execute(
            select(func.count(SentenceHistory.id))
            .where(SentenceHistory.created_at >= today_start)
        )
        today_sentences = today_sentences_result.scalar() or 0
        
        return {
            "total_users": total_users,
            "premium_users": premium_users,
            "regular_users": total_users - premium_users,
            "total_sentences": total_sentences,
            "active_users_7d": active_users,
            "sentences_today": today_sentences
        }
