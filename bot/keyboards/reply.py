"""
Reply keyboards (if needed).
"""

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


class ReplyKeyboards:
    """Factory for creating reply keyboards."""
    
    @staticmethod
    def remove_keyboard() -> ReplyKeyboardMarkup:
        """Create keyboard removal markup."""
        return ReplyKeyboardMarkup(
            keyboard=[],
            resize_keyboard=True,
            one_time_keyboard=True
        )
