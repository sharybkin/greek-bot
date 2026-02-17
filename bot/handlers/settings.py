"""
Settings handler.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories.user_repo import UserRepository
from bot.keyboards.inline import InlineKeyboards
from bot.utils.logger import logger

router = Router()


@router.callback_query(F.data == "settings_menu")
async def show_settings(callback: CallbackQuery, session: AsyncSession):
    """Show settings menu."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    await callback.message.edit_text(
        "⚙️ **Настройки**\n\nЗдесь ты можешь настроить параметры генерации предложений:",
        reply_markup=InlineKeyboards.settings_menu(
            difficulty=user.difficulty_level,
            plural=user.plural_enabled,
            tense=user.tense_restriction
        )
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_plural")
async def toggle_plural(callback: CallbackQuery, session: AsyncSession):
    """Toggle plural setting."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    # Toggle
    user.plural_enabled = not user.plural_enabled
    await session.commit()
    
    # Refresh menu
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboards.settings_menu(
            difficulty=user.difficulty_level,
            plural=user.plural_enabled,
            tense=user.tense_restriction
        )
    )
    await callback.answer("Настройка 'Множественное число' обновлена")


@router.callback_query(F.data == "cycle_tense")
async def cycle_tense(callback: CallbackQuery, session: AsyncSession):
    """Cycle through tenses or show selection menu."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    await callback.message.edit_text(
        "⏳ **Выберите время глаголов**\n\nКакое время использовать в предложениях?",
        reply_markup=InlineKeyboards.tenses_selection(user.tense_restriction)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("set_tense_"))
async def set_tense(callback: CallbackQuery, session: AsyncSession):
    """Set specific tense."""
    tense = callback.data.replace("set_tense_", "")
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    if tense in ["all", "present", "past", "future"]:
        user.tense_restriction = tense
        await session.commit()
    
    # Return to settings
    await callback.message.edit_text(
        "⚙️ **Настройки**",
        reply_markup=InlineKeyboards.settings_menu(
            difficulty=user.difficulty_level,
            plural=user.plural_enabled,
            tense=user.tense_restriction
        )
    )
    await callback.answer("Настройка 'Время' обновлена")


@router.callback_query(F.data == "set_difficulty")
async def show_difficulty_settings(callback: CallbackQuery, session: AsyncSession):
    """
    Show difficulty selection from settings.
    We reuse the existing handler logic but we need to import it or recreate it.
    Since we are in settings, maybe we should just redirect to the existing difficulty handler?
    The existing difficulty handler is in `bot/handlers/difficulty.py`. 
    It probably expects to go back to main menu.
    Let's check `bot/keyboards/inline.py`'s `difficulty_selection` - it has a "Back to menu" button.
    For now, let's keep it simple and just show the difficulty menu, but we might want to change the "Back" behavior later.
    """
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    await callback.message.edit_text(
        "📊 **Выберите уровень сложности:**",
        reply_markup=InlineKeyboards.difficulty_selection(user.difficulty_level)
    )
    await callback.answer()
