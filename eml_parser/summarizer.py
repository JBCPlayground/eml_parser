"""Extract key points from email content using extractive summarization."""

from sumy.nlp.stemmers import Stemmer
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
from sumy.summarizers.lsa import LsaSummarizer
from sumy.utils import get_stop_words

LANGUAGE = "english"
SENTENCES_COUNT = 3


def extract_key_points(text: str, sentence_count: int = SENTENCES_COUNT) -> list[str]:
    """Extract key sentences from text using LSA summarization."""
    if not text or len(text.strip()) < 100:
        # Text too short to summarize meaningfully
        return [text.strip()] if text.strip() else []

    try:
        parser = PlaintextParser.from_string(text, Tokenizer(LANGUAGE))
        stemmer = Stemmer(LANGUAGE)
        summarizer = LsaSummarizer(stemmer)
        summarizer.stop_words = get_stop_words(LANGUAGE)

        summary = summarizer(parser.document, sentence_count)
        return [str(sentence) for sentence in summary]
    except Exception as e:
        # Fallback: return first few sentences
        sentences = text.split(".")[:sentence_count]
        return [s.strip() + "." for s in sentences if s.strip()]


def summarize_email(text: str, max_sentences: int = 3) -> str:
    """Get a summary of email content as a single string."""
    key_points = extract_key_points(text, max_sentences)
    return " ".join(key_points)
