"""
Statistics handler.
"""

from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories.review_repo import ReviewRepository
from bot.keyboards.inline import InlineKeyboards
from bot.utils.logger import logger

router = Router()


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession):
    """Handle /stats command."""
    await show_statistics(message.from_user.id, session, message=message)


@router.callback_query(F.data == "show_stats")
async def show_stats_callback(callback: CallbackQuery, session: AsyncSession):
    """Show statistics via callback."""
    await show_statistics(callback.from_user.id, session, callback=callback)


async def show_statistics(user_id: int, session: AsyncSession, message: Message = None, callback: CallbackQuery = None):
    """Show user statistics."""
    review_repo = ReviewRepository(session)
    
    # Get review statistics
    stats = await review_repo.get_review_stats(user_id)
    
    text = f"""
📊 **Твоя статистика обучения**

🎓 **Прогресс по словам:**
• Всего слов в повторении: {stats['total']}
• Освоенных слов: {stats['mastered']}
• В процессе изучения: {stats['in_progress']}
• Доступно для повторения: {stats['due_now']}

Продолжай в том же духе! 🎯
"""
    
    if callback:
        await callback.message.edit_text(
            text,
            reply_markup=InlineKeyboards.back_to_menu()
        )
        await callback.answer()
    elif message:
        await message.answer(
            text,
            reply_markup=InlineKeyboards.back_to_menu()
        )
