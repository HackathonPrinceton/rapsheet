# Measured results

**Status: provisional (Nov 14).** The classifier figures rest on a small set of labels that have not
been hand-checked yet. Do not quote them in the pitch. Sections marked "solid" come straight from the
data and will not change.

Data: 420,201 FDA adverse event reports received from January 2019 to November 2026 for two device
types, AEDs (product code MKJ, 116,479 reports) and CPAP/BiPAP machines (BZD, 303,722 reports), and
419 recalls. Source: openFDA. Row counts match the totals the API reports.

## 1. Deaths in the FDA's own fields (solid, no model)

| | AED | CPAP | Total |
|---|---|---|---|
| Reports coded as "Death" | 1,232 | 4,457 | 5,689 |
| Coded "Malfunction" or "Injury" while the patient outcome field says "Death" | 162 | 63 | 225 |

The second row needs no model: the report's event type and its patient outcome field disagree.
To reproduce: `SELECT COUNT(*) FROM reports WHERE event_type != 'Death' AND outcomes LIKE '%Death%'`.

## 2. Hidden-death classifier (provisional)

What it does: gives every report not coded as a death a probability that its text says the patient died.

| | Value |
|---|---|
| Reports scored | 414,478 |
| Flagged as describing a death | 494 (AED 374, CPAP 120) |
| Of those, with no death-related word in the text | 48 |
| Of those, where the outcome field also says "Death" | 134 |
| Outcome field says "Death" but not flagged | 91 |

Accuracy on held-out labelled reports (221 reports, of which only 3 describe a death):

| | Precision | Recall |
|---|---|---|
| Classifier | 0.40 (2 of 5 flagged) | 0.67 (2 of 3) |
| Any death-related word | 0.014 | 1.00 |

Why this is not quotable yet:
- 3 positive examples is far too few to measure precision or recall.
- All 553 labels were assigned by an AI model reading the text. None are hand-checked.
- Known false positives remain: reports that say an earlier "Death" entry was a mistake and has been
  corrected, and one stock recall paragraph on CPAP reports.

What will make it final: about 2,000 more labels (`make sample label`), a retrain, and a gold set of
200 reports checked by hand by two people (`eval/gold_blind.csv`).

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
```
