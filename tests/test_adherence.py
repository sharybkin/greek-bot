
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.getcwd())

from bot.services.ai_service import AIService
from bot.config import config

async def test_adherence():
    print("Initializing AI Service...")
    service = AIService()
    
    # Test cases: (mandatory_words, difficulty)
    test_cases = [
        (["γεια", "κόσμος"], 1),        # 3-5 words
        (["σήμερα", "μου", "αρέσει"], 2), # 6-9 words
        (["θέλω", "να", "μάθω", "τη", "γλώσσα", "αυτή", "πολύ"], 3) # 10-15 words
    ]
    
    for i, (mandatory, diff) in enumerate(test_cases, 1):
        print(f"\n--- Test {i}: Adherence (Difficulty {diff}) ---")
        print(f"Mandatory: {mandatory}")
        
        result = await service.generate_sentence(
            mandatory, 
            general_words=["και", "είναι", "ωραία", "ελληνική", "γλώσσα", "μαθαίνω"], 
            difficulty=diff
        )
        
        if result:
            greek = result['greek']
            russian = result['russian']
            used = result.get('used_greek_words', [])
            word_count = len(greek.split())
            
            # Get boundaries
            word_count_map = {1: (3, 5), 2: (6, 9), 3: (10, 15)}
            min_w, max_w = word_count_map.get(diff, (3, 5))
            
            print(f"Greek: {greek}")
            print(f"Russian: {russian}")
            print(f"Word count: {word_count} (Expected {min_w}-{max_w})")
            
            # Check length
            if min_w <= word_count <= max_w:
                print("✅ Length OK")
            else:
                print("❌ Length FAILURE")
                
            # Check mandatory words (simple check)
            missing = [w for w in mandatory if w.lower().strip() not in greek.lower()]
            if not missing:
                print("✅ Mandatory words OK")
            else:
                print(f"❌ Missing mandatory words: {missing}")
        else:
            print("❌ Failed to generate.")

if __name__ == "__main__":
    asyncio.run(test_adherence())
