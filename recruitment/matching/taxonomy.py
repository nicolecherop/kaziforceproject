import hashlib
import re
from functools import lru_cache

from ..models import Occupation, Skill
from .text_tools import MatchingUnavailable, normalize, preprocess


class Taxonomy:
    """Longest phrase matching through a token trie preserves C, C++, C# and R."""

    def __init__(self, skills, occupations=()):
        self.skills = {skill.pk: skill for skill in skills}
        self.versions = sorted({skill.version for skill in self.skills.values()})
        self.trie = {}
        self.labels = {}
        for kind, items in [('skill', self.skills.values()), ('occupation', occupations)]:
            for item in items:
                marker = kind + '_' + hashlib.sha256(item.uri.encode()).hexdigest()[:20]
                self.labels[marker] = item.preferred_label
                shorthand = re.sub(r'\s*\([^)]*\)', '', item.preferred_label).strip()
                for alias in {
                    item.preferred_label,
                    shorthand,
                    *item.alternative_labels.splitlines(),
                }:
                    tokens = self.tokens(alias)
                    if not tokens:
                        continue
                    node = self.trie
                    for token in tokens:
                        node = node.setdefault(token, {})
                    value = (kind, item.pk, marker)
                    if None in node and node[None] != value:
                        node[None] = False
                    else:
                        node[None] = value

    @staticmethod
    def tokens(text):
        return re.findall(r'[\w]+(?:\+\+|#)?(?:\.[\w]+)*|[^\w\s]', normalize(text))

    def extract(self, text):
        tokens = self.tokens(text)
        output, skill_ids = [], set()
        index = 0
        while index < len(tokens):
            node, end, found = self.trie, index, None
            while end < len(tokens) and tokens[end] in node:
                node = node[tokens[end]]
                end += 1
                if node.get(None):
                    found = (end, node[None])
            if found:
                end, (kind, primary_key, marker) = found
                output.append(marker)
                if kind == 'skill':
                    skill_ids.add(primary_key)
                index = end
            else:
                output.append(tokens[index])
                index += 1
        return preprocess(' '.join(output)), skill_ids

    def marker(self, skill):
        return 'skill_' + hashlib.sha256(skill.uri.encode()).hexdigest()[:20]


@lru_cache(maxsize=1)
def load_taxonomy():
    skills = list(
        Skill.objects.only('pk', 'uri', 'preferred_label', 'alternative_labels', 'version')
    )
    if not skills:
        raise MatchingUnavailable(
            'The ESCO catalogue has not been imported. Ask the administrator to complete ESCO setup.'
        )
    return Taxonomy(skills, Occupation.objects.all())


def clear_taxonomy_cache(*args, **kwargs):
    load_taxonomy.cache_clear()
