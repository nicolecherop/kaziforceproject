# Testing and evaluation report

## Scope and environment

The implemented capstone was checked using Python 3.13.5, Django 5.2.17, psycopg 3.3.5, NLTK 3.10.3, scikit-learn 1.9.0 and Neon PostgreSQL 18.6. The web interface is Django templates with plain HTML/CSS/JavaScript. Automated tests use synthetic taxonomy/profile fixtures and a separate PostgreSQL database. No SQLite test substitute is used.

Actual command output is retained privately under `.local/verification-*.txt`. Reproduce the complete current suite with:

```powershell
.venv\Scripts\python.exe scripts/verify.py
```

## Executed checks

| Check | Result |
| --- | --- |
| Neon connection | Successful; client TLS enabled |
| Initial database migration | Completed |
| Core regression suite | 34 tests passed in 226.211 seconds; exit code 0 |
| Test database cleanup | Successful using the direct Neon endpoint |
| Migration consistency | No changes detected |
| Django system check | No issues |
| Supplemental management/resume-link regressions | 3 tests passed in 25.276 seconds; exit code 0 |
| Matching/cache regressions after performance update | 13 tests passed in 69.454 seconds, including 2 new cache tests; exit code 0 |
| Real-database page smoke checks | 16 page/export/admin checks returned HTTP 200 with the full catalogue |
| Actual localhost HTTP authentication | Candidate and recruiter login/logout passed with CSRF tokens and session cookies |
| Actual matching HTTP requests after cache update | First recommendations request 28.429 s; warm recommendations 8.056 s; warm ranking 4.664 s |
| Python and JavaScript syntax checks | Passed |
| Browser visual review | Not performed: no connected browser was available |
| Human user acceptance testing | Not performed; protocol below |
| Human-labelled matching accuracy | Not measured; evaluation tool below |

The initial 31-test run passed its assertions but failed during database cleanup because a pooled Neon session kept the temporary database open. The test configuration now uses the direct Neon endpoint. The temporary database from that initial run was removed; subsequent test cleanup completed normally. The application continues to use the pooled endpoint.

After the simplification update, the complete suite contains 40 tests. On 17 September 2026, all 40 passed in 246.486 seconds; test-database cleanup, migration consistency and Django system checks also passed. The additional test verifies that ranking five jobs performs just one requirements query, rather than one per job. The existing priority-change test confirms that freshly edited priorities still affect results. Current full-suite output is in `.local/verification-tests.txt`. Earlier supplemental logs remain in `.local/verification-management.txt` and `.local/verification-regression.txt`.

The repository also contains `.github/workflows/ci.yml`. On every push to `main` or `master` and on every pull request, it creates an isolated PostgreSQL service, installs `requirements-lock.txt`, prepares the NLTK resources and runs `scripts/verify.py`. This local verification confirms the commands used by that workflow; the hosted workflow status becomes available after the repository is pushed to GitHub.

The original database-backed smoke check confirmed 13,939 ESCO skills and 3,039 occupations from the explicitly requested v1.2.0 API dataset. Its historical report is `.local/smoke-results.json`; the duplicate smoke script was removed during simplification because page rendering is covered by the test suite. Actual HTTP authentication and matching can be checked with `scripts/live_http_check.py`, which writes `.local/live-http-results.json`. These are single-run prototype measurements on this computer's connection to the selected US-region Neon endpoint, not load-test results or a latency guarantee. The first matching request loads NLTK and ESCO resources. Subsequent requests reuse those resources while fetching current candidate/job data.

The cleanup reduced the existing database from 15 to 6 users, 13 to 4 candidate profiles, 4 to 2 jobs and 4 to 1 applications. This retains three fictional candidates, the demo recruiter, administrator and the owner's account. Unused demo-related match snapshots were removed through foreign-key cascades; normal matching requests regenerate current snapshots. Required tables and the complete ESCO catalogue were preserved. A validated UTF-8 compressed database fixture was saved privately before deletion in `.local/backups/before-simplification.json.gz`.

## Covered behaviours

- Identical input gives 100% similarity; empty or unrelated input safely returns zero.
- ESCO aliases share a canonical feature, Java does not spuriously match JavaScript, and C/C++/C#/R remain distinct.
- Increasing different recruiter skill priorities changes candidate ordering in the expected direction.
- Rankings stop at 10; recommendations exclude drafts, closed jobs and expired jobs.
- NLTK removes stopwords and lemmatises terms.
- Registration cannot grant staff or superuser status; emails are normalised and duplicate registration is rejected.
- Candidates cannot create jobs, and recruiters cannot manage another recruiter's postings or applications.
- Public discovery and applicant consent determine profile access; withdrawal removes application-based access.
- Duplicate applications create one application and one initial event.
- Status transitions enforce actor permissions and preserve timestamped history.
- CSRF and HTTP-method checks protect state changes; rendered user text is escaped.
- Job creation persists its owner and priority requirements from the submitted form.
- Catalogue search requires authentication and returns synonyms.
- TXT/DOCX resume extraction and section identification work; invalid or oversized uploads are rejected.
- Other candidates cannot download a private resume.
- Candidate and recruiter pages render successfully through Django's HTTP test client.

Supplemental tests cover updating ESCO concepts without breaking job requirements, calculating metrics from supplied labels, and rendering a private resume-download link rather than a public storage URL.

## Research evaluation protocol

Use multiple independent reviewers to label candidate-job pairs where possible. Record how disagreements were resolved. Do not treat the automatically generated demo examples as evidence of real-world accuracy.

Create a CSV with `job_id,candidate_id,relevance,missing_skill_uris`. Relevance grades range from 0 (irrelevant) to 3 (highly relevant). Use `|` between expected missing ESCO concept URIs, or `[]` for none. Include relevant and irrelevant candidates; aiming for at least 10 labelled candidates per job makes top-10 measures easier to interpret.

```powershell
.venv\Scripts\python.exe manage.py evaluate_matching data/evaluation-labels.csv --threshold 50
```

The command writes `docs/evaluation-results.json` with:

| Metric | Definition |
| --- | --- |
| Threshold accuracy | Fraction of supplied pairs whose thresholded score agrees with relevance > 0 |
| Precision@10 | Relevant results among the top 10, divided by 10 even if the labelled pool has fewer than 10 |
| NDCG@10 | Discounted graded relevance normalised by the ideal top-10 ordering; 0 if no relevant result exists |
| Skill-gap micro-F1 | Aggregate agreement between predicted and labelled missing-skill URI sets; 1 if both have no gaps throughout |
| Response time | Wall-clock time for ranking the supplied pool, excluding initial engine construction and persistence |

The threshold is configurable and is not an application hiring rule. Record the chosen threshold before inspecting final evaluation results. Report corpus size and taxonomy version, because scores depend on the comparison corpus. The command evaluates only the supplied labelled candidate pool. It does not claim performance over unlabelled candidates or establish fairness across demographic groups.

The separate real-database smoke report times complete Django request handling for demo pages. These timings include database queries and, for matching pages, matching setup and persistence. They are different measurements from the evaluation command and should not be compared as if they were identical.

## User acceptance testing sheet

Ask actual candidate and recruiter participants to perform the following tasks. Record participant code, completion, elapsed time, difficulty (1–5), comments and any defect. Obtain appropriate permission before collecting participant data. Mark pass/fail from observation rather than anticipated behaviour.

| ID | Actor | Task | Expected outcome | Observed result |
| --- | --- | --- | --- | --- |
| UAT-01 | Candidate | Register and sign in | Candidate overview appears | Not run |
| UAT-02 | Candidate | Complete profile and attach TXT/DOCX resume | Saved fields and extracted text can be reviewed | Not run |
| UAT-03 | Candidate | Attach PDF and enter matching text | Resume downloads privately; supplied text is used | Not run |
| UAT-04 | Candidate | Inspect recommendations and explanation | Up to 10 open roles; recognised skills and gaps visible | Not run |
| UAT-05 | Candidate | Apply twice to a role | One application with initial history event | Not run |
| UAT-06 | Candidate | Withdraw an active application | Status and history show withdrawal | Not run |
| UAT-07 | Recruiter | Create job and search ESCO skills | Posting and priorities persist | Not run |
| UAT-08 | Recruiter | Compare rankings before/after priority change | Ranking reflects changed weighting | Not run |
| UAT-09 | Recruiter | Inspect candidate and download ranking | Allowed profile and CSV are available | Not run |
| UAT-10 | Recruiter | Shortlist an applicant | Candidate sees updated status/history | Not run |
| UAT-11 | Recruiter | Close a posting | New applications stop; existing history stays | Not run |
| UAT-12 | Administrator | Moderate job and deactivate test user | Administrative changes take effect | Not run |
| UAT-13 | Both | Use mobile-width interface | Forms, navigation and result details remain usable | Not run |

## Known limits relevant to the defence

This is a controlled information-retrieval prototype. ESCO helps with known terminology but does not provide unrestricted semantic understanding. Negated statements, unsupported claims and unusual language can still affect matching. Qualifications and experience are supplied evidence, not externally verified facts. PDF text extraction and OCR are not included. Human accuracy evaluation and UAT remain research activities for the project owner. No empirical accuracy percentage or user acceptance result has been fabricated.
