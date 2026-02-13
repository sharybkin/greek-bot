"""
Throttling middleware to prevent spam.
"""

from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from collections import defaultdict
import time


class ThrottlingMiddleware(BaseMiddleware):
    """Middleware to throttle user requests."""
    
    def __init__(self, rate_limit: float = 1.0):
        """
        Initialize throttling middleware.
        
        Args:
            rate_limit: Minimum seconds between requests
        """
        self.rate_limit = rate_limit
        self.user_last_request = defaultdict(float)
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Check rate limit and process update."""
        
        user = data.get("event_from_user")
        
        if user:
            user_id = user.id
            current_time = time.time()
            last_request = self.user_last_request[user_id]
            
            if current_time - last_request < self.rate_limit:
                # Rate limit exceeded, skip this update
                return
            
            self.user_last_request[user_id] = current_time
        
        return await handler(event, data)
