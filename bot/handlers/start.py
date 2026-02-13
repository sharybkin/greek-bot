"""
Start command and main menu handler.
"""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from bot.keyboards.inline import InlineKeyboards
from bot.utils.logger import logger

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Handle /start command."""
    user = message.from_user
    
    welcome_text = f"""
👋 Привет, {user.first_name}!

Добро пожаловать в бота для изучения греческого языка! 🇬🇷

Я помогу тебе:
• Практиковать греческий с AI-генерацией предложений
• Слушать правильное произношение
• Повторять слова по системе интервального повторения

Выбери действие из меню ниже:
"""
    
    await message.answer(
        welcome_text,
        reply_markup=InlineKeyboards.main_menu()
    )
    logger.info(f"User {user.id} started the bot")


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Handle /help command."""
    help_text = """
📖 **Как пользоваться ботом:**

1️⃣ **Выбрать уроки** - выбери один или несколько уроков для практики
2️⃣ **Настроить сложность** - выбери уровень сложности предложений
3️⃣ **Начать практику** - слушай предложения и учи новые слова
4️⃣ **Повторение слов** - повторяй забытые слова
5️⃣ **Статистика** - смотри свой прогресс

**Команды:**
/start - Главное меню
/help - Эта справка
/stats - Статистика

Удачи в изучении греческого! 🎯
"""
    
    await message.answer(
        help_text,
        reply_markup=InlineKeyboards.back_to_menu()
    )


@router.callback_query(F.data == "main_menu")
async def show_main_menu(callback: CallbackQuery):
    """Show main menu."""
    await callback.message.delete()
    await callback.message.answer(
        "🏠 **Главное меню**\n\nВыбери действие:",
        reply_markup=InlineKeyboards.main_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "show_help")
async def show_help_callback(callback: CallbackQuery):
    """Show help via callback."""
    help_text = """
📖 **Как пользоваться ботом:**

1️⃣ **Выбрать уроки** - выбери один или несколько уроков
2️⃣ **Настроить сложность** - уровень сложности предложений
3️⃣ **Начать практику** - слушай и учи
4️⃣ **Повторение слов** - повторяй забытые слова
5️⃣ **Статистика** - смотри прогресс
"""
    
    await callback.message.edit_text(
        help_text,
        reply_markup=InlineKeyboards.back_to_menu()
    )
    await callback.answer()
