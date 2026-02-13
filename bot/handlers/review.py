"""
Review handler for spaced repetition.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories.review_repo import ReviewRepository
from bot.database.repositories.lesson_repo import LessonRepository
from bot.keyboards.inline import InlineKeyboards
from bot.utils.logger import logger

router = Router()

# Store selected word IDs temporarily (in production, use FSM or database)
user_selected_words = {}


@router.callback_query(F.data.startswith("select_word_"))
async def select_word_for_review(callback: CallbackQuery):
    """Toggle word selection for review."""
    word_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    if user_id not in user_selected_words:
        user_selected_words[user_id] = set()
    
    if word_id in user_selected_words[user_id]:
        user_selected_words[user_id].remove(word_id)
        await callback.answer("❌ Слово снято")
    else:
        user_selected_words[user_id].add(word_id)
        await callback.answer("✅ Слово выбрано")


@router.callback_query(F.data == "add_to_review")
async def add_words_to_review(callback: CallbackQuery, session: AsyncSession):
    """Add selected words to review list."""
    user_id = callback.from_user.id
    
    if user_id not in user_selected_words or not user_selected_words[user_id]:
        await callback.answer("Выбери хотя бы одно слово", show_alert=True)
        return
    
    review_repo = ReviewRepository(session)
    word_ids = list(user_selected_words[user_id])
    
    await review_repo.add_words_to_review(user_id, word_ids)
    
    # Clear selection
    user_selected_words[user_id] = set()
    
    text = f"""
✅ **Добавлено {len(word_ids)} слов для повторения!**

Что дальше?
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboards.review_actions()
    )
    await callback.answer(f"Добавлено {len(word_ids)} слов")
    logger.info(f"User {user_id} added {len(word_ids)} words to review")


@router.callback_query(F.data == "cancel_word_selection")
async def cancel_word_selection(callback: CallbackQuery):
    """Cancel word selection."""
    user_id = callback.from_user.id
    if user_id in user_selected_words:
        user_selected_words[user_id] = set()
    
    await callback.message.edit_text(
        "❌ Отменено",
        reply_markup=InlineKeyboards.back_to_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "start_review")
async def start_review(callback: CallbackQuery, session: AsyncSession):
    """Start review session."""
    review_repo = ReviewRepository(session)
    
    # Get words due for review
    reviews = await review_repo.get_due_reviews(callback.from_user.id, limit=20)
    
    if not reviews:
        await callback.message.edit_text(
            "🎉 **Нет слов для повторения!**\n\nВсе слова выучены или ещё не пришло время повторения.",
            reply_markup=InlineKeyboards.back_to_menu()
        )
        await callback.answer()
        return
    
    text = f"""
🔄 **Повторение слов**

Найдено слов для повторения: {len(reviews)}

Функция повторения в разработке. Скоро будет доступна!
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboards.back_to_menu()
    )
    await callback.answer()
