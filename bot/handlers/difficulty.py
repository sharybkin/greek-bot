"""
Difficulty settings handler.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories.user_repo import UserRepository
from bot.keyboards.inline import InlineKeyboards
from bot.utils.logger import logger

router = Router()


@router.callback_query(F.data == "set_difficulty")
async def show_difficulty(callback: CallbackQuery, session: AsyncSession):
    """Show difficulty selection menu."""
    user_repo = UserRepository(session)
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    current_difficulty = user.difficulty_level if user else 1
    
    text = """
⚙️ **Настройка сложности**

Выбери уровень сложности предложений:

🟢 **Легко** - короткие предложения (3-5 слов)
🟡 **Средне** - средние предложения (6-9 слов)
🔴 **Сложно** - длинные предложения (10-15 слов)
"""
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboards.difficulty_selection(current_difficulty)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("difficulty_"))
async def set_difficulty(callback: CallbackQuery, session: AsyncSession):
    """Set difficulty level."""
    difficulty = int(callback.data.split("_")[1])
    
    user_repo = UserRepository(session)
    await user_repo.update_difficulty(callback.from_user.id, difficulty)
    
    difficulty_names = {1: "Легко", 2: "Средне", 3: "Сложно"}
    
    await callback.message.edit_text(
        f"✅ Сложность установлена: **{difficulty_names[difficulty]}**",
        reply_markup=InlineKeyboards.back_to_menu()
    )
    await callback.answer(f"Установлена сложность: {difficulty_names[difficulty]}")
    logger.info(f"User {callback.from_user.id} set difficulty to {difficulty}")
