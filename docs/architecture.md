# Architecture and implementation

## Three-tier architecture

```text
Candidate / Recruiter / Administrator
                 |
HTML, CSS, JavaScript + Django templates
                 |
Django views, forms, authentication and permissions
                 |
MatchingEngine: NLTK -> ESCO -> TF-IDF -> weighted cosine
                 |
Django ORM -> psycopg -> TLS -> Neon PostgreSQL
```

The production application dependencies are in `requirements.txt`. There is no REST framework, frontend build chain, external model service or alternative database. Django's admin is the administrator interface.

## Domain model and database relationships

| Entity | Relationships and purpose |
| --- | --- |
| User | Django AbstractUser extension; candidate/recruiter role; staff/superuser administration |
| CandidateProfile | One-to-one User; profile fields and private resume reference |
| RecruiterProfile | One-to-one User; organisation details |
| Skill | Unique ESCO URI, preferred/alternative labels, description and version |
| Occupation | Unique ESCO URI and labels; optionally linked to Job |
| Job | Belongs to one recruiter; description, status and deadline |
| JobRequirement | Links Job and Skill, unique per pair; priority 1–5 and essential flag |
| Application | Links candidate and job, unique per pair; current status and cover note |
| ApplicationEvent | Belongs to Application; actor, status and timestamp |
| MatchResult | Candidate-job pair; score, skills, gaps and explanation JSON including rank/context |

`recruitment/models.py` and `recruitment/migrations/0001_initial.py` are the executable schema. Referential integrity and uniqueness are enforced by PostgreSQL. JobRequirement includes a database-level priority range constraint. Skill deletion is protected when requirements reference it. The profile's qualifications/certifications/experience are editable text fields because the source does not specify separate record schemas.

These entities and relationships provide the content for the proposal's Miro ERD/class diagrams. The actors and flows below provide the use-case, activity and sequence-diagram content. No claim is made that a Miro board has been created.

## Matching algorithm

1. Read the candidate's professional information and the job description, qualifications, certifications and experience. Exclude structured identity/contact/location fields and remove recognised name/contact/location text from the matching input. This is not a complete de-identification system for arbitrary prose.
2. Normalise Unicode, case and whitespace. Match the longest known ESCO label or synonym using a token trie. Replace recognised concepts with stable URI-derived feature tokens. Parenthetical qualifiers are removed for shorthand aliases, while ambiguous shared aliases are skipped. Occupation phrases can also be normalised.
3. Apply NLTK tokenisation, English stopword removal and WordNet lemmatisation. Technical punctuation in ESCO labels such as C++ and C# is preserved during concept recognition.
4. Merge recruiter-selected skill requirements with skills recognised in the job text. Inferred skills receive priority 1 and are not marked essential. Explicit priorities override them.
5. Use scikit-learn `TfidfVectorizer`, with sublinear term frequency and default smoothed IDF, on all documents in the comparison. Each document is already tokenised. No supervised model is trained.
6. Apply a weight of 1 to ordinary features and the recruiter's priority to the corresponding skill feature. Multiply both candidate and job vectors by the square root of each weight, then calculate cosine similarity.
7. Multiply by 100, bound to [0, 100], and round to two decimals. Empty vectors and no overlap return zero.
8. Report the intersection of identified candidate skills and job requirements, and the required skills for which no candidate evidence was found. Rank by score descending, then stable IDs for ties. Display at most 10 results.
9. Persist the latest result, including rank, context, source timestamps, ESCO versions, corpus size and strongest shared terms. Bulk upserts avoid an individual network round-trip per result.

For candidate vector `c`, job vector `j`, and feature priorities `w`:

```text
score = 100 × Σ(w_i c_i j_i)
              ---------------------------------------
              sqrt(Σ(w_i c_i²)) × sqrt(Σ(w_i j_i²))
```

Increasing a priority makes that skill more influential in both the numerator and norms. It does not guarantee that every candidate's score increases. Missing essential skills remain visible and do not trigger automated rejection.

IDF is corpus-dependent. A candidate's recommendation run compares that profile with currently open, unexpired jobs. A recruiter's candidate run compares a job with eligible candidates. These are different corpora. The single-job candidate detail uses the recommendation corpus so its score agrees with that recommendation run when data has not changed.

The approach recognises vocabulary equivalence available in ESCO and overlaps in normalised text. It is not deep semantic reasoning, evidence verification, proficiency measurement, or negation reasoning. A statement such as “no experience in Python” may still contain a recognised Python term. That limitation must be included when discussing research validity.

The read-only ESCO trie is cached within each Python process to avoid repeatedly downloading and rebuilding the full catalogue. Saving or deleting taxonomy concepts through Django invalidates that process's cache. Restart running web-server processes after command-line imports or out-of-process catalogue changes. Job descriptions, profiles, applications and priorities are not cached. NLTK language resources also remain loaded after first use, so a cold process is slower than subsequent requests.

## Application sequence

```text
Candidate submits application form
  -> Django authenticates the user and checks CSRF
  -> Locks the job row within a PostgreSQL transaction
  -> Checks job status/deadline and required profile fields
  -> Creates the unique candidate-job application and initial event
  -> Redirects to the application timeline

Recruiter changes an application status
  -> Checks ownership of the application's job
  -> Locks the application and validates the transition
  -> Saves the new status and timestamped actor event atomically
```

Allowed recruiter transitions: submitted → reviewing/shortlisted/rejected; reviewing → shortlisted/rejected; shortlisted → hired/rejected. The candidate can withdraw while submitted, reviewing or shortlisted. Terminal states are not silently reopened. Hiring status is set by the recruiter, never by the matching engine.

## Access and storage

Django sessions, CSRF protection, password validators and production password hashing are used. Public registration cannot grant staff status. Profile/job forms exclude ownership fields; ownership is assigned server-side. Recruiters can only edit their own jobs or statuses. Another candidate cannot access a resume. Files use random storage names and are served as attachments through an authenticated, permission-checked endpoint. The media directory is never mapped to a public development URL.

The CSV ranking exporter neutralises spreadsheet formula prefixes in user-controlled text. Templates escape user text. Portfolio URLs are validated by Django. Online PostgreSQL URLs require TLS. Settings, uploaded resumes, cached downloads and demo credentials are excluded from Git.

## Development organisation

The code separates persistence (`models.py`), validation (`forms.py`), request handling (`views.py`), matching (`matching.py`), templates and static assets. Django management commands perform ESCO import, NLTK setup, database checks, demo seeding and research evaluation. The proposal's Scrum sequence can be reviewed through those delivered increments; this build does not invent historical sprint meetings or supervisor acceptance.
