# Confidence rubric (tic-confidence-1.0)

Rule-based, not statistical. The factors come from the National Intelligence Council's estimative-language section
(ICA 2021) and are grouped under the UK's three factors (information base, analytical rigour, complexity and
volatility). The thresholds are this suite's own design, published so they can be checked and argued with.

**How it works:** the number of independent lines of evidence that agree sets the starting level; then every rule below
can cap it. The lowest cap wins. Each judgment lists the steps that would raise its level.

| UK factor | NIC element | Input | Rule |
|---|---|---|---|
| Information base | Consistency | independent lines that agree; any contradiction | Low below 2 lines; Moderate from 2; High needs 3 and no contradiction |
| Information base | Timeliness | age of the data against the source's expected cadence | Older than 2x the cadence caps at Low |
| Information base | Extent | coverage of the area or period | Below 50% caps at Low and marks the row degraded |
| Information base | Source quality | Admiralty grades | Reliability E or F, or credibility 5 or 6, caps at Moderate |
| Analytical rigour | Argumentation | alternatives examined and rejected | High needs at least one |
| Analytical rigour | Expertise | a scored Verdict record for the method version | No High until there is one |
| Analytical rigour | Assumptions | worst linked assumption | Strained caps at Moderate; broken blocks publication |
| Complexity and volatility | Deception | how easily the evidence could be faked | Easy to fake caps at Moderate |
| Complexity and volatility | Horizon | how far ahead a forecast looks | No High beyond 90 days |

**Independent lines.** Two reports count as one line when they share an upstream source (`source_lineage_id`) or sit in
the same independence group: the same government, the same aggregator, the same sensor network. For measurements, an
independent line is a separate sensing method (for GNSS interference: aircraft position quality, aircraft heard without
a position, satellite reflectometry, satellite radar interference flags).

Sources: [ICA 2021, estimative language](https://archive.dni.gov/files/ODNI/documents/assessments/ICA-declass-16MAR21.pdf);
[UK, explaining uncertainty](https://www.gov.uk/government/publications/explaining-uncertainty-in-uk-intelligence-assessment/explaining-uncertainty-in-uk-intelligence-assessment);
[ICD 203](https://archive.dni.gov/files/documents/ICD/ICD-203.pdf).
