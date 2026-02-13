"""
Google Cloud Text-to-Speech service.
"""

import hashlib
import os
from pathlib import Path
from typing import Optional
from google.cloud import texttospeech
from bot.config import config
from bot.utils.logger import logger


class TTSService:
    """Service for text-to-speech using Google Cloud TTS."""
    
    def __init__(self):
        """Initialize Google Cloud TTS client."""
        # Set credentials path
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = config.google_credentials_path
        self.client = texttospeech.TextToSpeechClient()
        
        # Audio cache directory
        self.cache_dir = Path("/app/audio_cache")
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        
        # TTS configuration
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="el-GR",
            name="el-GR-Standard-A",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.85,  # Slower for learning
            pitch=0.0
        )
    
    def _get_cache_path(self, text: str) -> Path:
        """
        Get cache file path for given text.
        
        Args:
            text: Greek text to hash
            
        Returns:
            Path to cache file
        """
        text_hash = hashlib.md5(text.encode()).hexdigest()
        return self.cache_dir / f"{text_hash}.mp3"
    
    async def synthesize(self, text: str) -> Optional[bytes]:
        """
        Synthesize speech from text.
        
        Args:
            text: Greek text to synthesize
            
        Returns:
            Audio content as bytes or None if failed
        """
        if not text:
            logger.error("No text provided for TTS")
            return None
        
        # Check cache
        cache_path = self._get_cache_path(text)
        if cache_path.exists():
            logger.info(f"Using cached audio for: {text[:50]}...")
            with open(cache_path, "rb") as f:
                return f.read()
        
        try:
            logger.info(f"Generating TTS for: {text[:50]}...")
            
            # Prepare synthesis input
            synthesis_input = texttospeech.SynthesisInput(text=text)
            
            # Perform TTS request
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=self.voice,
                audio_config=self.audio_config
            )
            
            # Cache the audio
            with open(cache_path, "wb") as f:
                f.write(response.audio_content)
            
            logger.info(f"Successfully generated and cached TTS audio")
            return response.audio_content
            
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None
