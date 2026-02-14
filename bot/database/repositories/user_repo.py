"""
User repository for database operations.
"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.models import User
from bot.utils.logger import logger


class UserRepository:
    """Repository for User model operations."""
    
    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.
        
        Args:
            session: Async database session
        """
        self.session = session
    
    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """
        Get user by Telegram ID.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            User model or None if not found
        """
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()
    
    async def create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None
    ) -> User:
        """
        Create new user.
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            
        Returns:
            Created User model
        """
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            selected_lessons=[]  # Empty list by default
        )
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        logger.info(f"Created new user: {telegram_id}")
        return user
    
    async def get_or_create(
        self,
        telegram_id: int,
        username: Optional[str] = None,
        first_name: Optional[str] = None
    ) -> User:
        """
        Get existing user or create new one.
        
        Args:
            telegram_id: Telegram user ID
            username: Telegram username
            first_name: User's first name
            
        Returns:
            User model
        """
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            return user
        return await self.create(telegram_id, username, first_name)
    
    async def update_last_active(self, telegram_id: int) -> None:
        """
        Update user's last active timestamp.
        
        Args:
            telegram_id: Telegram user ID
        """
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(last_active_at=datetime.now())
        )
        await self.session.commit()
    
    async def update_current_lesson(self, telegram_id: int, lesson_id: Optional[int]) -> None:
        """
        Update user's current lesson.
        
        Args:
            telegram_id: Telegram user ID
            lesson_id: Lesson ID or None
        """
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(current_lesson_id=lesson_id)
        )
        await self.session.commit()
        logger.info(f"Updated current lesson for user {telegram_id}: {lesson_id}")
    
    async def update_selected_lessons(self, telegram_id: int, lesson_ids: List[int]) -> None:
        """
        Update user's selected lessons.
        
        Args:
            telegram_id: Telegram user ID
            lesson_ids: List of lesson IDs
        """
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(selected_lessons=lesson_ids)
        )
        await self.session.commit()
        logger.info(f"Updated selected lessons for user {telegram_id}: {lesson_ids}")
    
    async def update_difficulty(self, telegram_id: int, difficulty: int) -> None:
        """
        Update user's difficulty level.
        
        Args:
            telegram_id: Telegram user ID
            difficulty: Difficulty level (1-3)
        """
        if difficulty not in [1, 2, 3]:
            raise ValueError("Difficulty must be between 1 and 3")
        
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(difficulty_level=difficulty)
        )
        await self.session.commit()
        logger.info(f"Updated difficulty for user {telegram_id}: {difficulty}")
    
    async def update_premium_status(self, telegram_id: int, is_premium: bool) -> None:
        """
        Update user's premium status.
        
        Args:
            telegram_id: Telegram user ID
            is_premium: Premium status
        """
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(is_premium=is_premium)
        )
        await self.session.commit()
        logger.info(f"Updated premium status for user {telegram_id}: {is_premium}")
    
    async def check_and_reset_generation_count(self, telegram_id: int) -> None:
        """
        Check if generation count needs to be reset (new day) and reset if needed.
        
        Args:
            telegram_id: Telegram user ID
        """
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            return
        
        now = datetime.now()
        # Check if last reset was on a different day
        if user.last_generation_reset.date() < now.date():
            await self.session.execute(
                update(User)
                .where(User.telegram_id == telegram_id)
                .values(
                    daily_generation_count=0,
                    last_generation_reset=now
                )
            )
            await self.session.commit()
            logger.info(f"Reset generation count for user {telegram_id}")
    
    async def increment_generation_count(self, telegram_id: int) -> None:
        """
        Increment user's daily generation count.
        
        Args:
            telegram_id: Telegram user ID
        """
        await self.session.execute(
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(daily_generation_count=User.daily_generation_count + 1)
        )
        await self.session.commit()
    
    async def can_generate(self, telegram_id: int) -> tuple[bool, int]:
        """
        Check if user can generate a new sentence.
        
        Args:
            telegram_id: Telegram user ID
            
        Returns:
            Tuple of (can_generate, remaining_count)
        """
        await self.check_and_reset_generation_count(telegram_id)
        user = await self.get_by_telegram_id(telegram_id)
        
        if not user:
            return False, 0
        
        # Premium users have unlimited generations
        if user.is_premium:
            return True, -1  # -1 indicates unlimited
        
        # Regular users have 3 generations per day
        max_generations = 3
        remaining = max_generations - user.daily_generation_count
        return remaining > 0, remaining
    
    async def get_all_users(self, limit: int = 100, offset: int = 0) -> List[User]:
        """
        Get all users with pagination.
        
        Args:
            limit: Maximum number of users to return
            offset: Number of users to skip
            
        Returns:
            List of User models
        """
        result = await self.session.execute(
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

