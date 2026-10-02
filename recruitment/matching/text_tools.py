import re
import unicodedata
from functools import lru_cache

import nltk
from django.conf import settings
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import RegexpTokenizer

nltk.data.path.insert(0, str(settings.BASE_DIR / 'nltk_data'))


class MatchingUnavailable(Exception):
    pass


def normalize(text):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text).casefold()).strip()


@lru_cache(maxsize=1)
def nlp_tools():
    try:
        words = set(stopwords.words('english'))
        lemma = WordNetLemmatizer()
        lemma.lemmatize('skills')
    except LookupError as exc:
        raise MatchingUnavailable(
            'Language resources are not installed. Run python manage.py setup_nlp.'
        ) from exc
    return words, lemma


def preprocess(text):
    words, lemma = nlp_tools()
    tokens = RegexpTokenizer(r'(?u)[\w][\w+#.]*').tokenize(normalize(text))
    return [
        lemma.lemmatize(lemma.lemmatize(token.rstrip('.'), 'v'))
        for token in tokens
        if token not in words and not token.isdigit()
    ]
