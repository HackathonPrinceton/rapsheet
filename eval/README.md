# Evaluation

**Start with [`metrics.md`](metrics.md)**: the final results, with an at-a-glance table at the top.

Everything else in this folder is the evidence behind those results, kept so anyone can check or rerun them.

```text
eval/
├── metrics.md                       final results, written for people
├── results/                         final numbers, written by the pipeline
│   ├── final_results.json             four methods scored on the hand-checked reports, and checker agreement
│   ├── explanations.json              why each flagged report was flagged; accuracy by confidence range
│   ├── reports_rising_backtest.json   "reports rising" flags tested against past recalls
│   ├── classifier_training.json       training-time check against model-assigned labels (not the headline)
│   └── classifier_scoring.json        counts after scoring every report
├── hand_check/                      the blind hand-check
│   ├── blind_set.csv                  the 200 reports the checkers read, with an empty answer column
│   ├── checker_A.csv                  Krutika's answers
│   ├── checker_B.csv                  Mrudula's answers
│   ├── answer_key.csv                 how each report was sampled and the model's score (hidden from checkers)
│   ├── sampling.json                  how many reports each sampling group stands for, for weighting
│   └── large_model_answers.csv        a large language model's answer on the same reports, for comparison
└── training/
    └── labels.csv                     2,675 reports the classifier learned from (labelled by a large language model)
```

## How the hand-check worked

1. `python -m pipeline.deaths gold` drew 200 reports not filed as deaths: some the model flagged, some
   with a death word it did not flag, some where the FDA's outcome field says death, and some at random.
2. Two people labelled them in `page/gold_check.py`, which never shows a model's answer. 30 reports went
   to both, to measure agreement.
3. `python -m pipeline.evaluate` scores every method on the reports both checkers could decide and writes
   `results/final_results.json`.

None of these files contain patient identities: the reports are public FDA records, and the FDA redacts
personal details before publishing them.
