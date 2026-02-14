"""
Google Cloud Text-to-Speech service.
"""

import os
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
        
        # TTS configuration
        self.voice = texttospeech.VoiceSelectionParams(
            language_code="el-GR",
            name="el-GR-Chirp3-HD-Aoede",
            ssml_gender=texttospeech.SsmlVoiceGender.FEMALE
        )
        
        self.audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.85,  # Slower for learning
            pitch=0.0
        )
    
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
            
            logger.info(f"Successfully generated TTS audio")
            return response.audio_content
            
        except Exception as e:
            logger.error(f"Error generating TTS: {e}")
            return None
