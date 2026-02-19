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
    
    # Ensure tense_restriction is a list
    tenses = user.tense_restriction
    if not isinstance(tenses, list):
        tenses = ["present", "past", "future"]
        
    await callback.message.edit_text(
        "⚙️ **Настройки**\n\nЗдесь ты можешь настроить параметры генерации предложений:",
        reply_markup=InlineKeyboards.settings_menu(
            difficulty=user.difficulty_level,
            plural=user.plural_enabled,
            tenses=tenses,
            personal_pronouns=user.personal_pronouns_enabled,
            possessive_pronouns=user.possessive_pronouns_enabled,
            prepositions=user.prepositions_enabled,
            interrogative_words=user.interrogative_words_enabled
        )
    )
    await callback.answer()


@router.callback_query(F.data == "toggle_plural")
async def toggle_plural(callback: CallbackQuery, session: AsyncSession):
    """Toggle plural setting."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    # Toggle
    new_plural = not user.plural_enabled
    await user_repo.update_plural_enabled(callback.from_user.id, new_plural)
    
    # Refresh user object to get updated state for UI
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    # Ensure tense_restriction is a list
    tenses = user.tense_restriction
    if not isinstance(tenses, list):
        tenses = ["present", "past", "future"]
    
    # Refresh menu
    logger.info(f"User {callback.from_user.id} toggled plural to {user.plural_enabled}")
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboards.settings_menu(
            difficulty=user.difficulty_level,
            plural=user.plural_enabled,
            tenses=tenses,
            personal_pronouns=user.personal_pronouns_enabled,
            possessive_pronouns=user.possessive_pronouns_enabled,
            prepositions=user.prepositions_enabled,
            interrogative_words=user.interrogative_words_enabled
        )
    )
    await callback.answer("Настройка 'Множественное число' обновлена")


@router.callback_query(F.data == "open_tense_selection")
async def open_tense_selection(callback: CallbackQuery, session: AsyncSession):
    """Show tense selection menu."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    tenses = user.tense_restriction
    if not isinstance(tenses, list):
        tenses = ["present", "past", "future"]
        
    await callback.message.edit_text(
        "⏳ **Выберите времена глаголов**\n\nОтметьте времена, которые можно использовать:",
        reply_markup=InlineKeyboards.tenses_selection(tenses)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_tense_"))
async def toggle_tense(callback: CallbackQuery, session: AsyncSession):
    """Toggle specific tense."""
    tense = callback.data.replace("toggle_tense_", "")
    
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    current_tenses = user.tense_restriction
    if not isinstance(current_tenses, list):
        current_tenses = ["present", "past", "future"]
    else:
        # Create a copy to avoid in-place modification issues
        current_tenses = list(current_tenses)
        
    # Toggle logic
    if tense in ["present", "past", "future"]:
        if tense in current_tenses:
            # Don't allow removing the last tense
            if len(current_tenses) > 1:
                current_tenses.remove(tense)
            else:
                await callback.answer("⚠️ Должно быть выбрано хотя бы одно время!", show_alert=True)
                return
        else:
            current_tenses.append(tense)
            
        # Update user via repository (bypass mutation tracking issues)
        await user_repo.update_tense_restriction(callback.from_user.id, current_tenses)
        
        # Refresh user object
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        logger.info(f"User {callback.from_user.id} updated tenses to: {user.tense_restriction}")
    
    # Refresh selection menu
    await callback.message.edit_reply_markup(
        reply_markup=InlineKeyboards.tenses_selection(user.tense_restriction)
    )
    await callback.answer()


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


@router.callback_query(F.data == "toggle_personal_pronouns")
async def toggle_personal_pronouns(callback: CallbackQuery, session: AsyncSession):
    """Toggle personal pronouns setting."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    new_value = not user.personal_pronouns_enabled
    await user_repo.update_extra_settings(callback.from_user.id, personal_pronouns_enabled=new_value)
    
    await show_settings(callback, session)
    await callback.answer("Настройка 'Личные местоимения' обновлена")


@router.callback_query(F.data == "toggle_possessive_pronouns")
async def toggle_possessive_pronouns(callback: CallbackQuery, session: AsyncSession):
    """Toggle possessive pronouns setting."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    new_value = not user.possessive_pronouns_enabled
    await user_repo.update_extra_settings(callback.from_user.id, possessive_pronouns_enabled=new_value)
    
    await show_settings(callback, session)
    await callback.answer("Настройка 'Притяжательные местоимения' обновлена")


@router.callback_query(F.data == "toggle_prepositions")
async def toggle_prepositions(callback: CallbackQuery, session: AsyncSession):
    """Toggle prepositions setting."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    new_value = not user.prepositions_enabled
    await user_repo.update_extra_settings(callback.from_user.id, prepositions_enabled=new_value)
    
    await show_settings(callback, session)
    await callback.answer("Настройка 'Предлоги' обновлена")


@router.callback_query(F.data == "toggle_interrogative_words")
async def toggle_interrogative_words(callback: CallbackQuery, session: AsyncSession):
    """Toggle interrogative words setting."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    new_value = not user.interrogative_words_enabled
    await user_repo.update_extra_settings(callback.from_user.id, interrogative_words_enabled=new_value)
    
    await show_settings(callback, session)
    await callback.answer("Настройка 'Вопросительные слова' обновлена")
