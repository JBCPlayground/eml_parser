"""Extract key points from email content using extractive summarization."""

import re

from sumy.nlp.stemmers import Stemmer
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer
from sumy.utils import get_stop_words

LANGUAGE = "english"
SENTENCES_COUNT = 3

# Patterns that contain periods but shouldn't be split as sentences
PROTECTED_PATTERNS = [
    (r'v(\d+)\.(\d+)\.(\d+)', r'v\1_DOT_\2_DOT_\3'),  # Version numbers: v0.52.40
    (r'(\d+)\.(\d+)\.(\d+)', r'\1_DOT_\2_DOT_\3'),     # Version numbers: 0.52.40
    (r'(\d+)\.(\d+)', r'\1_DOT_\2'),                   # Decimal numbers: 3.14
    (r'([A-Za-z])\.([A-Za-z])\.', r'\1_DOT_\2_DOT_'),  # Initials: U.S., e.g.
    (r'\.\.\.', '_ELLIPSIS_'),                         # Ellipsis
]


def _protect_periods(text: str) -> str:
    """Replace periods in version numbers and decimals with placeholders."""
    for pattern, replacement in PROTECTED_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text


def _restore_periods(text: str) -> str:
    """Restore protected periods back to normal."""
    return text.replace('_DOT_', '.').replace('_ELLIPSIS_', '...')


def extract_key_points(text: str, sentence_count: int = SENTENCES_COUNT) -> list[str]:
    """Extract key sentences from text using LSA summarization."""
    if not text or len(text.strip()) < 100:
        # Text too short to summarize meaningfully
        return [text.strip()] if text.strip() else []

    # Protect version numbers and decimals from being split as sentences
    protected_text = _protect_periods(text)

    try:
        parser = PlaintextParser.from_string(protected_text, Tokenizer(LANGUAGE))
        stemmer = Stemmer(LANGUAGE)
        summarizer = LsaSummarizer(stemmer)
        summarizer.stop_words = get_stop_words(LANGUAGE)

        summary = summarizer(parser.document, sentence_count)
        # Restore protected periods in the output
        return [_restore_periods(str(sentence)) for sentence in summary]
    except Exception:
        # Fallback: return first few sentences
        sentences = text.split(".")[:sentence_count]
        return [s.strip() + "." for s in sentences if s.strip()]


def summarize_email(text: str, max_sentences: int = 3) -> str:
    """Get a summary of email content as a single string."""
    key_points = extract_key_points(text, max_sentences)
    return " ".join(key_points)
