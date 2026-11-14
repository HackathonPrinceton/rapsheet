# Measured results

**Status (Nov 14, evening):** hand-checked results from one checker (Krutika, 115 reports) are in
section 2. The second checker's labels and the agreement figure will be added when they arrive. Sections marked "solid" come straight from the
data and will not change.

Data: 420,167 FDA adverse event reports received from January 2019 to November 2026 for two device
types, AEDs (product code MKJ) and CPAP/BiPAP machines (BZD), and
419 recalls. Source: openFDA.

## 1. Deaths in the FDA's own fields

| | AED | CPAP | Total |
|---|---|---|---|
| Reports coded as "Death" | 1,232 | 4,457 | 5,689 |
| Coded "Malfunction" or "Injury" while the patient outcome field says "Death" | 162 | 63 | 225 |

The two fields disagree on 225 reports. **This is a data-quality finding, not a count of hidden
deaths:** on the hand-checked reports, only 1 in 3 of those where the outcome field says "Death"
actually describes this patient dying (precision 0.33, section 2). Reproduce with
`SELECT COUNT(*) FROM reports WHERE event_type != 'Death' AND outcomes LIKE '%Death%'`.

## 2. Hidden-death classifier

### Hand-checked results

101 reports not coded as deaths, read and labelled by a person without seeing any model's answer
(115 checked, 14 marked "cannot tell" and left out). 27 of them describe the patient dying.
Every method below is scored on the same 101 reports.

| Method | Precision | Recall | Right / flagged |
|---|---|---|---|
| Keyword search (any death-related word) | 0.36 | 1.00 | 27 / 75 |
| FDA outcome field says "Death" | 0.33 | 0.26 | 7 / 21 |
| **Our classifier** | **0.94** | **0.56** | **15 / 16** |
| Classifier or outcome field | 0.56 | 0.70 | 19 / 34 |
| Large language model reading every report | 0.85 | 0.85 | 23 / 27 |

Reading:
- The classifier is wrong once in 16 flags. Keyword search is wrong about 2 times in 3, and the FDA's
  own outcome field is wrong 2 times in 3.
- The classifier finds a bit over half of the deaths. It trades recall for precision on purpose: a
  wrong "hidden death" on a public page is worse than a missed one.
- A large model reading every report finds more (0.85 recall) but costs an API call per report; the
  classifier runs free on a laptop over all 414,478 reports.

Weighted to the real mix of reports (the hand-check set over-samples interesting cases), classifier
precision is 0.98 and keyword precision 0.09. Weighted recall is too uncertain to quote: a handful of
random reports stand for hundreds of thousands. All figures in `eval/gold_results.json`.

Limits: 101 reports and one checker. The confidence interval on the classifier's precision is wide
(15 of 16 is consistent with roughly 70% to 99%).

### Earlier figures, against model-assigned labels

Accuracy on 1,005 held-out labelled reports not coded as deaths, of which 34 describe a death:

| | Precision | Recall |
|---|---|---|
| Classifier | 0.913 (21 of 23 flagged) | 0.618 (21 of 34) |
| Any death-related word | 0.044 | 0.912 |

Reading: a keyword search is right about 1 time in 23. The classifier is right about 9 times in 10,
and finds about 6 in 10 of the deaths. It trades recall for precision on purpose: a wrong "hidden
death" on a public page is worse than a missed one.

What the classifier does not do: find deaths that a keyword search would miss. We tested this directly.
We took the 287 highest-scoring reports that contain no death-related word and had them labelled: 4
described a death ("the patient was not resuscitated"). Deaths described without any death-related word
are rare in these two device types, and the model does not find them reliably.

Labels: 2,675 reports. 2,122 were labelled by a large language model through the API, 553 by an AI
model in a working session. These figures measure agreement with the large model, not with a person;
the hand-checked table above is the one to quote.

Death-related words alone are a poor signal: in AED reports they are mostly about equipment
("the battery was dead", "the pads were expired"), and in CPAP reports mostly stock denials
("there was no reported patient death or serious injury").

## 3. Late reporting (rule)

Computed in the pull: days from the date the manufacturer became aware to the date the FDA received
the report, for manufacturer reports. Follow-up reports are not separated from initial reports yet,
which may overstate lateness.

| | On time (30 days or fewer) | Late (31 to 180) | Very late (over 180) | Unknown dates |
|---|---|---|---|---|
| Our data, 2019 to 2022 (159,640 reports) | 68.9% | 16.0% | 15.0% | 0.2% |
| Our data, all years (416,862 reports) | 54.4% | 9.8% | 34.8% | 0.9% |
| Published, all device types (Everhart et al., BMJ 2025; figure to be confirmed against the paper) | 71% | 4.5% | 9.1% | 15.5% |

Our figures cover two device types only, so they are not expected to match the published ones.

## 4. Early warning (solid measurement, weak result)

A month is flagged when a device's report count is far above its own previous 12 months
(robust z-score of 3 or more, at least 5 reports). 301 devices scored, 20,476 device-months, 974 flagged.

| | Value |
|---|---|
| Recalls that could be tested (device had at least 7 months of history first) | 88 |
| Recalls with a flag in the 24 months before | 43 (48.9%) |
| Same question for random 24-month windows with no recall | 35.8% |
| Median lead time, when there was a flag | 12 months |
| Flags not followed by a recall of that device within 24 months | 79.2% (of 654) |

Reading: flags come before recalls more often than chance, but not by much, and most flags are not
followed by a recall. The honest wording is "reports are rising", not "a recall is coming".

Limits: reports also rise after news coverage, lawsuits, and when a manufacturer files old reports in
bulk. Recalls are matched to devices by maker and brand wording, which is imperfect.

## Reproduce

```
make pull      # about 50 minutes
make models    # train, score, backtest
python -m pipeline.evaluate   # compare four methods on the hand-checked set
```
