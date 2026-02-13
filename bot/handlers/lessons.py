"""
Lessons selection handler with multi-selection support.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories.lesson_repo import LessonRepository
from bot.database.repositories.user_repo import UserRepository
from bot.keyboards.inline import InlineKeyboards
from bot.utils.logger import logger

router = Router()


@router.callback_query(F.data == "select_lessons")
async def show_lessons(callback: CallbackQuery, session: AsyncSession):
    """Show lessons selection menu."""
    lesson_repo = LessonRepository(session)
    user_repo = UserRepository(session)
    
    # Get all lessons
    lessons = await lesson_repo.get_all_lessons()
    
    # Get user's selected lessons
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    selected_ids = user.selected_lessons if user and user.selected_lessons else []
    
    # If no lessons selected, select all by default
    if not selected_ids and lessons:
        selected_ids = [lesson.id for lesson in lessons]
        await user_repo.update_selected_lessons(callback.from_user.id, selected_ids)
    
    text = """
📚 **Выбор уроков**

Выбери уроки для практики. Можно выбрать несколько уроков одновременно.
По умолчанию выбраны все уроки.
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboards.lessons_selection(lessons, selected_ids)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_lesson_"))
async def toggle_lesson(callback: CallbackQuery, session: AsyncSession):
    """Toggle lesson selection."""
    lesson_id = int(callback.data.split("_")[2])
    
    lesson_repo = LessonRepository(session)
    user_repo = UserRepository(session)
    
    # Get user's current selection
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    selected_ids = user.selected_lessons if user.selected_lessons else []
    
    # Toggle selection
    if lesson_id in selected_ids:
        selected_ids.remove(lesson_id)
    else:
        selected_ids.append(lesson_id)
    
    # Update user's selection
    await user_repo.update_selected_lessons(callback.from_user.id, selected_ids)
    
    # Refresh display
    lessons = await lesson_repo.get_all_lessons()
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboards.lessons_selection(lessons, selected_ids)
    )
    await callback.answer()


@router.callback_query(F.data == "select_all_lessons")
async def select_all_lessons(callback: CallbackQuery, session: AsyncSession):
    """Select all lessons."""
    lesson_repo = LessonRepository(session)
    user_repo = UserRepository(session)
    
    lessons = await lesson_repo.get_all_lessons()
    all_ids = [lesson.id for lesson in lessons]
    
    await user_repo.update_selected_lessons(callback.from_user.id, all_ids)
    
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboards.lessons_selection(lessons, all_ids)
    )
    await callback.answer("✅ Все уроки выбраны")


@router.callback_query(F.data == "deselect_all_lessons")
async def deselect_all_lessons(callback: CallbackQuery, session: AsyncSession):
    """Deselect all lessons."""
    lesson_repo = LessonRepository(session)
    user_repo = UserRepository(session)
    
    await user_repo.update_selected_lessons(callback.from_user.id, [])
    
    lessons = await lesson_repo.get_all_lessons()
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboards.lessons_selection(lessons, [])
    )
    await callback.answer("❌ Все уроки сняты")
