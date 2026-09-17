# Requirements and source traceability

Sources: `Proposal complete.pdf` (41 physical pages, printed page numbers restart after the front matter) and `KaziForce_Proposal_Defense_slides.pptx` (12 slides). These were read as specifications supplied for this task. Literature-review descriptions of other systems are not implementation instructions.

## Technology decisions

The proposal §3.8 mentions Python, Django, PostgreSQL, NLTK, scikit-learn and HTML/CSS/JavaScript. Slide 8 explicitly selects the same stack and ESCO. Consequently, the implementation uses those technologies only, together with their supporting dependencies. The PostgreSQL driver psycopg is necessary to connect Django to PostgreSQL. PowerShell scripts provide setup automation on the user's Windows computer and are not an additional application service.

BERT, knowledge graphs, collaborative filtering and other literature-review approaches are not included. Slide 8 explicitly says no model training is performed. Fitting the TF-IDF vocabulary and IDF statistics is information retrieval, not supervised training. The user selected Neon as the online host for the PostgreSQL database.

## Feature mapping

| Requirement | Source | Implementation |
| --- | --- | --- |
| Registration and authentication | Proposal §1.6, §3.5.1 | Django authentication, candidate/recruiter registration, session login, logout and password change |
| Candidate profiles | Proposal §1.6, §3.6.1 | Headline, summary, skills, qualifications, certifications, experience, portfolio and location |
| Resume upload | Proposal §3.5.1, §3.6.2 | Private PDF/DOCX/TXT uploads, size and format checks, authorised downloads |
| Relevant text extraction | Proposal §1.6, §3.8.3 | TXT/DOCX extraction; conservative heading extraction; NLTK tokenisation, stopwords and lemmatisation |
| Job requirements | Proposal §1.6, §3.6.1 | Description, qualifications, certifications, experience and standardised skill requirements |
| Recruiter profile | Proposal §3.6.1 | Organisation name, website and description |
| Job posting management | Proposal §1.6; slide 7 | Create/edit postings; draft/open/closed states; deadlines; administrative moderation |
| ESCO skill and occupation standardisation | Slides 6–8 | Official concept URIs, labels and synonyms; English API downloader and CSV importer; occupation selection |
| TF-IDF + cosine similarity | Proposal §1.3, §2.5, §3.8.3; slides 4, 7–8 | scikit-learn TF-IDF and weighted cosine, documented formula |
| Recruiter priority weighting | Slides 6 and 8 | Per-skill priority 1–5, applied to weighted cosine |
| Compatibility scores | Proposal §1.3 and §3.7.2 | Bounded 0–100 similarity, strongest shared terms, saved results |
| Top 10 candidate rankings | Slide 6 | Up to 10 eligible profiles per posting, sorted by score with deterministic ties |
| Top 10 job recommendations | Slide 6 | Up to 10 open, unexpired roles per candidate |
| Skill-gap analysis | Proposal §1.3, §3.7.2; slides 6 and 11 | Recognised skills, missing requirements, essential flags and profile-improvement guidance |
| Application tracking | Slide 6 | Submit, review, shortlist, reject, hire, withdraw and timestamped history |
| Administration | Proposal §3.5.1; slide 7 | Django admin for users, jobs, profiles, taxonomy, result inspection and audit history |
| Persist match scores, rankings and gaps | Proposal §3.5.3, §3.6.1 | MatchResult per pair; rank and comparison context stored in explanation JSON |
| System documentation | Proposal §3.7.4; slide 11 | README, architecture, source traceability, user manual, Neon guide and evaluation protocol |
| Functional and integration tests | Proposal §3.7.5; slide 10 | Django tests on PostgreSQL, with a separate temporary test database |
| Matching accuracy, ranking quality, response time, gap accuracy | Slides 8 and 10 | Evaluation command accepting labelled data, producing measured metrics |
| UAT | Proposal §3.7.5; slides 8 and 10 | Reproducible participant task protocol; human acceptance results remain to be collected |
| Version control | Proposal §3.8.7 | Local Git repository and ignore rules; no GitHub publication or account access assumed |

## Decisions where the documents leave details open

- **Priorities:** The documents require weighting but provide no numeric scale or formula. This implementation uses 1–5 and weighted cosine. Essential flags are informational; scores never automatically reject candidates.
- **Profile visibility:** Candidates opt into discovery, or share their profile by applying. Recruiters can view an applicant to their own job even if general discovery is off. Withdrawal removes application-based access; an independent discovery opt-in still applies.
- **Resume formats:** No upload format or parser is mandated. TXT and DOCX work without an extra parsing package. PDF attachments are supported, but PDF text must be pasted into the matching field or represented in structured profile fields. OCR and automatic PDF extraction are not implemented.
- **Section extraction:** Heading rules detect explicit sections; they do not verify qualifications or infer missing facts. Candidates review and correct imported information.
- **ESCO release:** The API downloader explicitly requests v1.2.0. The importer can accept other official CSV releases when their version is supplied. Taxonomy records retain the selected version. Shorthand labels omit parenthetical qualifiers; ambiguous aliases are not matched automatically.
- **Language:** The matching prototype processes English using English NLTK resources and ESCO labels. Multilingual matching is not claimed.
- **Result lifetime:** A saved pair stores its latest calculation, including context and rank. It is not a historical experiment archive. Recommendation and recruiter-ranking scores can differ because IDF depends on the compared corpus. Each result page recalculates from current inputs.
- **UI:** No finished application wireframes were supplied; the proposal says they will be developed. The implementation uses an original responsive interface in HTML/CSS/JavaScript.
- **Deployment:** The database runs online on Neon. The Django web app runs locally for the controlled prototype. No public website deployment is implied.

## Explicit exclusions

Per proposal §1.6 and §1.7.2: no third-party recruitment-platform integration, psychometric or personality tests, video interview analysis, payroll, salary/performance prediction, full HR suite or automated hiring decision. These exclusions also apply to the demo.
