"""
Inline keyboards for bot interface.
"""

from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.database.models import Lesson, Word


class InlineKeyboards:
    """Factory for creating inline keyboards."""
    
    @staticmethod
    def main_menu() -> InlineKeyboardMarkup:
        """Create main menu keyboard."""
        buttons = [
            [InlineKeyboardButton(text="📚 Выбрать уроки", callback_data="select_lessons")],
            [InlineKeyboardButton(text="⚙️ Настроить сложность", callback_data="set_difficulty")],
            [InlineKeyboardButton(text="🎯 Начать практику", callback_data="start_practice")],
            [InlineKeyboardButton(text="🔄 Повторение слов", callback_data="start_review")],
            [InlineKeyboardButton(text="📊 Моя статистика", callback_data="show_stats")],
            [InlineKeyboardButton(text="ℹ️ Помощь", callback_data="show_help")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def lessons_selection(lessons: List[Lesson], selected_ids: List[int]) -> InlineKeyboardMarkup:
        """
        Create lessons selection keyboard with checkboxes.
        
        Args:
            lessons: List of available lessons
            selected_ids: List of currently selected lesson IDs
            
        Returns:
            InlineKeyboardMarkup with lesson selection buttons
        """
        buttons = []
        
        for lesson in lessons:
            is_selected = lesson.id in selected_ids
            checkbox = "✅" if is_selected else "☐"
            text = f"{checkbox} {lesson.name}"
            callback = f"toggle_lesson_{lesson.id}"
            buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])
        
        # Control buttons
        buttons.append([
            InlineKeyboardButton(text="✅ Выбрать все", callback_data="select_all_lessons"),
            InlineKeyboardButton(text="❌ Снять все", callback_data="deselect_all_lessons")
        ])
        buttons.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def difficulty_selection(current_difficulty: int) -> InlineKeyboardMarkup:
        """
        Create difficulty selection keyboard.
        
        Args:
            current_difficulty: Current difficulty level (1-3)
            
        Returns:
            InlineKeyboardMarkup with difficulty options
        """
        difficulties = [
            (1, "🟢 Легко (3-5 слов)"),
            (2, "🟡 Средне (6-9 слов)"),
            (3, "🔴 Сложно (10-15 слов)")
        ]
        
        buttons = []
        for level, text in difficulties:
            if level == current_difficulty:
                text = f"✅ {text}"
            buttons.append([InlineKeyboardButton(
                text=text,
                callback_data=f"difficulty_{level}"
            )])
        
        buttons.append([InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")])
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def practice_controls() -> InlineKeyboardMarkup:
        """Create practice control buttons."""
        buttons = [
            [InlineKeyboardButton(text="✅ Всё понятно - дальше", callback_data="next_sentence")],
            [InlineKeyboardButton(text="❌ Забыл слова - повторить", callback_data="forgot_words")],
            [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def word_selection(words: List[Word]) -> InlineKeyboardMarkup:
        """
        Create word selection keyboard for adding to review.
        
        Args:
            words: List of words to choose from
            
        Returns:
            InlineKeyboardMarkup with word selection buttons
        """
        buttons = []
        
        for word in words:
            text = f"{word.greek_word} - {word.russian_translation}"
            callback = f"select_word_{word.id}"
            buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])
        
        buttons.append([
            InlineKeyboardButton(text="✅ Добавить выбранные", callback_data="add_to_review"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_word_selection")
        ])
        
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def review_actions() -> InlineKeyboardMarkup:
        """Create review action buttons."""
        buttons = [
            [InlineKeyboardButton(text="🔄 Начать повторение", callback_data="start_review")],
            [InlineKeyboardButton(text="🎯 Продолжить практику", callback_data="start_practice")],
            [InlineKeyboardButton(text="🏠 Вернуться в меню", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(inline_keyboard=buttons)
    
    @staticmethod
    def back_to_menu() -> InlineKeyboardMarkup:
        """Create simple back to menu button."""
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="◀️ Назад в меню", callback_data="main_menu")]
        ])
