from enum import Enum

class CardRule(Enum):
    """Types of card rules for bring-in determination."""
    LOW_CARD = 'low card'          # Standard 7-Card Stud (Ace high, 2 low)
    LOW_CARD_AL = 'low card al'    # Unusual - low card bring-in (Ace low)
    HIGH_CARD = 'high card'        # For A-5 low games like Razz (King high, Ace low)
    HIGH_CARD_AH = 'high card ah'  # For 2-7 low games (Ace high, 2 low)
    HIGH_CARD_AH_WILD = 'high card ah wild'  # For games with high card bring-in with wild card, Ace high