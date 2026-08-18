"""
Utility functions to detect special phrases in user answers.
Used to trigger interview flow changes (end interview, ask different question, etc.)
"""
import re


def is_pure_idk_answer(answer_text: str) -> bool:
    """
    Detect if answer is primarily 'I don't know' / 'idk' / similar phrases.
    Should be mostly just the idk phrase, not mixed with substantial content.
    
    Returns True if answer triggers early interview end.
    """
    if not answer_text or not answer_text.strip():
        return False
    
    # Normalize: lowercase, remove extra whitespace, remove punctuation
    normalized = answer_text.strip().lower()
    # Remove leading/trailing punctuation
    normalized = re.sub(r'^[\s\W]+|[\s\W]+$', '', normalized)
    
    # List of phrases that trigger end interview
    idk_phrases = [
        'idk',
        "i don't know",
        "i dont know",
        "don't know",
        "dont know",
        "dunno",
        "dunnit",
        "i have no idea",
        "no idea",
        "not sure",
        "i'm not sure",
        "im not sure",
        "can't answer",
        'cant answer',
        'cannot answer',
        'skip',
        'skip this',
        'skip question',
        'pass',
        'no clue',
        'beats me',
        'clueless',
    ]
    
    # Check if normalized answer matches any idk phrase
    for phrase in idk_phrases:
        # Match if it's the entire answer or just the phrase with minimal padding
        if normalized == phrase or normalized == phrase.strip():
            return True
        # Also match if it's very short (< 15 chars) and contains the phrase
        if len(normalized) < 15 and phrase in normalized:
            return True
    
    return False


def contains_different_question_request(answer_text: str) -> bool:
    """
    Detect if user is asking for a different question.
    
    Returns True if answer contains "ask different question" / "next question" etc.
    """
    if not answer_text or not answer_text.strip():
        return False
    
    normalized = answer_text.strip().lower()
    
    # List of phrases that trigger "ask different question"
    different_q_phrases = [
        'ask a different question',
        'ask different question',
        'different question',
        'ask another question',
        'another question',
        'next question',
        'change question',
        'different topic',
        'ask something else',
        'ask something different',
        'ask a new question',
        'new question',
        'can you ask another',
        'can you ask a different',
        'can you ask another question',
        'can you ask a different question',
    ]
    
    for phrase in different_q_phrases:
        if phrase in normalized:
            return True
    
    return False
