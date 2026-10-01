# Vireo Audio - weekly first-response SLA breach report
**Week:** Mon 22 Jun - Sun 28 Jun 2026 (tickets created, IST) | **Run as of:** 01 Jul 2026 | **Data:** 11,169 tickets created up to 28 Jun 2026 (616 duplicate rows removed from the export)

## 1. This week
- **207 tickets, 49 first-response breaches (23.7%).** SLA credits at Rs 350: Rs 15,750 issued, Rs 1,400 still to come on open/pending tickets.
- Who the breaches belong to: **Unstaffed shift 36 (73%)**, Agent's own shift 10 (20%), Unclear 3 (6%).
- Of the 36 unstaffed-shift breaches, 33 are already resolved and will be booked in the helpdesk's standard report against the resolving agent's shift: Morning 31, Day 2.
- **Roster gap:** nobody is rostered on Night at the end of this week.

*Unstaffed shift* = ticket created in a shift with no agent on the roster (any team). *Agent's own shift* = created during the resolving agent's own shift, so plausibly theirs. *Unclear* = everything else: resolved by a different shift, not resolved yet, or the resolver is not on the roster. `agent_id` is the resolver, not necessarily the first responder.

### Last weeks
| week_start | tickets | breaches | breach_rate | unstaffed_shift | agents_own_shift | unclear |
|:--|--:|--:|--:|--:|--:|--:|
| 2026-05-04 | 158 | 35 | 22.2% | 25 | 4 | 6 |
| 2026-05-11 | 172 | 47 | 27.3% | 35 | 9 | 3 |
| 2026-05-18 | 178 | 45 | 25.3% | 31 | 8 | 6 |
| 2026-05-25 | 157 | 41 | 26.1% | 31 | 6 | 4 |
| 2026-06-01 | 162 | 36 | 22.2% | 24 | 5 | 7 |
| 2026-06-08 | 163 | 47 | 28.8% | 33 | 8 | 6 |
| 2026-06-15 | 195 | 46 | 23.6% | 35 | 7 | 4 |
| 2026-06-22 | 207 | 49 | 23.7% | 36 | 10 | 3 |

## 2. By creation shift
This week (rostered_on_last_day = agents on the roster on 28 Jun):

| created_shift | rostered_on_last_day | tickets | breaches | breach_rate | unstaffed_shift | agents_own_shift | unclear |
|:--|--:|--:|--:|--:|--:|--:|--:|
| Morning | 20 | 68 | 5 | 7.4% | 0 | 4 | 1 |
| Day | 21 | 93 | 8 | 8.6% | 0 | 6 | 2 |
| Night | 0 | 46 | 36 | 78.3% | 36 | 0 | 0 |
| All | 41 | 207 | 49 | 23.7% | 36 | 10 | 3 |

Last 13 weeks:

| created_shift | rostered_on_last_day | tickets | breaches | breach_rate | unstaffed_shift | agents_own_shift | unclear |
|:--|--:|--:|--:|--:|--:|--:|--:|
| Morning | 20 | 772 | 74 | 9.6% | 0 | 45 | 29 |
| Day | 21 | 963 | 89 | 9.2% | 0 | 49 | 40 |
| Night | 0 | 514 | 415 | 80.7% | 415 | 0 | 0 |
| All | 41 | 2249 | 578 | 25.7% | 415 | 94 | 69 |

The same breaches as the helpdesk's standard report books them (by the resolving agent's shift), this week:

| standard_report_shift | breaches_booked | of_which_created_in_unstaffed_shift |
|:--|--:|--:|
| Morning | 37 | 31 |
| Day | 8 | 2 |
| Night | 0 | 0 |
| not resolved yet | 4 | 3 |

And over the last 13 weeks:

| standard_report_shift | breaches_booked | of_which_created_in_unstaffed_shift |
|:--|--:|--:|
| Morning | 463 | 382 |
| Day | 84 | 11 |
| Night | 0 | 0 |
| not resolved yet | 31 | 22 |

## 3. Agents (Tier 1)
Window: last 13 weeks to 28 Jun 2026; resolved/closed tickets only. The **own-shift rate** counts only tickets created during the agent's own shift; the **standard rate** is the helpdesk's view (every ticket they resolved, whenever it was created). Agents need at least 20 own-shift tickets to be rated. Tier 2 (6 agents) is excluded per policy section 6.

**Many agents are tested at once, so some will look unusual by luck.** 34 agents are rated. Without correction 1 would be flagged at the 5% level; after Holm-Bonferroni correction 0 are. Each agent is compared with Tier-1 peers' own-shift rate on the same channel mix (excluding themselves); exact two-sided test. A flag is a reason to look at the tickets, not a verdict.

| Agent | Team | Shift | Resolved | Standard rate | Breaches from unstaffed shift | Own-shift tickets | Own-shift rate | 95% CI | Peers expect | Adj. p | Result |
|:--|:--|:--|--:|--:|--:|--:|--:|:--|--:|--:|:--|
| A3005 Sameer Joshi | Chat Frontline | Morning | 50 | 60.0% | 27 | 22 | 13.6% | 4.7%-33.3% | 8.1% | 1.000 | in line with peers |
| A3010 Neha Chatterjee | Chat Frontline | Morning | 38 | 55.3% | 17 | 20 | 15.0% | 5.2%-36.0% | 8.0% | 1.000 | in line with peers |
| A3013 Ritika Chatterjee | Chat Frontline | Morning | 53 | 50.9% | 26 | 25 | 4.0% | 0.7%-19.5% | 8.3% | 1.000 | in line with peers |
| A3011 Karan Roy | Chat Frontline | Morning | 40 | 50.0% | 20 | 19 |  |  |  |  | not rated (<20 own-shift tickets) |
| A3008 Steven Kaur | Chat Frontline | Morning | 37 | 48.6% | 16 | 20 | 10.0% | 2.8%-30.1% | 8.2% | 1.000 | in line with peers |
| A3007 Neha Gaikwad | Chat Frontline | Morning | 40 | 47.5% | 17 | 22 | 9.1% | 2.5%-27.8% | 8.4% | 1.000 | in line with peers |
| A3033 Amit Kulkarni | Billing | Morning | 58 | 44.8% | 22 | 28 | 7.1% | 2.0%-22.6% | 7.5% | 1.000 | in line with peers |
| A3009 Ramesh Patel | Chat Frontline | Morning | 46 | 41.3% | 17 | 27 | 7.4% | 2.1%-23.4% | 8.3% | 1.000 | in line with peers |
| A3028 Krishna Kaur | Logistics | Morning | 92 | 41.3% | 34 | 36 | 8.3% | 2.9%-21.8% | 7.8% | 1.000 | in line with peers |
| A3019 Sai Sandhu | Email Frontline | Morning | 105 | 36.2% | 30 | 35 | 17.1% | 8.1%-32.7% | 5.6% | 0.825 | in line with peers |
| A3031 Om Malhotra | Logistics | Morning | 112 | 34.8% | 30 | 50 | 10.0% | 4.3%-21.4% | 7.3% | 1.000 | in line with peers |
| A3014 Diya Patil | Chat Frontline | Morning | 42 | 33.3% | 14 | 28 | 0.0% | 0.0%-12.1% | 8.5% | 1.000 | in line with peers |
| A3032 Aadhya Sheikh | Billing | Morning | 73 | 32.9% | 19 | 37 | 5.4% | 1.5%-17.7% | 7.4% | 1.000 | in line with peers |
| A3037 Rahul Sen | Returns Desk | Morning | 103 | 31.1% | 29 | 45 | 6.7% | 2.3%-17.9% | 7.5% | 1.000 | in line with peers |
| A3018 Farah Sheikh | Email Frontline | Morning | 120 | 30.8% | 27 | 37 | 5.4% | 1.5%-17.7% | 7.1% | 1.000 | in line with peers |
| A3035 Rohit Mukherjee | Billing | Morning | 79 | 30.4% | 16 | 42 | 9.5% | 3.8%-22.1% | 7.6% | 1.000 | in line with peers |
| A3006 Lakshmi Reddy | Chat Frontline | Day | 42 | 14.3% | 0 | 39 | 12.8% | 5.6%-26.7% | 8.0% | 1.000 | in line with peers |
| A3012 Lakshmi Sethi | Chat Frontline | Day | 42 | 14.3% | 0 | 40 | 12.5% | 5.5%-26.1% | 8.1% | 1.000 | in line with peers |
| A3025 Lobsang Rao | Voice Frontline | Morning | 28 | 14.3% | 0 | 20 | 0.0% | 0.0%-16.1% | 4.6% | 1.000 | in line with peers |
| A3038 Amit Yadav | Returns Desk | Day | 39 | 12.8% | 3 | 32 | 6.2% | 1.7%-20.1% | 7.3% | 1.000 | in line with peers |
| A3003 Harpreet Deshpande | Chat Frontline | Day | 35 | 11.4% | 0 | 35 | 11.4% | 4.5%-26.0% | 8.1% | 1.000 | in line with peers |
| A3021 Aditya Dhillon | Email Frontline | Day | 55 | 10.9% | 2 | 33 | 0.0% | 0.0%-10.4% | 7.6% | 1.000 | in line with peers |
| A3004 Krishna Naidu | Chat Frontline | Day | 37 | 10.8% | 1 | 32 | 9.4% | 3.2%-24.2% | 8.1% | 1.000 | in line with peers |
| A3024 Kunal Khanna | Voice Frontline | Morning | 28 | 10.7% | 0 | 24 | 8.3% | 2.3%-25.8% | 3.6% | 1.000 | in line with peers |
| A3002 Tarun Mishra | Chat Frontline | Day | 38 | 10.5% | 0 | 37 | 10.8% | 4.3%-24.7% | 8.1% | 1.000 | in line with peers |
| A3023 Rahul Khanna | Voice Frontline | Day | 49 | 10.2% | 0 | 42 | 4.8% | 1.3%-15.8% | 4.0% | 1.000 | in line with peers |
| A3034 Thomas Patel | Billing | Day | 122 | 9.8% | 1 | 100 | 6.0% | 2.8%-12.5% | 6.9% | 1.000 | in line with peers |
| A3030 Sunita Srivastava | Logistics | Day | 53 | 9.4% | 2 | 42 | 2.4% | 0.4%-12.3% | 7.3% | 1.000 | in line with peers |
| A3022 Steven Tiwari | Email Frontline | Day | 64 | 9.4% | 0 | 38 | 2.6% | 0.5%-13.5% | 7.3% | 1.000 | in line with peers |
| A3036 Rohit Shinde | Returns Desk | Day | 40 | 7.5% | 2 | 30 | 3.3% | 0.6%-16.7% | 7.0% | 1.000 | in line with peers |
| A3027 Dev Chatterjee | Logistics | Day | 58 | 6.9% | 0 | 46 | 8.7% | 3.4%-20.3% | 7.0% | 1.000 | in line with peers |
| A3020 Ramesh Ghosh | Email Frontline | Day | 44 | 6.8% | 0 | 25 | 8.0% | 2.2%-25.0% | 7.6% | 1.000 | in line with peers |
| A3015 Yash Agarwal | Chat Frontline | Day | 36 | 5.6% | 0 | 33 | 6.1% | 1.7%-19.6% | 8.3% | 1.000 | in line with peers |
| A3026 Lakshmi Qureshi | Voice Frontline | Day | 41 | 4.9% | 0 | 41 | 4.9% | 1.3%-16.1% | 4.0% | 1.000 | in line with peers |
| A3029 Rajat Iyer | Logistics | Day | 45 | 4.4% | 0 | 36 | 5.6% | 1.5%-18.1% | 7.3% | 1.000 | in line with peers |

## 4. Money
Policy section 3: Rs 350 store credit per breached ticket, issued on resolution (resolved and auto-closed tickets count as issued; open/pending are shown as pending). Quarters are calendar quarters of ticket creation; the saving is what staffing the empty shift again would have avoided, simulated 5,000 times (seed 7) using that shift's own breach rate by channel from when it was staffed; the range is the 5th-95th percentile.

| quarter | tickets | breaches | credits issued | credits pending | of which unstaffed shift | unstaffed tickets (done) | their breaches | expected if staffed | simulated saving | saving 5-95% | cross-check saving |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|--:|
| 2025Q1 | 1,024 | 99 | Rs 32,550 | Rs 2,100 | Rs 0 | 0 | 0 | 0.0 | Rs 0 | Rs 0 to Rs 0 | Rs 0 |
| 2025Q2 | 1,242 | 112 | Rs 36,400 | Rs 2,800 | Rs 700 | 2 | 2 | 0.2 | Rs 646 | Rs 350 to Rs 700 | Rs 642 |
| 2025Q3 | 1,841 | 479 | Rs 158,900 | Rs 8,750 | Rs 110,600 | 384 | 316 | 38.4 | Rs 97,149 | Rs 91,700 to Rs 100,800 | Rs 95,652 |
| 2025Q4 | 2,572 | 614 | Rs 207,200 | Rs 7,700 | Rs 143,850 | 531 | 411 | 53.9 | Rs 124,987 | Rs 118,300 to Rs 129,850 | Rs 125,463 |
| 2026Q1 | 2,291 | 573 | Rs 190,050 | Rs 10,500 | Rs 136,150 | 501 | 389 | 51.2 | Rs 118,227 | Rs 111,300 to Rs 122,850 | Rs 118,437 |
| 2026Q2 (partial) | 2,199 | 560 | Rs 185,850 | Rs 10,150 | Rs 134,050 | 477 | 383 | 48.4 | Rs 117,096 | Rs 110,600 to Rs 121,450 | Rs 117,425 |

**How the simulated saving is built (last 13 weeks).** For each shift and channel: (1) count tickets created while the shift had nobody rostered and that are resolved/closed; (2) take that shift's breach rate from when it was staffed (breaches / tickets); (3) expected breaches = (1) x (2); (4) avoidable breaches = actual - expected; (5) saving = avoidable x Rs 350.

| shift | channel | (1) unstaffed tickets | actual breaches | staffed breaches | staffed tickets | baseline from | (2) rate | (3) expected | (4) avoidable | (5) saving |
|:--|:--|--:|--:|--:|--:|:--|--:|--:|--:|--:|
| Night | chat | 251 | 251 | 19 | 245 | Night while staffed | 7.8% | 19.5 | 231.5 | Rs 81,037 |
| Night | email | 190 | 103 | 27 | 202 | Night while staffed | 13.4% | 25.4 | 77.6 | Rs 27,161 |
| Night | social | 47 | 39 | 4 | 40 | Night while staffed | 10.0% | 4.7 | 34.3 | Rs 12,005 |

Total (5) = Rs 120,204; the 5-95% range comes from re-drawing the staffed rate and the breaches 5,000 times. Full audit trail for every quarter: `saving_steps_*.csv`.

*Cross-check saving* assumes the empty shift would have performed like the staffed shifts did on the same channel in the same quarter.

### Scaled to 650 tickets a week
In the last 13 weeks the desk created 2,249 tickets (173 a week). Simulated saving over that window: Rs 120,204 (range Rs 113,750 to Rs 124,600), i.e. Rs 53.45 per ticket created (Rs 120,204 / 2,249 tickets).

| volume | credits at current service | saving per quarter if Night staffed |
|:--|:--|:--|
| current (173/week) | Rs 191,450 | Rs 120,204 |
| 650/week | Rs 719,321 | Rs 451,632 (Rs 427,384 to Rs 468,150) |

Scaling assumes the same mix of channels and shifts as the last 13 weeks (about 23% of tickets arrive in an unstaffed shift) and the same breach rates when staffed.

Cost context (policy section 4): an agent-hour is Rs 165, a shift 8 hours, so one agent covering the empty shift every day of the week costs Rs 120,120 a quarter if it were new headcount. Headcount is frozen, so the realistic route is re-rostering existing agents, which is cost-neutral on payroll but not proven neutral on the other shifts' breach rates.

## 5. Method and caveats
- Export is UTC, converted to IST (+05:30); the voice-callback window 08:00-22:00 IST is used as a self-check on every run.
- Duplicate ticket_ids (migration re-import) are dropped keeping the helpdesk copy; legacy CSAT 0 is treated as blank.
- Shifts: Morning 06-14, Day 14-22, Night 22-06 IST; a Night shift belongs to the day it starts on. Staffing comes from the roster row in force on that day (one row per assignment).
- Resolver = `agent_id` on resolved/closed tickets, matched to the roster row on the resolution day. The data does not say who sent the first reply.
- The saving is a model, not an observation: it assumes the staffed rate seen before the gap (when the Night queue was smaller) still holds. Money figures use the status in the export; reports re-run for an earlier `--asof` still see the final status of each ticket.
