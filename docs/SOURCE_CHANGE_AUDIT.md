# Source snapshot change audit

`python -m phd_agents compare-sources --previous path/to/previous.json --current path/to/current.json`

This read-only operator command compares two independently acquired JSON evidence snapshots in the existing `{"records":[...]}` format. It checks stable application IDs and changes to deadline, deadline type, verification metadata, source URL, application URL, funding, eligibility and listed documents. It emits a deterministic JSON event ID, old/new values, the source link (with query/fragment removed), and a mandatory manual-review status.

The snapshot's `as_of` stamp is evaluated separately from **actual official website freshness**. An unchanged or recently generated snapshot cannot prove the official portal was rechecked. If the source is unknown, inaccessible or unverified, no deadline or eligibility conclusion is inferred. A disappeared record is a `record_missing_from_new_snapshot` observation, **not** proof of closure. No application record is automatically edited, and no external network request is performed.

This command does not crawl official sites or store verified observations automatically. Obtaining source snapshots, following robots/terms, verifying primary institutional records, retaining retrieval timestamps and independently resolving conflicting deadlines remain necessary before Issue #6's full official-source ingestion criterion can be closed. Never publish a private-source diff into GitHub Pages without an explicit data review.

Regression: `python -m pytest tests/test_phd_source_changes.py -q`.
