"""
SQLAlchemy models for Greek Learning Bot database.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import BigInteger, Integer, String, Text, Boolean, DateTime, Date, ARRAY, CheckConstraint, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Lesson(Base):
    """Lesson model."""
    __tablename__ = "lessons"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    order_number: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Relationships
    words: Mapped[List["Word"]] = relationship("Word", back_populates="lesson", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Lesson(id={self.id}, name='{self.name}')>"


class Word(Base):
    """Word model."""
    __tablename__ = "words"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    greek_word: Mapped[str] = mapped_column(String(200), nullable=False)
    russian_translation: Mapped[str] = mapped_column(String(300), nullable=False)
    lesson_id: Mapped[int] = mapped_column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Relationships
    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="words")
    
    def __repr__(self) -> str:
        return f"<Word(id={self.id}, greek='{self.greek_word}', russian='{self.russian_translation}')>"


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_lesson_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("lessons.id", ondelete="SET NULL"),
        nullable=True
    )
    selected_lessons: Mapped[List[int]] = mapped_column(JSONB, server_default="'[]'::jsonb")
    difficulty_level: Mapped[int] = mapped_column(
        Integer, 
        CheckConstraint("difficulty_level BETWEEN 1 AND 3"),
        default=1
    )
    is_premium: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_generation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_generation_reset: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Settings
    plural_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    tense_restriction: Mapped[List[str]] = mapped_column(JSONB, server_default='["present", "past", "future"]')  # List of allowed tenses
    
    # Extra settings
    personal_pronouns_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    possessive_pronouns_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    prepositions_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interrogative_words_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Cache
    system_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    system_prompt_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    review_words: Mapped[List["ReviewWord"]] = relationship(
        "ReviewWord", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    sentence_history: Mapped[List["SentenceHistory"]] = relationship(
        "SentenceHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    statistics: Mapped[List["UserStatistics"]] = relationship(
        "UserStatistics",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}')>"


class ReviewWord(Base):
    """Review word model for spaced repetition."""
    __tablename__ = "review_words"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE")
    )
    word_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("words.id", ondelete="CASCADE")
    )
    added_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="review_words")
    word: Mapped["Word"] = relationship("Word")
    
    # Indexes
    __table_args__ = (
        Index("idx_review_next", "user_telegram_id", "next_review_at"),
        Index("idx_user_word_unique", "user_telegram_id", "word_id", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<ReviewWord(id={self.id}, user_id={self.user_telegram_id}, word_id={self.word_id})>"


class SentenceHistory(Base):
    """Sentence history model."""
    __tablename__ = "sentence_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE")
    )
    greek_sentence: Mapped[str] = mapped_column(Text, nullable=False)
    russian_translation: Mapped[str] = mapped_column(Text, nullable=False)
    audio_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    difficulty_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    word_ids: Mapped[Optional[List[int]]] = mapped_column(ARRAY(Integer), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sentence_history")
    
    # Indexes
    __table_args__ = (
        Index("idx_sentence_user", "user_telegram_id", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<SentenceHistory(id={self.id}, user_id={self.user_telegram_id})>"


class UserStatistics(Base):
    """User statistics model."""
    __tablename__ = "user_statistics"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE")
    )
    date: Mapped[datetime] = mapped_column(Date, nullable=False)
    sentences_practiced: Mapped[int] = mapped_column(Integer, default=0)
    words_reviewed: Mapped[int] = mapped_column(Integer, default=0)
    new_words_learned: Mapped[int] = mapped_column(Integer, default=0)
    practice_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="statistics")
    
    # Indexes
    __table_args__ = (
        Index("idx_user_date", "user_telegram_id", "date", unique=True),
    )
    
    def __repr__(self) -> str:
        return f"<UserStatistics(id={self.id}, user_id={self.user_telegram_id}, date={self.date})>"
