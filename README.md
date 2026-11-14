# Rap Sheet

**The hidden safety record of the medical device you depend on.**

Text a photo of a medical device label (a CPAP, an insulin pump, an implant card, the AED on the wall). Rap Sheet replies with that device's safety record, built from the FDA's public adverse event reports: recalls, deaths that were filed under the wrong category, how late its manufacturer reports problems, and whether reports are rising. Every number links to the original FDA report.

Built at HackPrinceton Fall 2026. Track: Healthcare.

## Why

- **Deaths are miscoded.** In a published review of FDA device reports whose text said the patient died, about 23% were filed as "injury", "malfunction" or "other" (Lalani et al., JAMA Internal Medicine, 2021).
- **Manufacturers report late.** Only 71% of manufacturer reports met the 30-day legal deadline (Everhart et al., BMJ, 2025).
- **People are not told about recalls.** AEDs, for example, are not registered to their owners.

## How it works

| Step | Folder | What it does |
| --- | --- | --- |
| Pull | `pipeline/pull.py` | Downloads reports and recalls from openFDA into SQLite |
| Late reporting | `pipeline/pull.py` | Rule: days between the manufacturer learning of an event and the FDA receiving the report |
| Hidden deaths | `pipeline/deaths.py` | Trained classifier that reads report narratives |
| Early warning | `pipeline/warning.py` | Flags unusual jumps in monthly reports, backtested against past recalls |
| Record | `service/` | API that returns one device's full record |
| Messaging | `bot/` | Text a device name or photo, get the record back |
| Page | `page/` | The full record with source links |

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env                      # add your keys
python -m pipeline.pull --codes MKJ --start 2024-01    # MKJ = AEDs
uvicorn service.api:app --port 8000
streamlit run page/app.py
```

Without a database, the API serves `data/sample_record.json`, which is made-up example data for development only.

## Data and limits

- All data is public and comes from [openFDA](https://open.fda.gov/apis/device/). It contains no patient identities.
- A report is an allegation. It does not prove that a device caused harm.
- Rap Sheet never advises anyone to stop using a device. It points to the recall notice and the manufacturer.
