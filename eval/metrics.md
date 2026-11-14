# Measured results

**Status: provisional (Nov 14, afternoon).** The classifier figures rest on labels that have not been
hand-checked yet. Quote them only as "against model-assigned labels" until the hand-check is in. Sections marked "solid" come straight from the
data and will not change.

Data: 420,167 FDA adverse event reports received from January 2019 to November 2026 for two device
types, AEDs (product code MKJ) and CPAP/BiPAP machines (BZD), and
419 recalls. Source: openFDA.

## 1. Deaths in the FDA's own fields (solid, no model)

| | AED | CPAP | Total |
|---|---|---|---|
| Reports coded as "Death" | 1,232 | 4,457 | 5,689 |
| Coded "Malfunction" or "Injury" while the patient outcome field says "Death" | 162 | 63 | 225 |

The second row needs no model: the report's event type and its patient outcome field disagree.
To reproduce: `SELECT COUNT(*) FROM reports WHERE event_type != 'Death' AND outcomes LIKE '%Death%'`.

## 2. Hidden-death classifier (provisional until the hand-check is in)

What it does: gives every report not coded as a death a probability that its text says the patient died.
A report is flagged when the probability passes a threshold chosen to keep precision at 90% or more.

| | Value |
|---|---|
| Reports scored | 414,478 |
| Flagged as describing a death | 276 (AED 248, CPAP 28) |
| Of those, where the outcome field also says "Death" | 78 |
| Of those, with no death-related word in the text | 1 |
| Outcome field says "Death" but not flagged | 147 |

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
model in a working session. None are hand-checked yet, so these figures measure agreement with the
large model, not with a person. The hand-checked figures will come from `eval/gold_blind.csv`
(200 reports, two checkers) and replace this table: run `python -m pipeline.evaluate`.

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
