#!/usr/bin/env python
"""Independent validation of solution/breach_report.py.  Prints PASS/FAIL per check and saves the full log to
solution/outputs/validation_report.txt.  Exit code 1 if any check fails.

    python solution/validate.py

The reference implementation below uses only the standard library (csv, datetime, math) and shares NO code with the
tool. The tool (pandas) is imported only to obtain its answers so the two can be compared ticket by ticket.

Checks
  1. ticket-by-ticket agreement (every ticket: shift, breach, staffing, resolver, attribution)
  2. hand-derived golden cases (computed by hand from raw UTC rows, including shift and roster boundaries)
  3. timezone proof (voice-callback window; one offset only; same clock in both source systems)
  4. duplicates really identical
  5. backtest of a weekly detector: when it fires, false alarms before, and what the standard report would have said
  6. placebo: staffed shifts must not change, and fake cut-over dates must not look like the real one
  7. share of breaches whose owner cannot be known
  8. money audit: credits and the saving recomputed from scratch and compared with the tool's outputs
"""
from __future__ import annotations

import csv
import math
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data"
OUT = HERE / "outputs"
TOOL = HERE / "breach_report.py"

IST = timedelta(hours=5, minutes=30)
TARGET = {"chat": 15, "voice": 120, "social": 240, "email": 480}  # policy section 3, minutes
SHIFTS = ["Morning", "Day", "Night"]
DONE = ("resolved", "closed")
CUTOVER = date(2025, 6, 30)      # first day with no Night roster rows (roster shows Night agents end 2025-06-29)
CREDIT, WEEKS_Q, WINDOW_WEEKS, VOLUME = 350, 13, 13, 650


# =================================================================== independent reference implementation
def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d %H:%M")


def shift_of(dt: datetime) -> str:
    return "Morning" if 6 <= dt.hour < 14 else "Day" if 14 <= dt.hour < 22 else "Night"


def shift_day(dt: datetime) -> date:
    """A Night shift (22:00-06:00) belongs to the calendar day it starts on."""
    return (dt - timedelta(hours=6)).date()


def ticket_file() -> Path:
    for n in ("tickets.csv", "ticket.csv"):
        if (DATA / n).exists():
            return DATA / n
    raise SystemExit("ticket file not found in data/")


def load_raw() -> list[dict]:
    return read_csv(ticket_file())


def load_roster() -> list[dict]:
    out = []
    for r in read_csv(DATA / "agents.csv"):
        out.append({"agent": r["agent_id"], "shift": r["shift"], "tier": int(r["tier"]),
                    "from": date.fromisoformat(r["from_date"]),
                    "to": date.fromisoformat(r["to_date"]) if r["to_date"] else date(2999, 12, 31)})
    return out


def dedupe(rows: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for r in rows:
        k = r["ticket_id"]
        if k not in best or (best[k]["source_system"] != "helpdesk" and r["source_system"] == "helpdesk"):
            best[k] = r
    return list(best.values())


def reference(rows: list[dict], roster: list[dict]) -> dict[str, dict]:
    out = {}
    for r in dedupe(rows):
        created = parse(r["created_at"]) + IST
        reply = parse(r["first_response_at"]) + IST
        resolved = parse(r["resolved_at"]) + IST if r["resolved_at"] else None
        cs, sd = shift_of(created), shift_day(created)
        head = sum(1 for x in roster if x["shift"] == cs and x["from"] <= sd <= x["to"])
        resp = (reply - created).total_seconds() / 60.0
        breach = (reply - created) > timedelta(minutes=TARGET[r["channel"]])
        done = r["status"] in DONE and resolved is not None
        rshift = rtier = None
        if done:
            d = shift_day(resolved)
            for x in roster:
                if x["agent"] == r["agent_id"] and x["from"] <= d <= x["to"]:
                    rshift, rtier = x["shift"], x["tier"]
                    break
        if not breach:
            attr = ""
        elif head == 0:
            attr = "Unstaffed shift"
        elif done and rshift == cs:
            attr = "Agent's own shift"
        else:
            attr = "Unclear"
        out[r["ticket_id"]] = {
            "created": created, "reply": reply, "resolved": resolved, "channel": r["channel"], "status": r["status"],
            "agent": r["agent_id"], "cshift": cs, "sday": sd, "head": head, "resp": resp, "breach": breach,
            "done": r["status"] in DONE, "rshift": rshift, "rtier": rtier, "attr": attr}
    return out


# =================================================================== small statistics helpers
def diff_ci(k1: int, n1: int, k2: int, n2: int) -> tuple[float, float, float]:
    p1, p2 = k1 / n1, k2 / n2
    d = p2 - p1
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return d, d - 1.96 * se, d + 1.96 * se


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def pts(x: float) -> str:
    return f"{x * 100:+.1f} pts"


def monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def last_complete_week(asof: date) -> tuple[date, date]:
    end = asof - timedelta(days=asof.weekday() + 1)       # latest Sunday strictly before asof
    return end - timedelta(days=6), end


# =================================================================== result plumbing
class Result:
    def __init__(self, name: str):
        self.name, self.ok, self.lines = name, True, []

    def say(self, s: str = "") -> None:
        self.lines.append(s)

    def expect(self, cond: bool, msg: str) -> None:
        self.lines.append(("  ok    " if cond else "  FAIL  ") + msg)
        if not cond:
            self.ok = False


# =================================================================== 1. ticket-by-ticket vs the tool
def tool_outputs():
    sys.path.insert(0, str(HERE))
    import breach_report as tool  # imported only to read the tool's answers
    raw, roster = tool.load(DATA)
    return tool.classify(tool.clean(raw), roster)


def check_ticket_by_ticket(ref: dict, tk) -> Result:
    r = Result("Independent re-implementation agrees with the tool ticket by ticket")
    tool = {row.ticket_id: row for row in tk.itertuples()}
    r.expect(set(tool) == set(ref), f"same ticket set: reference {len(ref):,}, tool {len(tool):,}")
    fields = Counter()
    firsts = {}
    for tid, a in ref.items():
        b = tool[tid]
        rs = None if str(b.resolver_shift) in ("nan", "None", "<NA>") else b.resolver_shift
        pairs = {
            "created_shift": (a["cshift"], b.created_shift),
            "shift_day": (a["sday"], b.shift_date.date()),
            "breach": (a["breach"], bool(b.breach)),
            "response_minutes": (round(a["resp"], 6), round(float(b.resp_min), 6)),
            "headcount (staffing)": (a["head"], int(b.headcount)),
            "resolver_shift": (a["rshift"], rs),
            "attribution": (a["attr"], b.attribution if b.attribution else ""),
        }
        for f, (x, y) in pairs.items():
            if x != y:
                fields[f] += 1
                firsts.setdefault(f, (tid, x, y))
    for f in ["created_shift", "shift_day", "breach", "response_minutes", "headcount (staffing)", "resolver_shift", "attribution"]:
        r.expect(fields[f] == 0, f"{f}: {len(ref) - fields[f]:,} / {len(ref):,} agree"
                 + (f"  first disagreement {firsts[f]}" if fields[f] else ""))
    b = Counter(a["attr"] for a in ref.values() if a["breach"])
    r.say(f"  all-time breaches by reference: {sum(b.values()):,} = {dict(b)}")
    return r


# =================================================================== 2. golden cases (hand-derived)
GOLDEN = [
    # id, raw created UTC, raw reply UTC, what to expect after hand conversion (+05:30)
    ("TK-240267", "2025-01-26 14:54", "2025-01-26 15:09", dict(cshift="Day", breach=False),
     "20:24 IST, reply after exactly 15 min on chat: 15 is not later than 15, so NOT a breach"),
    ("TK-240187", "2025-01-21 19:38", "2025-01-21 19:54", dict(cshift="Night", breach=True, head=5, rshift="Night", attr="Agent's own shift"),
     "01:08 IST on 22 Jan = Night; 16 min > 15 so breach; Night had 5 agents; resolved by A3001 (Night until 29 Jun 2025) = own shift"),
    ("TK-241944", "2025-05-07 16:30", "2025-05-07 16:34", dict(cshift="Night", breach=False),
     "exactly 22:00 IST: Night starts at 22:00 (boundary)"),
    ("TK-240409", "2025-02-05 16:29", "2025-02-05 17:17", dict(cshift="Day", breach=False),
     "21:59 IST: still Day (boundary)"),
    ("TK-250820", "2026-03-16 00:29", "2026-03-16 01:29", dict(cshift="Night", breach=True, head=0, rshift="Morning", attr="Unstaffed shift", sday=date(2026, 3, 15)),
     "05:59 IST on 16 Mar = Night of 15 Mar; 60 min > 15 so breach; no Night roster after 29 Jun 2025, so Unstaffed (resolved by a Morning agent)"),
    ("TK-244029", "2025-08-22 00:30", "2025-08-22 00:45", dict(cshift="Morning", breach=False),
     "exactly 06:00 IST: Morning starts at 06:00 (boundary); 15 min on chat is not a breach"),
    ("TK-242834", "2025-06-29 19:31", "2025-06-29 19:39", dict(cshift="Night", breach=False, head=5, sday=date(2025, 6, 29)),
     "01:01 IST on 30 Jun = Night shift that STARTED 29 Jun, so Night still has its 5 agents"),
    ("TK-253797", "2026-06-21 19:30", "2026-06-22 01:03", dict(cshift="Night", breach=True, head=0, rshift="Morning", attr="Unstaffed shift", sday=date(2026, 6, 21)),
     "01:00 IST on 22 Jun = Night of 21 Jun; reply 333 min later (06:33 IST) = breach; unstaffed; resolved by A3028 (Morning)"),
    ("TK-242846", "2025-06-30 12:05", None, dict(cshift="Day", rshift="Day"),
     "resolved by A3002 at 18:53 IST on 30 Jun; A3002's roster row is Day from 30 Jun (was Night to 29 Jun)"),
]


def check_golden(ref: dict, tk, raw_rows: list[dict]) -> Result:
    r = Result("Hand-derived golden cases (raw UTC rows -> expected output) match reference AND tool")
    tool = {row.ticket_id: row for row in tk.itertuples()}
    rawby = {x["ticket_id"]: x for x in raw_rows if x["source_system"] == "helpdesk"} | \
            {x["ticket_id"]: x for x in raw_rows if x["ticket_id"] not in {y["ticket_id"] for y in raw_rows if y["source_system"] == "helpdesk"}}
    for tid, c_utc, f_utc, want, why in GOLDEN:
        row = rawby.get(tid)
        data_ok = row is not None and row["created_at"] == c_utc and (f_utc is None or row["first_response_at"] == f_utc)
        a, b = ref[tid], tool[tid]
        got = {"cshift": (a["cshift"], b.created_shift), "breach": (a["breach"], bool(b.breach)), "head": (a["head"], int(b.headcount)),
               "rshift": (a["rshift"], None if str(b.resolver_shift) == "nan" else b.resolver_shift),
               "attr": (a["attr"], b.attribution), "sday": (a["sday"], b.shift_date.date())}
        bad = [k for k, v in want.items() if got[k] != (v, v)]
        r.expect(data_ok and not bad, f"{tid}: {why}" + ("" if data_ok else "  [RAW ROW NOT AS EXPECTED]") +
                 (f"  mismatch on {bad}: {[got[k] for k in bad]}" if bad else ""))
    return r


# =================================================================== 3. timezone proof
def check_timezone(raw_rows: list[dict]) -> Result:
    r = Result("Timezone proof: the export is UTC and +05:30 is the only offset consistent with IVR hours")
    voice = [x for x in raw_rows if x["channel"] == "voice"]
    mins = [(parse(x["created_at"]).hour * 60 + parse(x["created_at"]).minute, x["source_system"]) for x in voice]

    def inside(sel, off):
        sel = [m for m, _ in sel]
        return sum(1 for m in sel if 480 <= (m + off) % 1440 <= 1320) / len(sel)

    full = [off / 60 for off in range(-12 * 60, 14 * 60 + 1, 30) if inside(mins, off) == 1.0]
    r.say(f"  {len(voice):,} voice rows. Offsets (hours, 30-min steps from -12 to +14) putting 100% inside 08:00-22:00: {full}")
    r.expect(full == [5.5], "exactly one offset works and it is +5.5 h")
    r.say(f"  left as exported (UTC): {inside(mins, 0):.1%} inside the window; raw clock range "
          f"{min(m for m, _ in mins) // 60:02d}:{min(m for m, _ in mins) % 60:02d}-{max(m for m, _ in mins) // 60:02d}:{max(m for m, _ in mins) % 60:02d}")
    for s in ("helpdesk", "legacy_fd"):
        sel = [(m, x) for m, x in mins if x == s]
        r.expect(inside(sel, 330) == 1.0, f"{s}: {len(sel):,} voice rows all inside 08:00-22:00 after +05:30")
    # the migration duplicates carry the same timestamps in both systems => the same clock
    by = defaultdict(dict)
    for x in raw_rows:
        by[x["ticket_id"]][x["source_system"]] = x
    pairs = [v for v in by.values() if len(v) == 2]
    same = sum(1 for v in pairs if all(v["helpdesk"][c] == v["legacy_fd"][c] for c in ("created_at", "first_response_at", "resolved_at")))
    r.expect(same == len(pairs), f"legacy and helpdesk copies of the same ticket carry identical timestamps ({same:,}/{len(pairs):,}) -> one clock")
    # a later-hours sanity check: callbacks are IVR-requested 08-22; first replies for voice never precede creation
    neg = sum(1 for x in raw_rows if parse(x["first_response_at"]) < parse(x["created_at"]))
    r.expect(neg == 0, "no first reply earlier than creation in any row (offset-independent consistency)")
    return r


# =================================================================== 4. duplicates
def check_duplicates(raw_rows: list[dict]) -> Result:
    r = Result("Duplicate ticket_ids are the same ticket (only the CSAT placeholder differs)")
    by = defaultdict(list)
    for x in raw_rows:
        by[x["ticket_id"]].append(x)
    dup = {k: v for k, v in by.items() if len(v) > 1}
    r.say(f"  {len(raw_rows):,} rows, {len(by):,} unique ids, {len(dup):,} ids appear more than once")
    r.expect(all(len(v) == 2 for v in dup.values()), "no id appears more than twice")
    r.expect(all(sorted(x["source_system"] for x in v) == ["helpdesk", "legacy_fd"] for v in dup.values()),
             "every duplicated id is exactly one helpdesk row + one legacy_fd row")
    cols = [c for c in raw_rows[0] if c not in ("source_system", "csat_score")]
    diffs = Counter()
    for v in dup.values():
        for c in cols:
            if v[0][c] != v[1][c]:
                diffs[c] += 1
    r.expect(not diffs, f"all {len(cols)} other columns identical in every pair" + (f"  DIFFERENCES: {dict(diffs)}" if diffs else ""))
    csat_pat = Counter()
    for v in dup.values():
        h = next(x for x in v if x["source_system"] == "helpdesk")["csat_score"]
        l = next(x for x in v if x["source_system"] == "legacy_fd")["csat_score"]
        csat_pat["equal" if h == l else "helpdesk blank / legacy 0" if (h == "" and l in ("0", "0.0")) else "OTHER"] += 1
    r.say(f"  csat pattern across pairs: {dict(csat_pat)}")
    r.expect(csat_pat["OTHER"] == 0, "CSAT differs only as helpdesk-blank vs legacy-0 (the documented placeholder)")
    last = max(parse(x["created_at"]).date() for v in dup.values() for x in v)
    r.expect(last < date(2025, 9, 14), f"duplicates all pre-date the helpdesk go-live of 14 Sep 2025 (latest created {last})")
    # dropping the legacy copy cannot change any breach decision: both copies give the same answer
    flips = 0
    for v in dup.values():
        res = {(parse(x["first_response_at"]) - parse(x["created_at"])) > timedelta(minutes=TARGET[x["channel"]]) for x in v}
        flips += len(res) > 1
    r.expect(flips == 0, "both copies of every pair give the same breach result")
    return r


# =================================================================== 5. backtest of a weekly detector
def weekly_table(items, weeks):
    """items: iterable of (week_monday, label, breach). -> {(week,label): [n,k]}"""
    t: dict = defaultdict(lambda: [0, 0])
    for w, lab, b in items:
        t[(w, lab)][0] += 1
        t[(w, lab)][1] += int(b)
    return t


def detect(tab, weeks, labels, base_weeks=8, min_base=30, min_week=10, z=3.0, min_jump=0.10):
    """Weekly rule: alarm when the week's rate exceeds the trailing-8-week pooled rate by z standard errors
    (and by at least min_jump), with enough tickets to say anything."""
    alarms, tests = [], []
    for i, w in enumerate(weeks):
        if i < base_weeks:
            continue
        for lab in labels:
            n, k = tab[(w, lab)]
            n0 = sum(tab[(weeks[j], lab)][0] for j in range(i - base_weeks, i))
            k0 = sum(tab[(weeks[j], lab)][1] for j in range(i - base_weeks, i))
            if n0 < min_base or n < min_week:
                continue
            p0, p = k0 / n0, k / n
            lim = p0 + z * math.sqrt(p0 * (1 - p0) / n)
            tests.append((w, lab))
            if p > lim and p - p0 >= min_jump:
                alarms.append((w, lab, p, p0))
    return alarms, tests


def check_backtest(ref: dict) -> Result:
    r = Result("Backtest: a weekly detector fires right after the roster change, with no false alarms before it")
    last_created = max(a["created"] for a in ref.values()).date()
    _, last_end = last_complete_week(last_created + timedelta(days=1))
    first_week = monday(min(a["created"] for a in ref.values()).date())
    weeks, w = [], first_week
    while w + timedelta(days=6) <= last_end:
        weeks.append(w)
        w += timedelta(days=7)
    cut_week = monday(CUTOVER)

    # fair view: weekly breach rate by the shift the ticket was CREATED in
    fair = weekly_table(((monday(a["created"].date()), a["cshift"], a["breach"]) for a in ref.values()
                         if monday(a["created"].date()) in set(weeks)), weeks)
    # standard helpdesk view: weekly breach rate by the shift of the agent who RESOLVED the ticket
    std = weekly_table(((monday(a["resolved"].date()), a["rshift"], a["breach"]) for a in ref.values()
                        if a["done"] and a["rshift"] and monday(a["resolved"].date()) in set(weeks)), weeks)

    alarms, tests = detect(fair, weeks, SHIFTS)
    pre_tests = [t for t in tests if t[0] < cut_week]
    pre_alarms = [a for a in alarms if a[0] < cut_week]
    night_post = sorted(a for a in alarms if a[1] == "Night" and a[0] >= cut_week)
    staffed_post = [a for a in alarms if a[1] != "Night" and a[0] >= cut_week]
    r.say(f"  {len(weeks)} complete weeks ({weeks[0]} .. {weeks[-1]}); rule: weekly rate > trailing-8-week rate + 3 standard errors and >= +10 pts, "
          f">=10 tickets in the week, >=30 in the baseline")
    r.say(f"  roster change takes effect on Mon {cut_week}; a weekly report on that week is run the following Monday")
    r.expect(len(pre_tests) > 0 and not pre_alarms,
             f"false alarms before the change: {len(pre_alarms)} of {len(pre_tests)} shift-weeks tested ({', '.join(f'{a[0]} {a[1]}' for a in pre_alarms) or 'none'})")
    first = night_post[0] if night_post else None
    lag = (first[0] + timedelta(days=7) - CUTOVER).days if first else None
    r.expect(first is not None and first[0] == cut_week,
             f"Night alarm in the first week after the change: {first[0] if first else 'never'} "
             f"(rate {pct(first[2]) if first else '-'} vs baseline {pct(first[3]) if first else '-'}); report available {lag} days after the change"
             if first else "Night alarm never fired")
    n_after = sum(1 for a in night_post)
    n_tests_after = len([t for t in tests if t[1] == "Night" and t[0] >= cut_week])
    r.say(f"  Night alarms after the change: {n_after} of {n_tests_after} weeks (baseline re-learns the new level, so alarms fade by design; "
          f"they fire in the weeks it matters: {[str(a[0]) for a in night_post[:6]]})")
    r.expect(not staffed_post, f"alarms on staffed shifts (Morning/Day) after the change: {len(staffed_post)} of "
                               f"{len([t for t in tests if t[1] != 'Night' and t[0] >= cut_week])} shift-weeks")
    # sensitivity of the rule
    r.say("  sensitivity (z, min_jump): false alarms before / weeks until Night alarm")
    for z, mj in [(2, 0.0), (2, 0.10), (3, 0.0), (3, 0.10), (4, 0.10)]:
        al, te = detect(fair, weeks, SHIFTS, z=z, min_jump=mj)
        pre = [a for a in al if a[0] < cut_week]
        npst = sorted(a[0] for a in al if a[1] == "Night" and a[0] >= cut_week)
        r.say(f"    z={z}, jump>={mj:.2f}: {len(pre)} false alarm(s) in {len([t for t in te if t[0] < cut_week])} tests; "
              f"Night first alarm {npst[0] if npst else 'never'}")
    # roster-based detector: zero rostered agents on a shift is visible on day 0
    roster = load_roster()
    first_gap = min(d for d in (CUTOVER + timedelta(days=i) for i in range(0, 5))
                    if not any(x["shift"] == "Night" and x["from"] <= d <= x["to"] for x in roster))
    r.say(f"  roster check (zero agents rostered on a shift): fires on {first_gap}, i.e. day 0 - the data-driven detector confirms it and sizes the damage")

    # what the standard (resolver) view would have alarmed on
    s_alarms, _ = detect(std, weeks, SHIFTS)
    s_post = sorted((a[0], a[1]) for a in s_alarms if a[0] >= cut_week)
    s_pre = [a for a in s_alarms if a[0] < cut_week]
    first_std = s_post[0] if s_post else None
    r.say(f"  standard resolver-view alarms: before the change {len(s_pre)}; after: first {first_std}; shifts alarmed after: "
          f"{dict(Counter(a[1] for a in s_alarms if a[0] >= cut_week))}")
    r.expect(first_std is not None and first_std[1] == "Morning" and not any(a[1] == "Night" for a in s_alarms),
             "the standard report points at Morning and never at Night (the shift that actually lost its staff) - the misattribution is real")
    return r


# =================================================================== 6. placebo
def shift_rates(ref, label_shift, lo: date, hi: date):
    n = k = 0
    for a in ref.values():
        if a["cshift"] == label_shift and lo <= a["sday"] < hi:
            n += 1
            k += a["breach"]
    return k, n


def check_placebo(ref: dict) -> Result:
    r = Result("Placebo: staffed shifts do not move at the change; fake change dates on Night do not look like the real one")
    first = min(a["sday"] for a in ref.values())
    end = max(a["sday"] for a in ref.values()) + timedelta(days=1)
    real = {}
    for s in SHIFTS:
        k1, n1 = shift_rates(ref, s, first, CUTOVER)
        k2, n2 = shift_rates(ref, s, CUTOVER, end)
        real[s] = diff_ci(k1, n1, k2, n2)
        r.say(f"  real change, {s:7s}: {pct(k1 / n1)} -> {pct(k2 / n2)}  ({pts(real[s][0])}, 95% CI {pts(real[s][1])} to {pts(real[s][2])}; n {n1:,} -> {n2:,})")
    for s in ("Morning", "Day"):
        d, lo, hi = real[s]
        r.expect(lo > -0.05 and hi < 0.05, f"{s} (staffed throughout): CI {pts(lo)} to {pts(hi)} excludes any effect of 5 pts or more")
    r.expect(real["Night"][1] > 0.5, f"Night: even the low end of the CI is {pts(real['Night'][1])}")

    # placebo-in-time: pretend the change happened on a Monday inside the staffed period; 8 weeks each side
    deltas = defaultdict(list)
    s0 = date(2025, 3, 3)
    splits = []
    while s0 + timedelta(weeks=8) <= CUTOVER:
        splits.append(s0)
        s0 += timedelta(weeks=1)
    for sp in splits:
        for s in SHIFTS:
            k1, n1 = shift_rates(ref, s, sp - timedelta(weeks=8), sp)
            k2, n2 = shift_rates(ref, s, sp, sp + timedelta(weeks=8))
            if n1 >= 30 and n2 >= 30:
                d, lo, hi = diff_ci(k1, n1, k2, n2)
                deltas[s].append((d, lo, hi, sp))
    for s in SHIFTS:
        ds = deltas[s]
        worst = max(ds, key=lambda x: abs(x[0]))
        sig = sum(1 for d, lo, hi, _ in ds if lo > 0 or hi < 0)
        r.say(f"  placebo {s:7s}: {len(ds)} fake change dates (Mondays {splits[0]} .. {splits[-1]}), largest |change| {pts(worst[0])} on {worst[3]}, "
              f"{sig} of {len(ds)} 'significant' (windows overlap, so these are not independent)")
    worst_night = max(abs(d[0]) for d in deltas["Night"])
    r.expect(worst_night < real["Night"][0] / 3,
             f"largest fake Night change ({pts(worst_night)}) is under one third of the real one ({pts(real['Night'][0])})")
    r.expect(all(abs(d[0]) < 0.10 for s in ("Morning", "Day") for d in deltas[s]),
             "fake changes on Morning/Day never exceed 10 pts")
    # placebo-in-space: the same before/after contrast on a staffed shift, split by channel
    for ch in ("chat", "email"):
        for s in ("Morning", "Day"):
            def rate(lo, hi):
                n = k = 0
                for a in ref.values():
                    if a["cshift"] == s and a["channel"] == ch and lo <= a["sday"] < hi:
                        n += 1
                        k += a["breach"]
                return k, n
            d, lo, hi = diff_ci(*rate(first, CUTOVER), *rate(CUTOVER, end))
            r.expect(lo < 0.05 and hi > -0.05 and abs(d) < 0.10, f"{s} {ch}: change {pts(d)} (CI {pts(lo)} to {pts(hi)})")
    return r


# =================================================================== 7. owner share
def check_owner_share(ref: dict) -> Result:
    r = Result("Share of breaches whose owner cannot be known")
    br = [a for a in ref.values() if a["breach"]]
    c = Counter(a["attr"] for a in br)
    n = len(br)
    r.expect(sum(c.values()) == n, f"three buckets reconcile to {n:,} breaches: {dict(c)}")
    unst, own, unc = c["Unstaffed shift"], c["Agent's own shift"], c["Unclear"]
    r.say(f"  Unstaffed shift (owner = the roster gap, knowable): {unst:,} = {pct(unst / n)}")
    r.say(f"  Agent's own shift (resolver was on shift when ticket was created; inference, not a record): {own:,} = {pct(own / n)}")
    r.say(f"  Unclear (resolved by a different shift, unresolved, or resolver off roster): {unc:,} = {pct(unc / n)}")
    outside = [a for a in br if a["attr"] == "Agent's own shift" and shift_of(a["reply"]) != a["rshift"]]
    r.say(f"  of the own-shift breaches, {len(outside):,} ({pct(len(outside) / own)}) had their first reply timestamped outside the resolver's shift hours, "
          f"so even the 'own shift' label may not mean the resolver sent the late reply")
    cannot_agent = unc + own
    r.say(f"  => breaches that cannot be pinned on a named agent: {pct(cannot_agent / n)} of all breaches "
          f"(100% of the {cannot_agent:,} staffed-shift breaches - the export never records WHO sent the first reply)")
    r.say(f"  => breaches with a shift-level owner we can defend: {pct(unst / n)} (roster gap) plus {pct((own - len(outside)) / n)} (own shift, reply inside shift hours)")
    post = [a for a in br if a["sday"] >= CUTOVER]
    cp = Counter(a["attr"] for a in post)
    r.say(f"  from 30 Jun 2025 only: unstaffed {pct(cp['Unstaffed shift'] / len(post))}, own {pct(cp[chr(65) + 'gent' + chr(39) + 's own shift'] / len(post))}, "
          f"unclear {pct(cp['Unclear'] / len(post))} of {len(post):,} breaches")
    r.expect(cannot_agent / n > 0, "reported (informational); agent-level conclusions must carry this caveat")
    return r


# =================================================================== 8. money audit
def money_audit(ref: dict, tool_dir: Path) -> Result:
    r = Result("Money audit: credits and the saving recomputed from scratch match the tool's outputs")
    last_created = max(a["created"] for a in ref.values()).date()
    wk_start, wk_end = last_complete_week(last_created + timedelta(days=1))
    data = [a for a in ref.values() if a["created"].date() <= wk_end]
    r.say(f"  report week: Mon {wk_start} - Sun {wk_end}; history used: tickets created up to {wk_end} ({len(data):,})")

    # ---- this week's credits
    wk = [a for a in data if wk_start <= a["created"].date() <= wk_end]
    br = [a for a in wk if a["breach"]]
    iss = sum(1 for a in br if a["done"])
    r.say(f"  STEP 1  tickets created this week {len(wk)}; breaches {len(br)}; resolved/closed {iss}; open/pending {len(br) - iss}")
    r.say(f"  STEP 2  credits issued = {iss} x Rs {CREDIT} = Rs {iss * CREDIT:,};  pending = {len(br) - iss} x Rs {CREDIT} = Rs {(len(br) - iss) * CREDIT:,}")
    tag = wk_start.isoformat()
    with open(tool_dir / f"breaches_{tag}.csv", newline="", encoding="utf-8") as f:
        t = list(csv.DictReader(f))
    r.expect(len(t) == len(br), f"tool's breach list has {len(t)} rows, reference {len(br)}")
    r.expect(sum(float(x["credit_inr"]) for x in t) == iss * CREDIT and sum(float(x["credit_pending_inr"]) for x in t) == (len(br) - iss) * CREDIT,
             f"tool's credits: issued Rs {sum(float(x['credit_inr']) for x in t):,.0f}, pending Rs {sum(float(x['credit_pending_inr']) for x in t):,.0f}")
    refattr = {tid: a["attr"] for tid, a in ref.items()}
    r.expect(all(x["attribution"] == refattr[x["ticket_id"]] for x in t), "every breach row in the tool's CSV carries the same attribution as the reference")

    # ---- credits by quarter
    with open(tool_dir / f"credits_by_quarter_{tag}.csv", newline="", encoding="utf-8") as f:
        q = {x["quarter"].split()[0]: x for x in csv.DictReader(f)}
    qs = defaultdict(lambda: [0, 0, 0])
    for a in data:
        key = f"{a['created'].year}Q{(a['created'].month - 1) // 3 + 1}"
        if a["breach"]:
            qs[key][0 if a["done"] else 1] += 1
            if a["done"] and a["head"] == 0:
                qs[key][2] += 1
    bad = [k for k, (i, p, u) in qs.items() if
           (float(q[k]["credits_issued_inr"]), float(q[k]["credits_pending_inr"]), float(q[k]["credits_from_unstaffed_inr"])) != (i * CREDIT, p * CREDIT, u * CREDIT)]
    r.expect(not bad and set(qs) <= set(q), f"credits by quarter (issued / pending / from unstaffed shifts) agree for all {len(qs)} quarters" + (f"  mismatches {bad}" if bad else ""))
    tot = sum(i for i, _, _ in qs.values())
    r.say(f"          all-time credits issued: {tot:,} x Rs {CREDIT} = Rs {tot * CREDIT:,}")

    # ---- the saving, from scratch, for the last 13 weeks
    w_lo = wk_end - timedelta(days=7 * WINDOW_WEEKS - 1)
    staffed = [a for a in data if a["head"] > 0]
    by_sc = defaultdict(lambda: [0, 0])
    by_c = defaultdict(lambda: [0, 0])
    for a in staffed:
        by_sc[(a["cshift"], a["channel"])][0] += 1
        by_sc[(a["cshift"], a["channel"])][1] += a["breach"]
        by_c[a["channel"]][0] += 1
        by_c[a["channel"]][1] += a["breach"]
    win = [a for a in data if w_lo <= a["created"].date() <= wk_end]
    unst = [a for a in win if a["head"] == 0 and a["done"]]
    r.say("")
    r.say(f"  SAVING, last {WINDOW_WEEKS} weeks ({w_lo} .. {wk_end}) - every number below can be checked with a calculator")
    r.say("  STEP 3  tickets created while the shift had NOBODY rostered and later resolved/closed, by shift and channel; how many breached")
    r.say("  STEP 4  baseline = that shift's breach rate while it WAS staffed = breaches / tickets (all staffed history up to the report week)")
    r.say("  STEP 5  expected breaches if staffed = (STEP 3 tickets) x (STEP 4 rate);  avoidable = actual - expected;  saving = avoidable x Rs 350")
    r.say(f"  {'shift':6s} {'chan':6s} {'unstaffed':>9s} {'actual':>7s} | {'staffed k/n':>12s} {'rate':>7s} | {'expected':>8s} {'avoidable':>9s} {'saving Rs':>10s}")
    grp = defaultdict(lambda: [0, 0])
    for a in unst:
        grp[(a["cshift"], a["channel"])][0] += 1
        grp[(a["cshift"], a["channel"])][1] += a["breach"]
    total_exp = total_save = 0.0
    ref_steps = {}
    for (s, c), (n, k) in sorted(grp.items()):
        bn, bk = by_sc[(s, c)] if by_sc[(s, c)][0] >= 30 else by_c[c]
        rate = bk / bn
        exp = n * rate
        sav = (k - exp) * CREDIT
        total_exp += exp
        total_save += sav
        ref_steps[(s, c)] = (n, k, bk, bn, exp, sav)
        r.say(f"  {s:6s} {c:6s} {n:9d} {k:7d} | {f'{bk}/{bn}':>12s} {pct(rate):>7s} | {exp:8.2f} {k - exp:9.2f} {sav:10,.0f}")
    r.say(f"  {'TOTAL':13s} {sum(v[0] for v in ref_steps.values()):9d} {sum(v[1] for v in ref_steps.values()):7d} | {'':12s} {'':7s} | {total_exp:8.2f} "
          f"{sum(v[1] for v in ref_steps.values()) - total_exp:9.2f} {total_save:10,.0f}")
    with open(tool_dir / f"saving_steps_{tag}.csv", newline="", encoding="utf-8") as f:
        ts = [x for x in csv.DictReader(f) if x["period"] == f"last {WINDOW_WEEKS} weeks"]
    ok = len(ts) == len(ref_steps)
    for x in ts:
        v = ref_steps.get((x["shift"], x["channel"]))
        ok &= v is not None and int(x["unstaffed_tickets"]) == v[0] and int(x["actual_breaches"]) == v[1] and \
              int(x["baseline_breaches"]) == v[2] and int(x["baseline_tickets"]) == v[3] and abs(float(x["saving_inr"]) - v[5]) < 0.01
    r.expect(ok, f"tool's saving_steps rows match line by line; tool total Rs {sum(float(x['saving_inr']) for x in ts):,.2f} vs reference Rs {total_save:,.2f}")

    # ---- scaling to 650 tickets a week
    n_win = len(win)
    per_ticket = total_save / n_win
    q650 = per_ticket * VOLUME * WEEKS_Q
    r.say("")
    r.say(f"  STEP 6  per ticket created = Rs {total_save:,.0f} / {n_win:,} tickets in the window = Rs {per_ticket:,.4f}")
    r.say(f"  STEP 7  at {VOLUME} tickets/week for {WEEKS_Q} weeks = {VOLUME * WEEKS_Q:,} tickets a quarter;  Rs {per_ticket:,.4f} x {VOLUME * WEEKS_Q:,} = Rs {q650:,.0f} a quarter")
    report = (tool_dir / f"weekly_report_{tag}.md").read_text(encoding="utf-8")
    r.expect(f"Rs {round(total_save):,}" in report, f"report quotes the window saving Rs {round(total_save):,}")
    r.expect(f"Rs {round(q650):,}" in report, f"report quotes the 650/week figure Rs {round(q650):,} a quarter")
    r.expect(f"Rs {per_ticket:,.2f} per ticket" in report, f"report quotes Rs {per_ticket:,.2f} per ticket created")
    r.say(f"  context: actual credits issued in the window = {sum(1 for a in win if a['breach'] and a['done'])} x Rs {CREDIT} = "
          f"Rs {sum(1 for a in win if a['breach'] and a['done']) * CREDIT:,}")
    return r


# =================================================================== runner
def main() -> int:
    raw_rows = load_raw()
    roster = load_roster()
    ref = reference(raw_rows, roster)
    print("Running the tool and loading its answers ...", flush=True)
    tk = tool_outputs()
    with tempfile.TemporaryDirectory() as tmp:
        p = subprocess.run([sys.executable, str(TOOL), "--out-dir", tmp], capture_output=True, text=True)
        if p.returncode != 0:
            print(p.stdout, p.stderr)
            print("FAIL: the tool did not run")
            return 1
        results = [
            check_ticket_by_ticket(ref, tk),
            check_golden(ref, tk, raw_rows),
            check_timezone(raw_rows),
            check_duplicates(raw_rows),
            check_backtest(ref),
            check_placebo(ref),
            check_owner_share(ref),
            money_audit(ref, Path(tmp)),
        ]
    lines = [f"Validation of solution/breach_report.py - run {datetime.now():%Y-%m-%d %H:%M}",
             "Reference implementation: standard library only, no shared code with the tool.", ""]
    for i, res in enumerate(results, 1):
        lines.append(f"[{'PASS' if res.ok else 'FAIL'}] {i}. {res.name}")
        lines.extend(res.lines)
        lines.append("")
    passed = sum(r.ok for r in results)
    lines.append(f"SUMMARY: {passed}/{len(results)} checks passed" + ("" if passed == len(results) else "  <-- FAILURES ABOVE"))
    text = "\n".join(lines)
    print(text)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "validation_report.txt").write_text(text + "\n", encoding="utf-8")
    print(f"\nSaved {OUT / 'validation_report.txt'}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
