# Multisource doctoral opportunity audit — 9 November 2026

**Coverage:** primary university and laboratory recruiting pages; EURAXESS and ELLIS discovery indexes; public LinkedIn and social search; Gmail recruiting emails; GitHub pipeline/source telemetry; CoChat and Consensus for methodological research alignment. These are separate evidence tiers. Academic papers and social reposts are not authoritative vacancy notices.

## Newly registered university calls

| Source | Position | Date/status | Decision | Critical qualification |
|:--|:--|:--|:--|:--|
| [KTH official vacancy](https://kth.varbi.com/en/what%3Ajob/jobID%3A978857/) | Agentic & Embodied AI for adaptive manufacturing | **3 Dec 2026**, final | **Go** | One funded doctoral place, PA-2026-3497; institution-specific admissions apply |
| [ETH IDEAL official vacancy](https://www.jobs.ethz.ch/job/view/JOPG_ethz_AUmT7tc75KfdQZK3sA) | Machine Learning for Engineering Design, Mark Fuge group | **15 Jan 2027, priority/best consideration only** | **Go** | 1–2 advertised PhDs. Do not label 15 Jan as a confirmed hard cutoff |
| [Imperial PAIR official lab](https://www.imperial.ac.uk/pair-lab/join-us/) | Three funded Human–Robot Interaction PhDs, September 2027 | **1 Dec 2026**, lab deadline | **Check first** | International students eligible; PAIR does **not** work on SLAM, robot control or generic computer vision |
| [University of Bonn HRL application](https://www.hrl.uni-bonn.de/jobs/application) | Active perception/mobile manipulation and VLM greenhouse robotics | **Rolling, until filled** | **Go** | Two fully funded **TV-L E13 100%** posts; form-only application, single PDF under 8 MB |
| [UZH Robotics and Perception Group](https://rpg.ifi.uzh.ch/positions.html) | Vision-based robot learning with world models, estimator-free navigation, event cameras | **Rolling, no fixed closing date** | **Go** | Primary lab page overrides outdated 27 Oct indexed cutoff |
| [ETH HC3 official vacancy](https://jobs.ethz.ch/job/view/JOPG_ethz_VHL83kyFBbwBQD0AfO) | Multimodal 3D reconstruction, LiDAR and digital twins | **31 Jan 2027, EURAXESS index only** | **Check first** | Four-year funded PhD; [EURAXESS deadline](https://euraxess.ec.europa.eu/jobs/477410) not independently established by ETH |

### Deduplication
The [Aalborg ROX6G multi-robot planning PhD](https://www.vacancies.aau.dk/phd-positions/show-vacancy/vacancyId/981852), closing 29 Nov 2026, is already in the original tracker as `N264-08`. ETH RobotX, KTH/UZH research subtopics, and other existing routes were checked against the existing source-ID registry to avoid manufacturing extra applications.

### Resolved archive discrepancy: TUM `N263-07`
A cached version of the [official TUM AVS humanoid-robotics posting](https://www.mos.ed.tum.de/en/avs/career/our-jobs/ki-motorsport-1/) had an earlier **17 July 2026** deadline. A **fresh 9 November 2026 source search** returned the updated TUM posting with **15 November 2026** as the application deadline, **1–15 December 2026** interviews and a **1 February 2027** start. The lab's [autonomous motorsport recruitment overview](https://tum-autonomous-motorsport.com/) and a current public LinkedIn recruitment post independently corroborate **15 November**.

The existing tracker deadline `N263-07` is therefore **supported by the fresher official version**. The live evidence monitor reports `anchor_present`, rather than a contradiction. The `N263-07-LIVE` watch retains a `contradiction_deadline_mismatch` regression guard only if the older July date reappears. No protected workbook date was overwritten.

### Supporting research, not vacancy evidence
- [Dream to Fly — model-based reinforcement learning for drone flight](https://doi.org/10.1109/icra57385.2026.11695931) (CoChat-indexed).
- [Demonstrating Agile Flight from Pixels without State Estimation](https://doi.org/10.48550/arxiv.2406.12505) (CoChat-indexed).
- Consensus research search returned related robot world-model / VLA literature. These papers inform the UZH, Bonn and KTH research-fit assessment, not the availability or deadline of doctoral openings.

### Plugin and discovery coverage
- **GitHub:** connected; source registry, documentation, monitor and tests committed directly to `main`.
- **Gmail:** read-only targeted research; recent recruiting announcements were reviewed, but this pass did not establish any additional successful application submission.
- **LinkedIn:** current connector searches people profiles, **not** a full authenticated posts, jobs and inbox feed; public web results supplemented it.
- **CoChat + Consensus:** academic relevance only, no vacancy inference.
- **ChatAcademia:** grant and literature searches were attempted but returned **no evidence** because the connected account had insufficient credits.
- **Acumen:** recent-context research; current institutional notices remained controlling sources.
- **TinyFish:** proposed as an optional browser-based connector for expanded authenticated portal and social-site retrieval; installation requires user action and is not assumed.

The [discovery diagnostics](../data/discovery_report.json) remain degraded: only Inria was healthy among four configured search providers; AcademicPositions returned HTTP 403, AcademicTransfer returned no new candidates, and Brave lacked `BRAVE_SEARCH_API_KEY`. All-source/exhaustive coverage therefore cannot be claimed. Reconciliation and workbook validation should be confirmed from the latest GitHub Actions run.

**Privacy and state:** no full email bodies, login credentials, or sensitive personal information are copied into the repo. No candidate was automatically marked submitted, rejected or personally eligible.
