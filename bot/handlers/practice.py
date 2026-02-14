"""
Practice handler - main learning module.
"""

import random
from io import BytesIO
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories.user_repo import UserRepository
from bot.database.repositories.lesson_repo import LessonRepository
from bot.database.repositories.sentence_repo import SentenceRepository
from bot.services.ai_service import AIService
from bot.services.tts_service import TTSService
from bot.keyboards.inline import InlineKeyboards
from bot.utils.logger import logger

router = Router()

# Initialize services
ai_service = AIService()
tts_service = TTSService()


@router.callback_query(F.data == "start_practice")
async def start_practice(callback: CallbackQuery, session: AsyncSession):
    """Start practice session."""
    user_repo = UserRepository(session)
    lesson_repo = LessonRepository(session)
    
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    # Check if lessons are selected
    if not user.selected_lessons:
        await callback.message.edit_text(
            "❌ Сначала выбери уроки для практики!",
            reply_markup=InlineKeyboards.back_to_menu()
        )
        await callback.answer()
        return
    
    # Check generation limit for non-premium users
    can_generate, remaining = await user_repo.can_generate(callback.from_user.id)
    if not can_generate:
        await callback.message.edit_text(
            "⛔️ **Лимит генераций исчерпан**\\n\\n"
            "Ты использовал все 3 бесплатные генерации на сегодня\\.\\n"
            "Попробуй завтра или обратись к администратору для получения Premium\\-доступа\\!",
            reply_markup=InlineKeyboards.back_to_menu(),
            parse_mode="MarkdownV2"
        )
        await callback.answer()
        return
    
    await callback.answer("Генерирую предложение...")
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    # Show remaining generations for non-premium users
    if remaining > 0:
        loading_msg = await callback.message.answer(
            f"⏳ Генерирую предложение для тебя...\n💡 Осталось генераций сегодня: {remaining - 1}"
        )
    else:
        loading_msg = await callback.message.answer("⏳ Генерирую предложение для тебя...")
    
    # Get words from selected lessons
    words = await lesson_repo.get_words_by_lesson_ids(user.selected_lessons)
    
    if not words:
        await loading_msg.edit_text(
            "❌ В выбранных уроках нет слов!",
            reply_markup=InlineKeyboards.back_to_menu()
        )
        return
    
    # Select random words based on difficulty
    difficulty_word_count = {1: 4, 2: 7, 3: 12}
    word_count = difficulty_word_count.get(user.difficulty_level, 4)
    selected_words = random.sample(words, min(word_count, len(words)))
    
    # Generate sentence
    greek_words = [w.greek_word for w in selected_words]
    logger.info(f"Selected words for sentence generation: {greek_words}")
    sentence_data = await ai_service.generate_sentence(greek_words, user.difficulty_level)
    
    if not sentence_data:
        await loading_msg.edit_text(
            "❌ Не удалось сгенерировать предложение. Попробуй ещё раз.",
            reply_markup=InlineKeyboards.back_to_menu()
        )
        return
    
    # Generate audio
    audio_bytes = await tts_service.synthesize(sentence_data["greek"])
    
    if not audio_bytes:
        await loading_msg.delete()
        await callback.message.answer(
            f"🇬🇷 {sentence_data['greek']}\n\n❌ Не удалось сгенерировать аудио",
            reply_markup=InlineKeyboards.practice_controls()
        )
        return
    
    # Save to history
    sentence_repo = SentenceRepository(session)
    word_ids = [w.id for w in selected_words]
    await sentence_repo.create(
        user_telegram_id=callback.from_user.id,
        greek_sentence=sentence_data["greek"],
        russian_translation=sentence_data["russian"],
        word_ids=word_ids,
        difficulty_level=user.difficulty_level
    )
    
    # Increment generation count
    await user_repo.increment_generation_count(callback.from_user.id)
    
    # Send audio
    audio_file = BufferedInputFile(audio_bytes, filename="greek.mp3")
    await loading_msg.delete()
    caption = f"""🎧 Послушай предложение:

🇬🇷 <tg-spoiler>{sentence_data['greek']}</tg-spoiler>
🇷🇺 <tg-spoiler>{sentence_data['russian']}</tg-spoiler>"""
    
    await callback.message.answer_voice(
        voice=audio_file,
        caption=caption,
        parse_mode="HTML",
        reply_markup=InlineKeyboards.practice_controls()
    )
    
    logger.info(f"Generated sentence for user {callback.from_user.id}")





@router.callback_query(F.data == "next_sentence")
async def next_sentence(callback: CallbackQuery, session: AsyncSession):
    """Generate next sentence."""
    await start_practice(callback, session)


@router.callback_query(F.data == "forgot_words")
async def forgot_words(callback: CallbackQuery, session: AsyncSession):
    """Show words from last sentence for adding to review."""
    sentence_repo = SentenceRepository(session)
    lesson_repo = LessonRepository(session)
    
    last_sentence = await sentence_repo.get_last_sentence(callback.from_user.id)
    
    if not last_sentence or not last_sentence.word_ids:
        await callback.answer("Нет слов для добавления")
        return
    
    words = await lesson_repo.get_words_by_ids(last_sentence.word_ids)
    
    text = """
❌ **Забыл слова?**

Выбери слова, которые хочешь добавить в повторение:
"""
    
    await callback.message.delete()
    await callback.message.answer(
        text,
        reply_markup=InlineKeyboards.word_selection(words)
    )
    await callback.answer()
