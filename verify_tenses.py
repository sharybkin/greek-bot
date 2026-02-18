
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from bot.services.ai_service import AIService
from bot.config import config

async def test_generation():
    print("Initializing AI Service...")
    service = AIService()
    
    review_words = ["γεια", "κόσμος"]
    general_words = ["και", "είναι", "ωραία"]
    
    print("\n--- Test 1: Present Tense ---")
    result = await service.generate_sentence(
        review_words, general_words, 
        difficulty=1, 
        plural=True, 
        tenses=["present"]
    )
    if result:
        print(f"Greek: {result['greek']}")
        print(f"Russian: {result['russian']}")
    else:
        print("Failed to generate.")

    print("\n--- Test 2: Past Tense ---")
    result = await service.generate_sentence(
        review_words, general_words, 
        difficulty=1, 
        plural=True, 
        tenses=["past"]
    )
    if result:
        print(f"Greek: {result['greek']}")
        print(f"Russian: {result['russian']}")
    else:
        print("Failed to generate.")

    print("\n--- Test 3: Multiple Tenses (Present + Future) ---")
    result = await service.generate_sentence(
        review_words, general_words, 
        difficulty=1, 
        plural=True, 
        tenses=["present", "future"]
    )
    if result:
        print(f"Greek: {result['greek']}")
        print(f"Russian: {result['russian']}")
    else:
        print("Failed to generate.")

if __name__ == "__main__":
    asyncio.run(test_generation())
