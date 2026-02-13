"""
User middleware for automatic user creation and updates.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories.user_repo import UserRepository
from bot.database.database import async_session_maker
from bot.utils.logger import logger


class UserMiddleware(BaseMiddleware):
    """Middleware to create/update user in database."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Process update and create/update user."""
        
        # Get user from event
        user: User = data.get("event_from_user")
        
        if user:
            async with async_session_maker() as session:
                user_repo = UserRepository(session)
                
                # Get or create user
                db_user = await user_repo.get_or_create(
                    telegram_id=user.id,
                    username=user.username,
                    first_name=user.first_name
                )
                
                # Update last active
                await user_repo.update_last_active(user.id)
                
                # Add session to data for handlers
                data["session"] = session
                
                # Call handler
                return await handler(event, data)
        
        return await handler(event, data)
