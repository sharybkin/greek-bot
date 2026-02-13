"""
Spaced repetition algorithm implementation.
"""

from datetime import datetime, timedelta


class SpacedRepetition:
    """Spaced repetition algorithm for word review scheduling."""
    
    @staticmethod
    def calculate_next_review(review_count: int) -> datetime:
        """
        Calculate next review time based on review count.
        
        Args:
            review_count: Number of times word has been reviewed
            
        Returns:
            Datetime for next review
        """
        now = datetime.now()
        
        if review_count == 0:
            # First review: 1 hour
            return now + timedelta(hours=1)
        elif review_count == 1:
            # Second review: 4 hours
            return now + timedelta(hours=4)
        elif review_count == 2:
            # Third review: 1 day
            return now + timedelta(days=1)
        elif review_count == 3:
            # Fourth review: 3 days
            return now + timedelta(days=3)
        elif review_count == 4:
            # Fifth review: 7 days
            return now + timedelta(days=7)
        else:
            # After 5 reviews: word is mastered, review in 30 days
            return now + timedelta(days=30)
    
    @staticmethod
    def is_mastered(review_count: int) -> bool:
        """
        Check if word is mastered based on review count.
        
        Args:
            review_count: Number of times word has been reviewed
            
        Returns:
            True if word is mastered
        """
        return review_count >= 5
