# Opt-in official-source byte observations

Run `python -m phd_agents observe-sources --limit 8` or `--application APPLICATION_ID` locally. External HTTPS requests are **manual and opt-in**, not performed on startup, browsing, scheduled CI, or ordinary model inference. Confirm the relevant website's terms and crawling policy before running.

The observer selects previously reviewed, tracked records with HTTPS institutional source links. It rejects embedded credentials, query strings, redirects, insecure transports, localhost and non-global DNS results; inherited HTTP proxies are disabled. Request timeout is 15 seconds and response data is limited to 1 MB of HTML/plain text. No cookies, applicant data or API keys are sent. Raw website text is **not retained**. Only content hashes, status, timestamp, byte count, source link and application ID are recorded in owner-only SQLite, retaining up to 2,000 observations.

A first observation creates a baseline; a changed content hash raises `source_bytes_changed_needs_review`. A 403/404/redirect/timeout or unsupported response emits `unavailable_no_source_conclusion`, not an assertion that the university closed admissions. `GET /api/source-observations` lists recent private observations with no raw page content. Hash equality does not establish institutional source freshness or verified deadline. This is a byte-drift signal, **not a semantic deadline extractor**, automatic eligibility verifier, or admissions update.

The existing `compare-sources` command reports field-level differences between independently acquired JSON snapshots. For official deadline verification, an operator must still inspect the primary institution page and its effective date, capture evidence, and resolve differences manually. Do not copy private source observations into public Pages exports.

CI: `python -m pytest tests/test_phd_source_observer.py -q` uses a fake HTTPS transport; no real university URL is contacted in tests.


## Owner review decisions

The private runtime now supports **append-only source observation review notes** via `POST /api/source-observations/review`. A review references a specific immutable observation ID and expected content digest, accepts a bounded owner rationale, and records either `needs_follow_up` or `reviewed_no_fact_change`. Stale digest submissions are rejected. Changing a previously recorded decision creates a new audit event; duplicate sequential submissions are idempotent. The API does not alter an application deadline, mark eligibility, upload university source HTML, or certify institutional facts.

`GET /api/source-observations` includes the latest owner decision for each observation, but not the private rationale text. The UI retains outstanding changes across subsequent unchanged fetches. It considers only the bounded loaded history and cannot certify that older retained events were already reviewed. Source excerpt capture and official-claim semantic verification remain in [Issue #8](https://github.com/Armanasq/phd_tracker/issues/8).

## Review workspace

The private `#source-observations` route displays recent observations from `GET /api/source-observations`, one latest entry per tracked application/source URL. The saved `drift` classification is immutable for each observation; SQLite schema migration leaves historic classifications unknown rather than inventing a previous comparison outcome. Review categories are **changed bytes**, **unavailable**, **unchanged bytes**, **baseline**, or **legacy unknown**.

The UI offers manual history refresh and a command to perform another observation locally. It does **not** initiate network collection, store source HTML, authenticate university portals, or infer official deadline/eligibility changes. Data access remains limited to the loopback private API. The public Pages build does not have access to this history.

Remaining semantic proof requirements are tracked in [Issue #8](https://github.com/Armanasq/phd_tracker/issues/8).

## Exact-quote source evidence

The private `#source-claims` route now displays bounded, normalized visible source text collected by the existing HTTPS-only observer. Scripts, styles, SVGs, and template blocks are omitted; pages rendered by JavaScript and documents requiring authentication may not expose usable text. Every text observation retains its original byte SHA-256, a distinct normalized visible-text SHA-256 and a truncation indicator. A byte change with unchanged extracted text is still treated as **requiring manual source review**.

A candidate claim must identify the exact observation, its original byte digest, an exact 20–320-character quote found in the retained text, its claim category and a candidate value. The API rejects forged quotes, nonexistent observation identifiers and stale digests; duplicates resolve to the existing private claim record. The owner-only ledger never changes applicant status, deadline, eligibility or portal state, and it does not claim semantic truth from the source digest. Historical observations created before text capture are preserved with no invented text.

The following private, local-only endpoints support the workflow: `GET /api/source-observations/{id}/text`, `GET /api/source-claims` and `POST /api/source-claims/capture`. The captured body is limited to 24,000 normalized characters per observation and is not published to GitHub Pages. Sensitive institutional pages, PDFs and login-dependent portals require an independently authorized capture adapter and remain outside this workflow. This is not an admissions portal scraper or an automated application submitter.

## Agent retrieval semantics

A private agent now receives up to six captured source quotations when their application IDs match its selected or retrieved records. The bounded context explicitly marks each quote as `source_quote_observed_not_fact_verified`, with an immutable `SRC-<id>` citation identifier and raw source digest. When the model cites `[claim:SRC-123]`, the citation auditor may match the stored record but **must mark it unverified** until independent evidence review establishes the interpretation. The model cannot update source records, deadline fields or applicant statuses through citation. Returned run traces include source claim references, not the entire stored excerpt.

### Provenance retention

The observer keeps the newest **2,000 uncited** observations plus every observation referenced by a saved source claim or owner review event. Older uncited observations may be pruned; cited observations are exempt from this pruning so their captured source text and SHA-256 remain inspectable. The normal history API still returns at most 2,000 recent entries; older pinned observations are accessible through their exact private observation IDs and claim records. Export and back up the local SQLite state before destructive maintenance. This is not an unlimited retention guarantee for deleted databases or manual data modifications.

### Deterministic before/after source comparison

The private `GET /api/source-observations/{id}/diff` endpoint compares the selected fetched observation with the immediately previous fetched observation for the same application and HTTPS URL. The bounded word-level comparison includes additions, removals, replacements, limited context, possible lexical review topics and explicit completeness. Comparisons with missing or truncated text are partial or unavailable. The UI displays changes only on request. No model is called and no admission facts or applicant records are changed by the diff.

### Owner interpretation review

Owners can now attach a dated, append-only interpretation verdict to a captured source claim using `POST /api/source-claims/review`. The request requires both the stored source SHA-256 and quoted-text SHA-256 and a 30–1,500-character rationale. Supported verdicts: `needs_recheck`, `owner_interpretation_supported`, `owner_interpretation_rejected`. Later decisions append new audit events; exact immediate repeats are idempotent. The claim list includes only the latest owner decision timestamp, not private rationale text. All claim records retain `source_quote_observed_not_fact_verified`, even after owner assessment. The AI citation checker deliberately keeps such evidence **unverified**; no deadline, eligibility or admission status is silently modified.

The private `GET /api/source-claims/{id}/reviews` endpoint provides the dated, append-only owner-review history, including bounded rationale text, only when requested by the local owner. This history is not included in public Pages assets, model prompts or routine claim listings. The UI has a per-claim **Review history** control to inspect earlier verdicts; revised decisions preserve their predecessors.

### Deterministic candidate date parsing (private owner preview)

The private `GET /api/source-observations/{id}/candidates` endpoint proposes date *mentions* from the retained normalized visible source excerpt. It supports unambiguous ISO `YYYY-MM-DD` and English named-month forms (day-month-year and month-day-year), validates calendar dates, returns exact character offsets and a bounded source quotation, and flags multiple distinct deadline-like dates. Context detection is limited to the same source sentence; unrecognized locale-sensitive numeric formats, live portal state, other languages, document timezones and cutoff hours are **not guessed**. Scans are capped at 25 candidates and report source truncation/partial scan status. The `#source-claims` route displays provisional candidates and can *prefill* the manual capture form; reading or pre-filling a candidate never creates a source-claim row or modifies application state. Persisting a quote still requires explicit owner submission and source digest verification, and the resulting claim remains `source_quote_observed_not_fact_verified` even after review.

### Exact normalized-text source spans and migration

Captured source-claim records expose `schema_version=2`, the normalized visible-text SHA-256, exact quotation occurrence count, and a character span only when a quote appears **once**. Repeated quotations retain the digest but have `span_start=null`/`span_end=null` to avoid claiming an invented location. Legacy SQLite records migrate with missing text hashes/spans recorded as unknown. All records remain unverified candidate interpretations.
