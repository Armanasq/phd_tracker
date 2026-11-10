# Redistribution and provenance audit

Run `python scripts/redistribution_inventory.py --json` in a repository checkout. The tool inventories tracked application source, visual assets, research data, declared Python dependencies and external GitHub Actions references without exposing file contents or credentials.

The inventory lists **proof obligations**, not copyright findings. A LICENSE file is necessary but is not alone sufficient evidence of legal authorization, third-party license compliance, or permission to publish applicants' data. The tool deliberately reports redistribution as blocked until a rights-holder decision and a separate provenance audit.

Required operator sign-off before Issue #13 can be closed:

1. Identify the application and asset copyright holders and obtain approval of the chosen software distribution license.
2. Review pinned Python dependencies, workflow actions, generated figures, imported code and other third-party materials against their actual release terms.
3. Review source datasets, applicant workbooks, source excerpts, reports and imported data separately from software copyright.
4. Add the authorized LICENSE and notices. Check Docker, Pages, source, examples, and the README against the approved rights scope.
5. Audit the public Git history for secrets and personal information with a dedicated security inspection. This inventory is only a paths-and-declarations scanner.

The regression test `tests/test_redistribution_inventory.py` confirms that missing licenses and an unverified grant cannot accidentally be marked release-ready. No automated test can substitute for a legally authorized license decision.
