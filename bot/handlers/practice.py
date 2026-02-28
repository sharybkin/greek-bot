"""
Practice handler - main learning module.
"""

import random
from datetime import datetime, timedelta
from io import BytesIO
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.repositories.user_repo import UserRepository
from bot.database.repositories.lesson_repo import LessonRepository
from bot.database.repositories.sentence_repo import SentenceRepository
from bot.database.repositories.review_repo import ReviewRepository
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
    review_repo = ReviewRepository(session)
    
    user = await user_repo.get_by_telegram_id(callback.from_user.id)
    
    # Check if lessons are selected
    if not user.selected_lessons:
        text = "❌ Сначала выбери уроки для практики!"
        reply_markup = InlineKeyboards.back_to_menu()
        
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        else:
            await callback.message.answer(text, reply_markup=reply_markup)
            try:
                await callback.message.delete()
            except Exception:
                pass
        
        await callback.answer()
        return
    
    # Check generation limit for non-premium users
    can_generate, remaining = await user_repo.can_generate(callback.from_user.id)
    if not can_generate:
        text = (
            "⛔️ Лимит генераций исчерпан\n\n"
            "Ты использовал все 3 бесплатные генерации на сегодня.\n"
            "Попробуй завтра или обратись к администратору для получения Premium-доступа!"
        )
        reply_markup = InlineKeyboards.back_to_menu()
        
        if callback.message.text:
            await callback.message.edit_text(text, reply_markup=reply_markup)
        else:
            await callback.message.answer(text, reply_markup=reply_markup)
            try:
                await callback.message.delete()
            except Exception:
                pass
        
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
    lesson_words = await lesson_repo.get_words_by_lesson_ids(user.selected_lessons)
    
    if not lesson_words:
        await loading_msg.edit_text(
            "❌ В выбранных уроках нет слов!",
            reply_markup=InlineKeyboards.back_to_menu()
        )
        return
    
    # Get review words (limit 1 for now as per requirements)
    review_words_list = await review_repo.get_due_reviews(callback.from_user.id, limit=1)
    review_words = [rw.word for rw in review_words_list]

    # Get word statistics for LRU selection
    sentence_repo = SentenceRepository(session)
    word_usage = await sentence_repo.get_word_last_usage(callback.from_user.id)
    
    # Sort lesson words by last usage (None first, then oldest)
    # We assign a default very old date for never used words to safely sort
    never_used_date = datetime.min
    
    sorted_lesson_words = sorted(
        lesson_words,
        key=lambda w: word_usage.get(w.id, never_used_date)
    )

    # Determine how many mandatory words we need
    difficulty_word_count = {1: 3, 2: 6, 3: 10}
    target_count = difficulty_word_count.get(user.difficulty_level, 3)
    
    # Start mandatory list with review words
    mandatory_words = list(review_words)
    mandatory_ids = {w.id for w in mandatory_words}
    
    # Fill remaining mandatory slots from LRU list
    # Skip words already in mandatory list (e.g. if review word is also in lesson words)
    remaining_slots = max(0, target_count - len(mandatory_words))
    
    for word in sorted_lesson_words:
        if remaining_slots <= 0:
            break
        if word.id not in mandatory_ids:
            mandatory_words.append(word)
            mandatory_ids.add(word.id)
            remaining_slots -= 1
            
    # Check if system prompt cache is fresh (less than 1 day old)
    is_system_prompt_fresh = (
        user.system_prompt and 
        user.system_prompt_updated_at and 
        datetime.now() - user.system_prompt_updated_at < timedelta(days=1)
    )

    general_greek = []
    system_prompt_to_use = user.system_prompt

    # Extract existing words from cache if fresh
    if is_system_prompt_fresh and system_prompt_to_use:
        import re
        match = re.search(r'\[ (.*?) \]', system_prompt_to_use)
        if match:
            existing_words_str = match.group(1).strip()
            # The words in the prompt are comma separated
            general_greek = [w.strip() for w in existing_words_str.split(',')]

    existing_tokens = set(general_greek)
    
    # Find words we can add (up to 100 new context words)
    available_general = []
    for w in sorted_lesson_words:
        if w.id in mandatory_ids:
            continue
        if w.greek_word in existing_tokens:
            continue
        available_general.append(w)

    words_to_add = 100
    selected_new_general = random.sample(
        available_general,
        min(words_to_add, len(available_general))
    )
    new_general_greek = [w.greek_word for w in selected_new_general]
    
    # Prepare lists for AI
    mandatory_greek = [w.greek_word for w in mandatory_words]
    all_user_words_greek = [w.greek_word for w in lesson_words]

    if new_general_greek or not is_system_prompt_fresh:
        # We need to update the prompt
        general_greek.extend(new_general_greek)
        
        # We combine mandatory_greek and general_greek for the system prompt
        prompt_words = mandatory_greek + [g for g in general_greek if g not in mandatory_greek]
        
        system_prompt_to_use = ai_service.generate_system_prompt(
            all_words=prompt_words,
            plural=user.plural_enabled,
            tenses=user.tense_restriction,
            personal_pronouns=user.personal_pronouns_enabled,
            possessive_pronouns=user.possessive_pronouns_enabled,
            prepositions=user.prepositions_enabled,
            interrogative_words=user.interrogative_words_enabled
        )
        await user_repo.update_system_prompt_cache(callback.from_user.id, system_prompt_to_use)

    
    logger.info(f"User {callback.from_user.id} practice settings: plural={user.plural_enabled}, tenses={user.tense_restriction}")
    logger.info(f"Generating with Mandatory: {mandatory_greek}, Using System Prompt Cache: {is_system_prompt_fresh}")
    
    sentence_data = await ai_service.generate_sentence(
        review_words=mandatory_greek, 
        general_words=general_greek, 
        difficulty=user.difficulty_level,
        system_prompt=system_prompt_to_use,
        plural=user.plural_enabled,
        tenses=user.tense_restriction,
        personal_pronouns=user.personal_pronouns_enabled,
        possessive_pronouns=user.possessive_pronouns_enabled,
        prepositions=user.prepositions_enabled,
        interrogative_words=user.interrogative_words_enabled,
        all_user_words=all_user_words_greek
    )
    
    if not sentence_data:
        await loading_msg.edit_text(
            "❌ Не удалось сгенерировать предложение. Попробуй ещё раз.",
            reply_markup=InlineKeyboards.back_to_menu()
        )
        return
        
    # Process used words
    used_greek_words = sentence_data.get("used_greek_words", [])
    
    # Find word objects for used words
    # We check against ALL lesson words since general words can come from the cached prompt
    all_candidate_words = lesson_words
    used_word_objects = []
    used_review_ids = []
    
    # Normalize for comparison (simple case insensitive)
    used_greek_normalized = [w.lower().strip() for w in used_greek_words]
    
    # Track which mandatory words were actually used
    used_mandatory_ids = []

    for word in all_candidate_words:
        if word.greek_word.lower().strip() in used_greek_normalized:
            used_word_objects.append(word)
            # Check if this used word was a review word
            # We need to find the specific review entry for this word id
            for review_item in review_words_list:
                if review_item.word_id == word.id:
                    used_review_ids.append(review_item.id)
            
            if word.id in mandatory_ids:
                used_mandatory_ids.append(word.id)
    
    # Fallback if AI didn't return valid used words
    if not used_word_objects:
        logger.warning("AI didn't return valid used words, falling back to mandatory words")
        used_word_objects = mandatory_words
    
    # Update progress for review words that were used
    for review in review_words_list:
        if review.word_id in used_review_ids:
            await review_repo.update_review_progress(review.id, success=True)
    
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
    word_ids = [w.id for w in used_word_objects]
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
