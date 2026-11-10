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
