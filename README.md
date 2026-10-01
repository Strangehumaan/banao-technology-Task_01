# Vireo Audio - weekly first-response SLA breach report

A small command-line tool that turns the helpdesk export and the agent roster into the weekly breach report Neha Kulkarni asked for, with one difference: every breach is labelled as **unstaffed shift**, **agent's own shift**, or **unclear**, so people are not blamed for tickets that arrived when nobody was rostered.

It is plain Python (pandas + numpy). **No API keys, no network calls, no paid services, no LLM.** A run takes about a second and costs Rs 0.

```
README.md                  this file
data/                      the client pack (NOT in the repo - see step 2)
solution/
  breach_report.py         the tool
  validate.py              independent checks that the tool is right (PASS/FAIL)
  night_shift_evidence.ipynb   the analysis behind the finding (already executed, outputs saved)
  memo.md                  one-page memo to Neha
  decisions.md             assumptions, pushback, weaknesses, what was left out
  submission-form.md       the submission form
  outputs/                 what the tool and validator wrote (latest run is committed)
```

## Run it on a clean machine

You need **Python 3.10 or newer** (tested on 3.13) and nothing else but `pandas` and `numpy` (tested on pandas 2.2.3 and 3.0.6, numpy 2.2 and 2.5).

**1. Get the code and create an environment**

Windows (PowerShell):
```powershell
git clone <repo-url>
cd <repo-folder>
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install pandas numpy
```

macOS / Linux:
```bash
git clone <repo-url>
cd <repo-folder>
python3 -m venv .venv
source .venv/bin/activate
pip install pandas numpy
```

**2. Put the client pack in `data/`**

The repo does not contain client data. Copy the pack's files into a folder called `data/` at the top level of the repo (next to `solution/`). The tool reads only two of them:

| File | Needed | Note |
|---|---|---|
| `tickets.csv` (or `ticket.csv`) | yes | the helpdesk API export, **UTC** timestamps |
| `agents.csv` | yes | the roster, one row per assignment |
| everything else | no | `orders.csv`, `customers.csv`, `products.csv`, the policy PDF are not used |

**3. Run the report**

```bash
python solution/breach_report.py
```

You should see:

```
Week 22 Jun - 28 Jun 2026: 207 tickets, 49 breaches (36 unstaffed shift, 10 own shift, 3 unclear)
Wrote .../solution/outputs/weekly_report_2026-06-22.md
      + 6 CSVs in .../solution/outputs
```

Open `solution/outputs/weekly_report_2026-06-22.md`. That is the report.

**4. Check that it is right (about 30 seconds)**

```bash
python solution/validate.py
```

It prints one `[PASS]` or `[FAIL]` per check, ends with `SUMMARY: 8/8 checks passed`, and saves the full log to `solution/outputs/validation_report.txt`. The exit code is 1 if anything fails.

## Running it every week

When Sameer sends the next export, replace the ticket file in `data/` and run step 3 again. By default the tool reports the **last complete Monday-Sunday week** in the export. To re-run a past week, say what date you are running it on:

```bash
python solution/breach_report.py --asof 2026-06-15      # reports Mon 8 Jun - Sun 14 Jun 2026
```

Other options (`python solution/breach_report.py --help`):

| Option | Default | What it does |
|---|---|---|
| `--asof YYYY-MM-DD` | day after the last ticket | report the last complete week before this date |
| `--data-dir`, `--out-dir` | `data/`, `solution/outputs/` | where to read and write |
| `--window-weeks` | 13 | trailing window for the agent table and the money scaling |
| `--min-tickets` | 20 | own-shift tickets an agent needs before being rated |
| `--correction` | `holm` | multiple-testing correction for the agent table (`holm` or `bh`) |
| `--credit` | 350 | Rs store credit per breached ticket (policy section 3) |
| `--weekly-volume` | 650 | tickets a week for the scaled money view |
| `--sims`, `--seed` | 5000, 7 | simulation size and seed (same seed = identical output) |

## What each output file is

| File | Contents |
|---|---|
| `weekly_report_<monday>.md` | the report: this week, by creation shift, agent table, money, method |
| `breaches_<monday>.csv` | every breach that week with its label, reason, resolver and credit |
| `by_creation_shift_<monday>.csv` | breaches by the shift the ticket was created in |
| `agents_<monday>.csv` | Tier-1 agents: standard rate next to own-shift rate, with p-values |
| `credits_by_quarter_<monday>.csv` | credits issued and the simulated saving, per quarter |
| `saving_steps_<monday>.csv` | the line-by-line arithmetic behind every saving figure |
| `weekly_trend_<monday>.csv` | last 8 weeks |
| `validation_report.txt` | the output of `validate.py` |

## Optional: the notebook

`solution/night_shift_evidence.ipynb` is already executed and shows its charts when opened on GitHub or in Jupyter. To re-run it you also need `pip install jupyter matplotlib`; run it from the `solution/` folder (it reads `../data`).

## If something goes wrong

| Symptom | Fix |
|---|---|
| `error: none of ['tickets.csv', 'ticket.csv'] found` | the data is not in `data/` next to `solution/`, or pass `--data-dir path` |
| `warning: only NN% of voice tickets fall in 08:00-22:00 after UTC->IST` | the export is not UTC (for example it was already converted). Shift definitions would be wrong, so ask for the API export |
| `error: no tickets created in the week ...` | `--asof` is earlier than the data; use a later date |
| `ModuleNotFoundError: pandas` | the virtual environment is not active; repeat step 1 |

Read `solution/decisions.md` before relying on the money figures or the agent table: it lists every assumption and what the data cannot tell you.
