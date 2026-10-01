# Submission form - Task 1, Vireo Audio (Set D)

Placeholders in `[SQUARE BRACKETS]` are for you to fill in before submitting.

---

**What did you build, and what business outcome does it move? State the number and the money.**

A command-line tool (`solution/breach_report.py`, Python, pandas + numpy) that produces Neha's weekly first-response breach report by agent and shift, plus a checking script (`solution/validate.py`), an evidence notebook, and a one-page memo.

The difference from what was asked: every breach is labelled **unstaffed shift**, **agent's own shift**, or **unclear**. The data shows nobody has been rostered on the Night shift (22:00-06:00 IST) since 30 Jun 2025. Night-created tickets wait for the Morning shift, breach, and the helpdesk books them against the Morning team. Night-created breach rate: 10% before, 79% since; Morning and Day did not move.

**Number:** cut the share of tickets that miss their first-response target from **25.7% to about 9.6%** (last 13 weeks, 578 of 2,249 tickets) by staffing Night again.
**Money:** about **Rs 1.2 lakh a quarter** in avoidable SLA credits on the export's volume (Rs 120,204 over 13 weeks), and about **Rs 4.5 lakh a quarter** at 650 tickets a week (Rs 451,632; range Rs 4.3-4.7 lakh). The recommendation is to re-roster existing agents, not hire, because headcount is frozen.

---

**What does one run cost, and what would a month cost at Vireo's volume (roughly 650 tickets a week)? Show the arithmetic. If you used no paid calls, say so.**

**No paid calls. The tool contains no LLM and makes no network requests.** One run costs Rs 0.

- Volume: 650 tickets/week x 52 / 12 = about 2,817 tickets a month.
- Paid API calls per ticket: 0. Cost per ticket: Rs 0. Cost per month: 2,817 x Rs 0 = **Rs 0**.
- Compute: the weekly report takes about 1.3 s on a laptop (measured), the full validation about 26 s. A month is 52 / 12 = 4.3 weekly runs, so about 6 s of laptop time.
- Cost of building it with AI: [AI COST - fill in, e.g. subscription share or tokens x price].

---

**How do you know it works? Sample size, how you checked, error rate, and the kind of case it gets wrong.**

`solution/validate.py` runs 8 checks (8 of 8 pass, log in `solution/outputs/validation_report.txt`):

1. **Independent re-implementation, no shared code** (standard library only) compared ticket by ticket on all **11,200 tickets** across 7 fields (shift, shift-day, breach, response minutes, staffing, resolver shift, label): **0 disagreements in 78,400 comparisons**. Statistical upper bound on the error rate, by the rule of three: about 0.03%.
2. **9 golden cases worked out by hand** from raw UTC rows, including exactly 15 minutes (not a breach), 22:00 / 21:59 / 06:00, and the 30 Jun roster boundary.
3. **Timezone proof:** only +5.5 h puts all 1,566 voice callbacks inside 08:00-22:00 (62.7% fit if left as UTC).
4. **Duplicates:** all 616 duplicated ids are identical in 19 of 20 columns; CSAT differs only as blank vs 0.
5. **Backtest:** a simple weekly detector gave 0 false alarms in 54 shift-weeks before the roster change and fired in the first week after it (7 days after the change). The helpdesk's standard report alarms on Morning and never on Night.
6. **Placebo:** Morning and Day moved +0.7 and +0.3 points at the change (confidence intervals exclude any 5-point effect); fake change dates on Night never exceeded 6 points against +68.8 for the real one.
7. **Owner uncertainty measured:** 64.8% of breaches have a defensible shift-level owner; 35.2% cannot be tied to a named person.
8. **Money audit:** credits and the saving recomputed from scratch match the tool's CSVs line by line.

I also checked the checks: I planted 7 bugs in a copy of the tool (wrong UTC offset, `>=` for `>`, no Night-day roll-back, wrong credit, own-shift ignoring the resolver, roster end dates ignored, and one change that changed nothing). The validator caught all 6 that changed behaviour.

**What it gets wrong or cannot know:** it cannot tell who sent the first reply (not in the export), so named-agent conclusions are inferences. Of the 429 "own shift" breaches, 73 (17%) had a first reply timestamped outside the agent's shift hours. The saving is a model, not an observation. The independent check shares my reading of the policy, so it finds bugs but not wrong definitions.

---

**Did you change, narrow, or push back on the client's ask? What, when, and why.**

Yes, at the start, before building, and again in the memo.

- **"Which agents are breaching most":** I show each agent's own-shift rate beside the helpdesk's rate, corrected for testing about 34 agents at once. None stands out. About 80% of the breaches booked to Morning agents were created overnight.
- **"Report by agent and shift":** the main view is by the shift the ticket was *created* in, with each breach labelled. A resolver-based report would keep blaming the Morning team, which Priya asked us not to do.
- **Neha's "Morning is the bulk of the breaches, that's just the fact":** true as booked, wrong as a cause. Created-in-Morning tickets breach at 9.9%, Day-created at 9.0%.
- **"The reshuffle was cost-neutral":** neutral on payroll, not on SLA credits (about Rs 11,000 to about Rs 64,000 a month in the export).
- **Priya "credits flat" vs Arjun "tripled":** both are right (one step up in Jul-Aug 2025, flat since).
- **Arjun's hiring freeze:** the recommendation is to re-roster, not hire.
- **"Nothing fancy":** kept the report to Markdown and CSV; no dashboard.

---

**What is wrong with what you are handing us? Be specific: bugs, shortcuts, things you know are off.**

1. **35.2% of breaches cannot be pinned on a named person.** The export does not record who sent the first reply.
2. **Unexplained overnight replies:** since the change 672 first replies are timestamped 22:00-06:00 (497 of them email) although no one is rostered on Night. If real people answer some night email, "unstaffed" overstates the email gap. I did not resolve this.
3. **The saving assumes the old Night breach rate still holds.** Night volume is about double what five agents used to handle, and moving agents may raise breaches elsewhere. The stated range covers sampling only.
4. **Volume mismatch:** the brief says about 650 tickets a week; the export averages 144 (173 recently). The 650 figure is a straight-line scale-up.
5. **Assumed, not given:** auto-closed tickets are counted as receiving the Rs 350 credit.
6. **The agent table has low power;** "no one flagged" is not "no differences".
7. **Tested on one machine** (Windows, Python 3.13, pandas 2.2.3 and 3.0.6), not on macOS, Linux or older Python.
8. **Re-running with an earlier `--asof`** still uses each ticket's final status.
9. **The outputs contain agent names and ticket IDs;** decide whether to keep them in a public repo.

Full list in `solution/decisions.md`.

---

**What did you deliberately leave out, and why that rather than something else?**

- **Free-text analysis (customer messages, agent notes):** breach, shift and attribution come from timestamps and the roster; text cannot change them. It would also send customer details to an external model.
- **CSAT impact of the Night gap:** a different question from first-response breaches; the first thing I would add next.
- **Handle time, first-contact resolution, repeat contacts, transfers, refunds and replacements:** other problems in the same data, not needed here.
- **A full staffing model:** needs leave, skills and site constraints I do not have; the memo gives a rough load figure and names two candidates.
- **Dashboards, email delivery, scheduling:** Neha asked for nothing fancy, weekly; one command does it.
- **Tier 2 metrics, orders, customers, products:** policy says Tier 2 is measured differently, and the other files have no link to first-response timing.

I chose these because each either cannot change the breach numbers or answers a different question, and the time went into making the numbers provable instead.

---

**Anything you built or found that nobody asked for?**

- A **validation harness** with an independent re-implementation, hand-derived golden cases, a backtest, placebo tests and a mutation test of the checks themselves.
- A **line-by-line money audit** (`saving_steps_*.csv`) so every Rs figure can be checked with a calculator.
- An **owner-uncertainty measure** (35.2% of breaches cannot be pinned on a person).
- **616 duplicate tickets** and the proof they are identical except for the CSAT placeholder.
- The **timezone proof** from the voice-callback window.
- A **reconciliation of Arjun's and Priya's claims** about the credit line.
- The **overnight email replies** that do not fit the roster, as an open question for Vireo.

---

**What did you use AI for? Which tools and models, where they helped, where they wasted your time, what you threw away. Link your three-minute screen recording here.**

**Tool:** Claude Code (Claude desktop app), model Claude Sonnet 5.5. No other AI tool. [CONFIRM or edit if you used anything else.]

**Used it for:** reading the pack, profiling the data, the evidence notebook, writing the tool and the validator, hand-checking numbers, and drafting these documents.

**Where it helped:** fast profiling of 11,816 rows, building and executing the notebook, and a validator written from scratch with no shared code. It also found things I had not asked about: the 616 duplicates and the overnight email replies.

**Where it wasted time:**
- Edit scripts it generated corrupted string literals (a backslash-n became a real line break) three times, each needing a manual fix.
- A helper script named `inspect.py` shadowed a standard-library module and broke imports.
- It opened the problem statement PDF late, after the data had been profiled and the notebook built, so the scope guidance came in late.

**Thrown away:**
- A team-level definition of "staffed" (tested; shift-level is right).
- A "first reply inside the agent's shift" test for own-shift breaches (the export's reply times do not follow shift hours).
- A smoothed baseline for the headline saving (not reproducible by hand; replaced with plain breaches / tickets).
- Agent flags without a multiple-testing correction.

**AI cost:** [AI COST]
**Screen recording (3 minutes):** [SCREEN RECORDING LINK]

---

**Your Public Google Drive Link**

[[GOOGLE DRIVE LINK]](https://drive.google.com/file/d/1BUnOv1b3YOKYRnrr3QK93qI9kafZ9-d2/view?usp=sharing)

---

**Someone picks this up on Monday and you are unreachable. The three things they need to know.**

1. **How to run it.** Put Sameer's UTC export in `data/` (`ticket.csv` and `agents.csv`), run `python solution/breach_report.py` for the weekly report and `python solution/validate.py` after any change. Steps are in `README.md`; it takes about a minute and costs nothing.
2. **The finding, and what is still open.** Nobody has been rostered on Night since 30 Jun 2025; 71% of breaches since then belong to that gap, not to the Morning team. Ask Sameer who sent the 497 overnight emails, ask Vireo what happened to three Night agents (Zoya Mehta, Deepak Jadhav, Shreya Bhatt), and confirm the real weekly volume (650 or about 173).
3. **Which numbers to trust and which to treat as a model.** Breach counts and shift labels are verified (0 of 11,200 tickets differ from an independent check). The Rs figures are a model that assumes Night performs as it used to; the agent table says nothing about individuals because the export does not record who replied. Everything is in `solution/decisions.md`.

---

**Honest hours spent. One number.**

3h

---

**Github Repo Link** (public)

[[GITHUB REPO URL]](https://github.com/Strangehumaan/banao-technology-Task_01)
