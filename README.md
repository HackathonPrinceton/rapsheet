# Tally

**Controlled-substance forensics for independent pharmacies.**

The pharmacist says or texts an opioid count while counting. Tally checks it against deliveries and fills. When pills go missing, it rebuilds a timeline in which every finding cites the record behind it. It also flags prescription rings in the pharmacy's own fill history.

Built at HackPrinceton Fall 2026.

## Why

- Pharmacists share legal responsibility for catching illegitimate controlled-substance prescriptions (21 CFR 1306.04, "corresponding responsibility").
- CVS, Walgreens and Walmart agreed to about $13.8B in 2022 opioid settlements over ignored red flags.
- Since 2023, a theft or significant loss must be filed on DEA Form 106 within 45 days.
- Independent pharmacies still count by hand on paper logs.

## What it does

1. **Count by voice or text.** Counts arrive by voice or text message, and Tally replies right away if the number doesn't match the expected count.
2. **Invoice photo intake.** A photo of the delivery invoice is logged as received stock, which catches short shipments.
3. **Timeline reconstruction.** When a count is off, it narrows down when the loss happened, using counts, invoices, fills, edits and shifts, each finding cited.
4. **Prescription ring detection.** A graph of patients, prescribers and addresses that flags DEA red flags.
5. **Prescriber checks.** Real public data from NPPES and CMS Part D.
6. **Drafts.** A DEA Form 106 draft and a red-flag decision note.

Flags are prompts to verify, never automatic refusals.

## Repo layout

| Folder | What lives there |
| --- | --- |
| `generator/` | Synthetic pharmacy data with planted diversion scenarios |
| `engine/` | Count reconciliation, timeline reconstruction, ring graph, prescriber lookups |
| `bot/` | Messaging agent: counts, invoice photos, alerts, replies |
| `dashboard/` | Timeline view and ring graph |
| `data/` | Generated data (large files are not committed) |

## Setup

```bash
cp .env.example .env   # then fill in your keys
pip install -r requirements.txt
```

## Data and ethics

- Pharmacy records are synthetic. No real patient data is used.
- Prescriber data comes from public NPPES and CMS datasets.
- A flag means "review", not "fraud".
