"""Interpretable information retrieval; no supervised model or training dataset."""
import hashlib
import math
import re
import unicodedata
from functools import lru_cache
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import RegexpTokenizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from django.conf import settings
from django.db.models import Q, Exists, OuterRef, prefetch_related_objects
from django.utils import timezone
from .models import Application, CandidateProfile, Job, JobRequirement, MatchResult, Occupation, Skill

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
        raise MatchingUnavailable('Language resources are not installed. Run python manage.py setup_nlp.') from exc
    return words, lemma


def preprocess(text):
    words, lemma = nlp_tools()
    tokens = RegexpTokenizer(r'(?u)[\w][\w+#.]*').tokenize(normalize(text))
    return [lemma.lemmatize(lemma.lemmatize(t.rstrip('.'), 'v')) for t in tokens
            if t not in words and not t.isdigit()]


class Taxonomy:
    """Longest phrase matching through a token trie preserves C, C++, C# and R."""
    def __init__(self, skills, occupations=()):
        self.skills = {s.pk: s for s in skills}
        self.versions = sorted({s.version for s in self.skills.values()})
        self.trie = {}
        self.labels = {}
        for kind, items in [('skill', self.skills.values()), ('occupation', occupations)]:
            for item in items:
                marker = kind + '_' + hashlib.sha256(item.uri.encode()).hexdigest()[:20]
                self.labels[marker] = item.preferred_label
                # Parenthetical qualifiers in ESCO labels (e.g. Python (computer programming))
                # are removed for a shorthand alias. Ambiguity is handled below.
                shorthand = re.sub(r'\s*\([^)]*\)', '', item.preferred_label).strip()
                for alias in {item.preferred_label, shorthand, *item.alternative_labels.splitlines()}:
                    tokens = self.tokens(alias)
                    if not tokens:
                        continue
                    node = self.trie
                    for token in tokens:
                        node = node.setdefault(token, {})
                    # Identical aliases shared by concepts are ambiguous: don't invent a match.
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
        i = 0
        while i < len(tokens):
            node, end, found = self.trie, i, None
            while end < len(tokens) and tokens[end] in node:
                node = node[tokens[end]]
                end += 1
                if node.get(None):
                    found = (end, node[None])
            if found:
                end, (kind, pk, marker) = found
                output.append(marker)
                if kind == 'skill':
                    skill_ids.add(pk)
                i = end
            else:
                output.append(tokens[i])
                i += 1
        return preprocess(' '.join(output)), skill_ids

    def marker(self, skill):
        return 'skill_' + hashlib.sha256(skill.uri.encode()).hexdigest()[:20]


def open_jobs():
    return Job.objects.filter(status=Job.Status.OPEN, recruiter__is_active=True).filter(
        Q(deadline__isnull=True) | Q(deadline__gte=timezone.localdate()))


def eligible_profiles(job):
    applied = Application.objects.filter(candidate_id=OuterRef('user_id'), job=job).exclude(status='withdrawn')
    return CandidateProfile.objects.filter(user__is_active=True, user__role='candidate').annotate(
        applied_to_job=Exists(applied)).filter(Q(discoverable=True) | Q(applied_to_job=True)).select_related('user')


@lru_cache(maxsize=1)
def load_taxonomy():
    skills = list(Skill.objects.only('pk', 'uri', 'preferred_label', 'alternative_labels', 'version'))
    if not skills:
        raise MatchingUnavailable('The ESCO catalogue has not been imported. Ask the administrator to complete ESCO setup.')
    return Taxonomy(skills, Occupation.objects.all())


def clear_taxonomy_cache(*args, **kwargs):
    load_taxonomy.cache_clear()


class MatchingEngine:
    def __init__(self):
        # The read-only ESCO trie is reused. Candidate and job data is always fresh.
        self.taxonomy = load_taxonomy()

    def rank(self, jobs, profiles, persist=True, ranking_context='candidate ranking'):
        jobs, profiles = list(jobs), list(profiles)
        if not jobs or not profiles:
            return []
        prefetch_related_objects(jobs, 'occupation')
        prefetch_related_objects(profiles, 'user')
        # One query for all jobs, including when callers pass plain model lists.
        # Fetch fresh requirements on each ranking so edited priorities take effect.
        requirements_by_job = {job.pk: {} for job in jobs}
        for req in JobRequirement.objects.filter(job__in=jobs).select_related('skill'):
            requirements_by_job[req.job_id][req.skill_id] = (req.skill, req.priority, req.essential)
        profile_data = [self.taxonomy.extract(p.matching_text()) for p in profiles]
        job_data, requirements = [], []
        for job in jobs:
            tokens, inferred = self.taxonomy.extract(job.matching_text())
            reqs = requirements_by_job[job.pk]
            for pk in inferred:
                reqs.setdefault(pk, (self.taxonomy.skills[pk], 1, False))
            tokens = list(tokens)
            for skill, _, _ in reqs.values():
                marker = self.taxonomy.marker(skill)
                if marker not in tokens:
                    tokens.append(marker)
            if job.occupation_id:
                tokens += self.taxonomy.extract(job.occupation.preferred_label)[0]
            job_data.append(tokens)
            requirements.append(reqs)
        corpus = [data[0] for data in profile_data] + job_data
        if any(corpus):
            vectorizer = TfidfVectorizer(analyzer=lambda document: document, sublinear_tf=True)
            vectors = vectorizer.fit_transform(corpus)
            features = vectorizer.get_feature_names_out()
        else:
            vectors, features = None, []
        results = []
        for j, job in enumerate(jobs):
            reqs = requirements[j]
            if vectors is not None:
                # Multiplying BOTH vectors by sqrt(priority) gives weighted cosine.
                weights = [1.0] * len(features)
                priority = {self.taxonomy.marker(s): w for s, w, _ in reqs.values()}
                for n, feature in enumerate(features):
                    weights[n] = math.sqrt(priority.get(feature, 1))
                candidates = vectors[:len(profiles)].multiply(weights).tocsr()
                target = vectors[len(profiles) + j].multiply(weights).tocsr()
                scores = cosine_similarity(candidates, target).ravel()
            for i, profile in enumerate(profiles):
                score = max(0.0, min(100.0, float(scores[i]) * 100)) if vectors is not None else 0.0
                matched, missing = [], []
                for pk, (skill, weight, essential) in reqs.items():
                    detail = {'label': skill.preferred_label, 'uri': skill.uri, 'priority': weight, 'essential': essential}
                    (matched if pk in profile_data[i][1] else missing).append(detail)
                top_terms = []
                if vectors is not None:
                    overlap = candidates[i].multiply(target).tocoo()
                    top_terms = [{'term': self.taxonomy.labels.get(features[n], features[n]), 'weight': round(float(v), 5)}
                                 for n, v in sorted(zip(overlap.col, overlap.data), key=lambda x: -x[1])[:8]]
                explanation = {'method': 'NLTK + ESCO + weighted TF-IDF cosine', 'top_terms': top_terms,
                               'corpus_size': len(corpus), 'profile_updated': profile.updated_at.isoformat(),
                               'job_updated': job.updated_at.isoformat(), 'esco_versions': self.taxonomy.versions,
                               'note': 'Similarity is a decision-support score, not a probability of hiring. Missing skills mean no evidence found in the supplied text.'}
                values = {'score': round(score, 2), 'matched_skills': matched, 'missing_skills': missing, 'explanation': explanation}
                results.append({'candidate': profile, 'job': job, **values})
        results.sort(key=lambda r: (-r['score'], r['job'].pk, r['candidate'].pk))
        ranks, snapshots = {}, []
        for result in results:
            group = result['candidate'].pk if ranking_context == 'job recommendations' else result['job'].pk
            ranks[group] = ranks.get(group, 0) + 1
            result['explanation']['rank'] = ranks[group]
            result['explanation']['ranking_context'] = ranking_context
            if persist:
                snapshots.append(MatchResult(candidate=result['candidate'].user, job=result['job'],
                    **{key: result[key] for key in ['score', 'matched_skills', 'missing_skills', 'explanation']}))
        if snapshots:
            MatchResult.objects.bulk_create(snapshots, update_conflicts=True, unique_fields=['candidate', 'job'],
                update_fields=['score', 'matched_skills', 'missing_skills', 'explanation', 'calculated_at'], batch_size=500)
        return results

    def candidates(self, job):
        return self.rank([job], eligible_profiles(job))[:10]

    def recommendations(self, profile):
        return self.rank(open_jobs().select_related('occupation'), [profile], ranking_context='job recommendations')[:10]
