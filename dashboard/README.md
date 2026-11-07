# EvidenceGraph / interactive flight deck

This is a real, data-backed browser application. It is **not executable inside GitHub's README renderer**. The homepage links to a GitHub-native workflow that is immediately interactive through workflow inputs. The richer canvas application is in this directory.

## Open

Clone the repository and open the generated dashboard file:

```bash
git clone https://github.com/Armanasq/phd_tracker.git
cd phd_tracker
python scripts/experience_engine.py
xdg-open dashboard/index.html
```

On macOS, use `open dashboard/index.html`. The generated **index.html is fully self-contained**, embedding its CSS, JavaScript and versioned evidence snapshot. You can also download that single file from GitHub and open it directly. No bundler, CDN, web server, or internet connection is required for the interactive features. The separate JavaScript and CSS files remain editable source modules.

For a GitHub-native interface without cloning, open [Run workflow](https://github.com/Armanasq/phd_tracker/actions/workflows/experience-lab.yml), select the horizon and decision lens, and review the computed job summary and JSON artifact.

## Interactive capabilities

| Control | Meaningful state change |
|---|---|
| Evidence graph | Drag nodes, zoom with the wheel, inspect document mentions and application provenance |
| Temporal lens | Scrub 0–60 days and animate the period; the graph and workload selection update |
| Conflict view | Switch from document links to source-monitor anomaly highlighting |
| Scenario weights | Adjust urgency, proof debt and unknown-document weights; rankings recalculate locally |
| Resource readiness | Hypothetically mark mentioned documents ready; affects the scenario only |
| Local board | Drag applications between investigate, prepare and reviewed-local lanes; saved to browser local storage |
| Command palette | Press Ctrl/Cmd + K, search actions or applications, select to navigate |
| Reproducibility | Copy horizon/weight selection to a URL hash; export prioritization CSV, graph JSON and board JSON |
| Native GitHub workflow | Runs input-driven analysis on stored evidence, producing a report and downloadable artifact |

These are real interactions, not pre-recorded animations.

## Data integrity

The generator consumes versioned records from the execution plan, portfolio frontier, explicitly confirmed assets, discovery report, source monitor, and research radar. The browser reuses their committed snapshot date; it never silently changes the workbook.

Scores are **user-chosen workload indexes**, not probabilities of admission or eligibility. Document mentions are evidence edges; unknown readiness does not mean missing documents. Moving a card in the local board does not establish an actual submission.

## Public hosting

The repository currently does not have GitHub Pages enabled. A GitHub Pages deployment can host this static application if the repository owner enables Pages and uses a supported plan. **Until a deployment is confirmed, the GitHub README links to setup instructions rather than claiming that a Pages website is live.**

The root README can render SVG/CSS motion, GIFs, native expandable sections, links to GitHub Issues and input-driven GitHub Actions. It cannot execute inline JavaScript, React or an interactive canvas.

## Source

- `dashboard/template.html`: HTML shell and initial evidence browser.
- `dashboard/experience.js`: graph, time machine, scenario model, command palette, workspace.
- `dashboard/experience.css`: responsive immersive visual system.
- `scripts/experience_engine.py`: versioned snapshot embedding and artifact generation.
- `scripts/scenario_lab.py`: typed GitHub Actions input analysis and report generation.
- `scripts/kinetic_readme.py`: animated data-derived SVG cover and pipeline.

