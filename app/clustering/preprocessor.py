import re
import unicodedata


def preprocess(text):
    """Clean and normalize step operation text for embedding.

    Steps:
    1. Strip leading/trailing whitespace
    2. Collapse multiple spaces/tabs/newlines into single space
    3. Normalize full-width punctuation to half-width
    4. Remove step numbering prefix (e.g. "1. ", "1) ", "(1) ", "Step 1: ")
    5. Strip trailing periods/semicolons
    """
    if not text:
        return ""

    text = str(text).strip()

    # Normalize full-width chars to half-width (for punctuation)
    text = _normalize_punctuation(text)

    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove step numbering prefix
    # Handles: "1. ", "1) ", "(1) ", "(1)", "1、", "Step 1: " etc.
    text = re.sub(r'^[\(\（]?\d+[\)\）][\.\、:：\s]*', '', text).strip()
    text = re.sub(r'^\d+[\.\、:：\s]+', '', text).strip()
    text = re.sub(r'^[Ss]tep\s*\d+[\.\、:：\s]+', '', text, flags=re.IGNORECASE).strip()

    # Strip trailing punctuation
    text = re.sub(r'[;；。.]+$', '', text).strip()

    return text


def _normalize_punctuation(text):
    """Normalize common full-width punctuation to half-width."""
    replacements = {
        '，': ',',
        '；': ';',
        '：': ':',
        '（': '(',
        '）': ')',
        '！': '!',
        '？': '?',
        '【': '[',
        '】': ']',
        '｛': '{',
        '｝': '}',
    }
    for fw, hw in replacements.items():
        text = text.replace(fw, hw)

    # Normalize full-width digits/letters to half-width
    result = []
    for ch in text:
        cp = ord(ch)
        # Full-width ASCII range: 0xFF01 - 0xFF5E -> 0x0021 - 0x007E
        if 0xFF01 <= cp <= 0xFF5E:
            result.append(chr(cp - 0xFEE0))
        elif cp == 0x3000:  # Full-width space
            result.append(' ')
        else:
            result.append(ch)

    return ''.join(result)
