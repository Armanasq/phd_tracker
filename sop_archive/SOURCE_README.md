# CS PhD Statements of Purpose Archive

A year-organized collection of original publicly shared SOP files referenced by [CS PhD Statements of Purpose](https://cs-sop.notion.site/CS-PhD-Statements-of-Purpose-df39955313834889b7ac5411c37b958d).

## Import status (2026-11-05)

- **216** source records indexed
- **191** applicants with archived documents
- **214** actual PDF files committed and verified in this repository
- **25** unresolved records, including unavailable or access-restricted links
- Years: **2017–2026**, with an additional unclassified section

| Application year | Archived PDF files | Index |
|---|---:|---|
| 2026 | 1 | [Index](2026/index.csv) |
| 2025 | 21 | [Index](2025/index.csv) |
| 2024 | 53 | [Index](2024/index.csv) |
| 2023 | 32 | [Index](2023/index.csv) |
| 2022 | 31 | [Index](2022/index.csv) |
| 2021 | 49 | [Index](2021/index.csv) |
| 2020 | 9 | [Index](2020/index.csv) |
| 2019 | 9 | [Index](2019/index.csv) |
| 2018 | 4 | [Index](2018/index.csv) |
| 2017 | 5 | [Index](2017/index.csv) |

Each `YEAR/files/` directory contains the binary PDF documents, not merely URLs. Each `YEAR/index.csv` records the original Notion source, source document URL, local file path, retrieval status and SHA-256 checksum. A few applicants have multiple program-specific SOPs. For these, extra filenames are indicated in the index notes; see [2024 multi-document manifest](2024/extra_statements.csv) and [2021 multi-document manifest](2021/sai_siddartha_maram_documents.csv).

## Updating

The [import workflow](.github/workflows/import-sops.yml) runs [the eight-worker downloader](scripts/sync_sops.mjs) using the public Notion database and linked PDF/DOCX URLs. It validates file signatures, records checksums and commits successful downloads. Existing archived files are retained. Run the workflow manually when the source changes.

Full run summary: [SYNC_STATUS.json](SYNC_STATUS.json). Some originals are inaccessible because their links are dead, access requires authentication, or a linked resource is a folder/HTML page instead of a direct PDF. Such records remain listed as unresolved rather than substituted with unrelated files.

## Credit and copyright

Original SOP authors retain copyright in their statements. The [source collection](https://cs-sop.notion.site/CS-PhD-Statements-of-Purpose-df39955313834889b7ac5411c37b958d) states that its website content is licensed under **CC BY-NC-SA**, with SOP copyrights attributed to their respective authors. This independent archive is for noncommercial educational reference. The original author and source link are preserved for each entry. The source site's license statement should not be interpreted as independent confirmation of redistribution permission for every linked third-party file. Remove any file whose holder does not authorize mirroring.

This repository is not affiliated with or endorsed by the original collection's maintainers.
