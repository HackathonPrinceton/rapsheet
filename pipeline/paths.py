"""Where every input and output of the evaluation lives. One place, so no file name is repeated.

eval/
  metrics.md                      final results, written for people
  results/                        final numbers, written by the pipeline
  hand_check/                     the blind hand-check: what was checked, and both checkers' answers
  training/                       labels the classifier learned from
"""
import os

EVAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eval")
RESULTS = os.path.join(EVAL, "results")
HAND = os.path.join(EVAL, "hand_check")
TRAINING = os.path.join(EVAL, "training")

# results/
FINAL_RESULTS = os.path.join(RESULTS, "final_results.json")          # four methods on the hand-checked set
EXPLANATIONS = os.path.join(RESULTS, "explanations.json")            # why each flagged report was flagged
BACKTEST = os.path.join(RESULTS, "reports_rising_backtest.json")     # reports-rising flags vs past recalls
CLASSIFIER_TRAINING = os.path.join(RESULTS, "classifier_training.json")   # training run, against model labels
CLASSIFIER_SCORING = os.path.join(RESULTS, "classifier_scoring.json")     # counts after scoring every report

# hand_check/
BLIND_SET = os.path.join(HAND, "blind_set.csv")                      # what the checkers saw: text, empty answer
ANSWER_KEY = os.path.join(HAND, "answer_key.csv")                    # sampling group and model score per report
CHECKERS = {"A": os.path.join(HAND, "checker_A.csv"), "B": os.path.join(HAND, "checker_B.csv")}
SAMPLING = os.path.join(HAND, "sampling.json")                       # population of each sampling group
LARGE_MODEL_ANSWERS = os.path.join(HAND, "large_model_answers.csv")  # the large model's answer per report

# training/
LABELS = os.path.join(TRAINING, "labels.csv")                        # report_number, label, quote, source, note
TO_LABEL = os.path.join(TRAINING, "to_label.csv")                    # sample waiting to be labelled (not committed)
