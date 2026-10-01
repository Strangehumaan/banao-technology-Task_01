# Decisions, assumptions, weaknesses

Neha's email is not a specification, so where something was unclear I decided, wrote it down here, and gave the reason. Numbers quoted are from the 13 weeks to 28 Jun 2026 unless stated.

## 1. Assumptions

**Time and shifts**
1. **The export is UTC and I convert to IST (+05:30).** Sameer said so; I proved it rather than trusting it: +5.5 h is the only offset (tested -12 h to +14 h in 30-minute steps) that puts all 1,566 voice callback requests inside the IVR window of 08:00-22:00 (policy section 2). Left as UTC only 62.7% fit. Legacy and helpdesk copies of the same ticket carry identical timestamps, so legacy rows are on the same clock.
2. **Shifts are Morning 06:00-14:00, Day 14:00-22:00, Night 22:00-06:00 IST** (policy section 7), judged on the ticket's creation time. A Night shift belongs to the day it *starts* on (so 01:01 on 30 Jun is still the Night of 29 Jun). 22:00 is Night, 21:59 is Day, 06:00 is Morning.
3. **Weeks run Monday to Sunday by IST creation date.** "Last complete week" is the latest Sunday strictly before `--asof`. The default `--asof` is the day after the last ticket in the export, so the latest report covers 22-28 Jun 2026 and the last two days of data (29-30 Jun) wait for next week.

**Breaches and staffing**
4. **A breach is a first human reply later than the channel target, measured from creation** (chat 15 min, voice callback 2 h, social 4 h, email 8 h; policy section 3). "Later than" is strict: exactly 15 minutes on chat is not a breach. Open and pending tickets already have a first reply, so they count as breaches.
5. **A shift is "unstaffed" when no agent, in any team or tier, is on the roster for it that day.** I tested the stricter team-level version: before June 2025 Night tickets routed to Billing or Logistics (teams that never had a Night agent) breached at ordinary rates (6-17%) because the Night frontline team picked them up. After the change they jumped to 73-98%. So the shift is the right unit.
6. **The roster is taken at face value.** One row per assignment; the row in force on the day counts; a blank `to_date` means still assigned. The roster shows five Night agents until 29 Jun 2025 and none after. It does not say what happened to three of them (Zoya Mehta, Deepak Jadhav, Shreya Bhatt), and I treated "no row" as "not on the roster".
7. **The resolver is `agent_id` on resolved or closed tickets only,** matched to the roster row on the shift-day of resolution. For open or pending tickets `agent_id` is not a resolver, so those tickets are left out of every resolver view.
8. **Labels.** *Unstaffed shift*: created in a shift with no rostered agent. *Agent's own shift*: created while the resolving agent's shift was on. *Unclear*: everything else (resolved by a different shift, not resolved yet, resolver not on the roster). "Own shift" is an inference about who was around, not a record of who replied.

**People**
9. **Agent table is Tier 1 only** (policy section 6: Tier 2 is measured on resolution days). Tier 2 breaches still count in the shift totals.
10. **An agent needs at least 20 own-shift tickets to be rated.** The window is the trailing 13 weeks, because one week gives about five tickets per agent.
11. **Peers are Tier-1 own-shift tickets on the same channel** (chat, email, voice and social breach at different base rates), leaving the agent out of their own comparison. The test is an exact two-sided test on the sum of channel-specific breach probabilities. With about 34 agents tested at once I use **Holm-Bonferroni** at 5%, which protects against naming someone by luck; Benjamini-Hochberg is available with `--correction bh`. Why this and not the gentler option: the report is meant to start conversations about named people, and a false accusation costs more than a missed one. Without correction 1 agent would be flagged; with it, none.

**Money**
12. **Rs 350 per breached ticket, issued on resolution** (policy section 3). I count resolved *and* auto-closed tickets as issued; the policy does not say whether auto-closed tickets get the credit. Open and pending breaches are shown separately as "pending". Quarters are calendar quarters of ticket *creation*, not of resolution.
13. **Saving if Night is staffed again** = for each channel, (Night tickets created while unstaffed and later resolved/closed) x (Night's own breach rate while it was staffed) = expected breaches; saving = (actual - expected) x Rs 350. That rate is plain breaches / tickets, so it can be checked with a calculator (`saving_steps_*.csv`). Where Night has fewer than 30 staffed tickets in a channel the rate falls back to all staffed shifts on that channel. The 5,000-draw simulation only supplies the range (staffed rate redrawn from a Beta distribution, breaches redrawn as binomials). A second method, using the same-quarter breach rate of the staffed shifts on the same channel, agrees within about 2% in every full quarter.
14. **Scaling to 650 tickets a week** is linear: saving per ticket created (Rs 120,204 / 2,249 = Rs 53.45) x 650 x 13 weeks = Rs 451,632. It assumes the same mix of channels and shifts. Policy section 4 costs: Rs 165 per agent-hour, 8-hour shift, so one agent covering every night is Rs 165 x 8 x 7 x 13 = Rs 120,120 a quarter if it were new headcount.
15. **The "business number"** (25.7% to 9.6% overall) replaces the Night rate (80.7% in the window) with Night's staffed rate by channel (10.2%) and leaves everything else as it was.

**Data cleaning**
16. **616 duplicate ticket_ids** (migration re-import, all before the 14 Sep 2025 go-live) are dropped keeping the helpdesk copy. The two copies are identical in all 19 other columns; only CSAT differs (helpdesk blank, legacy 0). Legacy CSAT 0 is treated as blank. CSAT is not used in the report.
17. **Column names:** the README says `tickets.csv` / `customers.csv`; the pack on disk has `ticket.csv` / `Customer.csv`. The tool accepts either ticket name and does not read the customer file.

## 2. What I pushed back on or changed in the ask

| Ask | What I did | Why |
|---|---|---|
| "Which agents are breaching most" | The agent table shows the helpdesk's rate next to a rate on tickets created in the agent's own shift, corrected for testing ~34 people at once. | The standard rate is mostly a roster effect: 85% of breaches since the change are booked to Morning resolvers, but about 80% of those were created overnight. Morning agents sit at 30-60% on that basis and about 8% on their own tickets. |
| "Report by agent and shift" | The primary view is by the shift the ticket was *created* in, with each breach labelled. | Priya asked for nothing that demoralises the Morning team; a report that repeats the misattribution would do exactly that. |
| Neha: "Morning is the bulk of the breaches, that's just the fact" | True as booked, misleading as a cause. Said so in the memo. | Created-in-Morning tickets breach at 9.9%, the same as Day-created (9.0%); the gap is +0.9 pts and inside noise. |
| Neha: "the Indore reshuffle was cost-neutral" | Payroll-neutral, not credit-neutral. | It coincides with a jump from about Rs 11,000 to about Rs 64,000 a month in credits in the export. |
| Priya "credits look flat" vs Arjun "tripled" | Both are right. | One step up in July-August 2025, flat since (about five times the Jan-Jun 2025 level in the export, part of it ticket volume). |
| Arjun: "the answer cannot be hire" | The recommendation is to re-roster existing agents. | Respected as a hard constraint. Hiring cost is shown only as context. |
| "Nothing fancy" | Kept the report to a readable Markdown file plus CSVs and left out dashboards and alerts. | Matches the ask. The extra effort went into the checks, not the polish. |
| "AI-assisted tool" | AI was used to build and check the tool; no model runs inside it (section 4.1). | See below. |

## 3. Known weaknesses

1. **The export never records who sent the first reply.** Only 64.8% of all breaches (70.8% since the change) have a defensible owner at shift level (the roster gap). The other 35.2% cannot be tied to a named person. Even among the 429 "own shift" breaches, 73 (17%) had a first reply timestamped outside the resolver's shift hours, so the label can be wrong.
2. **Replies happen overnight even though nobody is rostered.** Since the change 672 first replies fall between 22:00 and 06:00 (497 email, 82 voice, 75 social, 18 chat). I have not explained this. Possibilities are unrostered overtime, remote work, or timestamps that do not follow shift hours. If real people are answering some night email, "unstaffed" overstates the gap for email (email Night breaches are 50%, chat 100%).
3. **The saving is a model, not an observation.** It assumes the old Night rate holds now. Night volume is roughly double what it was when five agents covered it, and re-rostering might raise breaches on the shifts the agents come from. The 5-95% range (Rs 114k-125k for the window) reflects sampling only, not these assumptions.
4. **Volume mismatch.** The brief says about 650 tickets a week; the export averages 144 a week overall and 173 recently. I do not know whether the export is a sample. The 650 figure is a straight-line scale-up.
5. **The independent check shares my assumptions.** The reference implementation was written from the same reading of the policy. It catches implementation bugs (I planted seven bugs in a copy of the tool; one changed nothing, and the validator caught all six that did); it cannot catch a wrong definition. The backtest rests on one event: 0 false alarms in 54 shift-weeks, but a looser threshold gives 4.
6. **The agent table has low power.** With about 20-50 own-shift tickets each, an agent's rate has a wide 95% interval (for example 4.7%-33.3% on 22 tickets). "No one flagged" does not mean "no differences".
7. **Look-ahead on re-runs.** Running with an earlier `--asof` still uses each ticket's final status and resolver from the export.
8. **Tested on one machine** (Windows, Python 3.13; pandas 2.2.3 and 3.0.6). Not tested on macOS, Linux, or Python 3.10-3.12, although nothing in the code is platform-specific.
9. **Output files contain agent names and ticket IDs.** The data folder is gitignored; the outputs are not. Decide before publishing the repo whether to keep `agents_*.csv` and `breaches_*.csv`.

## 4. What I left out, and why

| Left out | Why this and not something else |
|---|---|
| **Reading the free text** (customer messages, agent notes) | Breach, shift and agent attribution come from timestamps and the roster alone. The text cannot change those answers (section 4.1). |
| **CSAT impact of the Night gap** (Priya says CSAT moved) | Plausible and worth doing, but a separate question from first-response breaches; the memo would grow without changing the recommendation. First thing I would add. |
| **Handle time, first-contact resolution, repeat contacts, transfers, refunds and replacements** | Other problems in the same data (the policy defines them), none needed for the breach report. |
| **A staffing model** (how many Night agents, which ones) | A rough load figure (about 20 tickets a night at 650 a week) is in the memo. A real rota needs leave, skills and site constraints I do not have, and Neha does. |
| **Who actually answered the overnight emails** | Not in the data; this is a question for Sameer. |
| **Dashboards, email delivery, scheduling** | "Nothing fancy, weekly." One command a week does the job. |
| **Tier 2 metrics** | Policy says they are measured on resolution days, not here. |
| **Orders, customers, products** | No link to first-response timing. |

### 4.1 Why no LLM runs inside the tool

- **The job is arithmetic on timestamps.** Convert a clock, compare to a target, look up a roster row. Every answer has to be reproducible and auditable, because it is used to talk to named people about their performance. A deterministic program gives identical results every run; a model can differ run to run and cannot be validated to the 0-in-11,200 standard I could reach here.
- **Cost.** One run costs Rs 0 and takes about a second. A per-ticket model call would add recurring cost and latency for no gain in accuracy.
- **Privacy.** Customer messages and agent notes can contain personal details. Sending them to an external model would be a new data-sharing decision for Vireo that this task does not need.
- **No benefit found.** I looked for places where text would change an answer: the category tag, the failed IVR transcripts (about 40), the closing notes. None affects who breached or when.
- **Where AI did help:** building, profiling, and testing the tool (see the submission form).

## 5. Tried and thrown away

- **Team-level "staffed"** (section 1, item 5): tested, shift-level is right.
- **"First reply inside the agent's own shift" as a stricter own-shift test:** the export's reply times do not follow shift hours (weakness 2), so it would have created false precision. Reported as an uncertainty figure instead.
- **A smoothed (Laplace) baseline for the headline saving:** the Rs figure was not reproducible by hand. Replaced with plain breaches / tickets; the simulation now gives only the range.
- **Flagging agents without a multiple-testing correction.**

## 6. Open questions for Vireo

1. Who sent the overnight email replies since July 2025?
2. What happened to Zoya Mehta, Deepak Jadhav and Shreya Bhatt after 29 Jun 2025?
3. Is 650 tickets a week the real volume, and is the export a sample?
4. Does an auto-closed ticket that missed its target get the Rs 350 credit?
