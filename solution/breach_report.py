#!/usr/bin/env python
"""Weekly first-response SLA breach report for the Vireo Audio support desk.

Fair version of "breaches by agent and shift": every breach is labelled as
  * Unstaffed shift  - the ticket was created in a shift with nobody rostered,
  * Agent's own shift - created during the resolving agent's shift (plausibly theirs),
  * Unclear           - everything else (resolved by another shift, not resolved yet, ...).

Usage (from anywhere; pandas + numpy only, no network):
    python solution/breach_report.py                      # last complete week in the export
    python solution/breach_report.py --asof 2026-06-15    # as the report would have run on that date
    python solution/breach_report.py --help

Conventions
    * Timestamps in the helpdesk-API export are UTC; everything is converted to IST (+05:30), policy section 9.
    * Weeks run Monday-Sunday by IST creation date. "Last complete week" = the latest Sunday strictly
      before --asof. Default --asof = the day after the last ticket in the export.
    * Shifts (IST): Morning 06-14, Day 14-22, Night 22-06. A Night shift belongs to the day it starts on.
    * Breach = first human reply later than the channel target (policy section 3).
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

IST = pd.Timedelta(hours=5, minutes=30)
SHIFTS = ["Morning", "Day", "Night"]
TARGET_MIN = {"chat": 15, "voice": 120, "social": 240, "email": 480}  # policy section 3
UNSTAFFED, OWN, UNCLEAR = "Unstaffed shift", "Agent's own shift", "Unclear"
DONE = ("resolved", "closed")  # policy section 10: attendance; credit is issued on resolution

HERE = Path(__file__).resolve().parent


# --------------------------------------------------------------------------- loading and cleaning
def find_file(data_dir: Path, names: list[str]) -> Path:
    for n in names:
        if (data_dir / n).exists():
            return data_dir / n
    raise SystemExit(f"error: none of {names} found in {data_dir}")


def load(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    tickets = pd.read_csv(find_file(data_dir, ["tickets.csv", "ticket.csv"]), dtype={"csat_score": float})
    roster = pd.read_csv(find_file(data_dir, ["agents.csv"]), parse_dates=["from_date", "to_date"])
    need = {"ticket_id", "created_at", "first_response_at", "resolved_at", "status", "channel",
            "agent_id", "source_system", "priority", "assigned_team"}
    missing = need - set(tickets.columns)
    if missing:
        raise SystemExit(f"error: tickets file is missing columns {sorted(missing)}")
    roster = roster.rename(columns={"shift": "agent_shift"})
    roster["to_date"] = roster["to_date"].fillna(pd.Timestamp("2099-12-31"))
    return tickets, roster


def warn(msg: str) -> None:
    print(f"warning: {msg}", file=sys.stderr)


def check_utc(raw: pd.DataFrame) -> None:
    """Voice callbacks are only taken 08:00-22:00 IST (policy section 2): a cheap proof the export is UTC."""
    v = pd.to_datetime(raw.loc[raw.channel == "voice", "created_at"])
    if v.empty:
        return
    mins = v.dt.hour * 60 + v.dt.minute
    inside = lambda off: (((mins + off) % 1440 >= 480) & ((mins + off) % 1440 <= 1320)).mean()
    if inside(330) < 0.99:
        warn(f"only {inside(330):.0%} of voice tickets fall in 08:00-22:00 after UTC->IST; "
             f"({inside(0):.0%} if left as-is) - check the export's timezone before trusting shifts")


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    check_utc(raw)
    tk = (raw.assign(_legacy=raw.source_system.ne("helpdesk"))
             .sort_values(["ticket_id", "_legacy"], kind="stable")
             .drop_duplicates("ticket_id", keep="first").drop(columns="_legacy").reset_index(drop=True))
    for c in ("created_at", "first_response_at", "resolved_at"):
        tk[c + "_ist"] = pd.to_datetime(tk[c]) + IST
    tk = tk.drop(columns=["created_at", "first_response_at", "resolved_at"])
    tk["csat_score"] = tk.csat_score.replace(0, np.nan)  # legacy 0 == no response
    unknown = set(tk.channel) - set(TARGET_MIN)
    if unknown:
        raise SystemExit(f"error: no first-response target for channel(s) {sorted(unknown)}")
    tk["resp_min"] = (tk.first_response_at_ist - tk.created_at_ist).dt.total_seconds() / 60
    tk["target_min"] = tk.channel.map(TARGET_MIN)
    tk["breach"] = tk.resp_min > tk.target_min
    h = tk.created_at_ist.dt.hour
    tk["created_shift"] = np.select([(h >= 6) & (h < 14), (h >= 14) & (h < 22)], ["Morning", "Day"], "Night")
    tk["shift_date"] = (tk.created_at_ist - pd.Timedelta(hours=6)).dt.normalize()
    tk["created_date"] = tk.created_at_ist.dt.normalize()
    tk["quarter"] = tk.created_at_ist.dt.to_period("Q").astype(str)
    return tk


# --------------------------------------------------------------------------- roster, staffing, attribution
def staffing_table(roster: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    days = pd.date_range(start, end)
    out = pd.DataFrame(0, index=days, columns=SHIFTS)
    for r in roster.itertuples():
        lo, hi = max(r.from_date, start), min(r.to_date, end)
        if lo <= hi and r.agent_shift in SHIFTS:
            out.loc[lo:hi, r.agent_shift] += 1
    return out


def classify(tk: pd.DataFrame, roster: pd.DataFrame) -> pd.DataFrame:
    stf = staffing_table(roster, tk.shift_date.min() - pd.Timedelta(days=2), tk.shift_date.max() + pd.Timedelta(days=2))
    tk = tk.copy()
    tk["headcount"] = 0
    for s in SHIFTS:
        m = tk.created_shift == s
        tk.loc[m, "headcount"] = stf[s].reindex(tk.loc[m, "shift_date"]).to_numpy()

    # resolver = the roster row in force on the (shift) day the ticket was resolved
    done = tk[tk.status.isin(DONE) & tk.resolved_at_ist.notna()].copy()
    done["_d"] = (done.resolved_at_ist - pd.Timedelta(hours=6)).dt.normalize()
    j = done[["ticket_id", "agent_id", "_d"]].merge(roster, on="agent_id", how="inner")
    j = j[(j._d >= j.from_date) & (j._d <= j.to_date)]
    if j.ticket_id.duplicated().any():
        warn("some resolvers match more than one roster row on the resolution day; using the first")
        j = j.drop_duplicates("ticket_id")
    j = j.rename(columns={"name": "resolver_name", "agent_shift": "resolver_shift", "tier": "resolver_tier",
                          "team": "resolver_team", "site": "resolver_site"})
    keep = ["ticket_id", "resolver_name", "resolver_shift", "resolver_tier", "resolver_team", "resolver_site"]
    tk = tk.merge(j[keep], on="ticket_id", how="left")

    is_done = tk.status.isin(DONE)
    own = is_done & (tk.resolver_shift == tk.created_shift)
    reason = np.select(
        [tk.headcount == 0, own, ~is_done, tk.resolver_shift.isna(), tk.resolver_shift != tk.created_shift],
        ["no agent rostered on this shift", "resolved by an agent on the same shift",
         "not resolved yet - no resolver", "resolver not on the roster that day",
         "resolved by an agent on a different shift"], "")
    tk["reason"] = reason
    tk["attribution"] = np.where(tk.headcount == 0, UNSTAFFED, np.where(own, OWN, UNCLEAR))
    tk.loc[~tk.breach, ["attribution", "reason"]] = ""
    tk["own_shift"] = own & (tk.headcount > 0)
    return tk


# --------------------------------------------------------------------------- statistics (no scipy)
def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def binom_pmf(n: int, p: float) -> np.ndarray:
    pmf = np.zeros(n + 1)
    if p <= 0:
        pmf[0] = 1.0
    elif p >= 1:
        pmf[n] = 1.0
    else:
        lg = math.lgamma
        pmf = np.array([math.exp(lg(n + 1) - lg(k + 1) - lg(n - k + 1) + k * math.log(p) + (n - k) * math.log1p(-p))
                        for k in range(n + 1)])
    return pmf


def exact_two_sided_p(k: int, groups: list[tuple[int, float]]) -> float:
    """Exact two-sided p-value for k breaches when ticket groups have different breach probabilities.

    groups = [(n_tickets, p_expected), ...] (one per channel). The distribution of the total is the convolution
    of the binomials (Poisson-binomial); two-sided p = 2 * the smaller tail, capped at 1.
    """
    pmf = np.array([1.0])
    for n, p in groups:
        if n > 0:
            pmf = np.convolve(pmf, binom_pmf(n, p))
    hi, lo = pmf[k:].sum(), pmf[: k + 1].sum()
    return float(min(1.0, 2 * min(hi, lo)))


def adjust_p(p: pd.Series, method: str) -> pd.Series:
    """Multiple-testing correction: Holm (family-wise error) or Benjamini-Hochberg (false discovery rate)."""
    m = len(p)
    if m == 0:
        return p.copy()
    order = p.sort_values().index
    ps = p.loc[order].to_numpy()
    ranks = np.arange(1, m + 1)
    if method == "holm":
        adj = np.minimum(1.0, np.maximum.accumulate((m - ranks + 1) * ps))
    elif method == "bh":
        adj = np.minimum(1.0, np.minimum.accumulate((ps * m / ranks)[::-1])[::-1])
    else:
        raise ValueError(method)
    return pd.Series(adj, index=order).reindex(p.index)


# --------------------------------------------------------------------------- report pieces
def last_complete_week(asof: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    d = asof.normalize()
    week_end = d - pd.Timedelta(days=d.weekday() + 1)  # latest Sunday strictly before asof
    return week_end - pd.Timedelta(days=6), week_end


def attribution_counts(d: pd.DataFrame) -> dict:
    b = d[d.breach]
    return {UNSTAFFED: int((b.attribution == UNSTAFFED).sum()), OWN: int((b.attribution == OWN).sum()),
            UNCLEAR: int((b.attribution == UNCLEAR).sum())}


def by_creation_shift(d: pd.DataFrame, stf_row: pd.Series) -> pd.DataFrame:
    rows = []
    for s in SHIFTS:
        x = d[d.created_shift == s]
        c = attribution_counts(x)
        rows.append({"created_shift": s, "rostered_on_last_day": int(stf_row[s]), "tickets": len(x),
                     "breaches": int(x.breach.sum()), "breach_rate": x.breach.mean() if len(x) else np.nan,
                     "unstaffed_shift": c[UNSTAFFED], "agents_own_shift": c[OWN], "unclear": c[UNCLEAR]})
    x = d
    c = attribution_counts(x)
    rows.append({"created_shift": "All", "rostered_on_last_day": int(stf_row[SHIFTS].sum()), "tickets": len(x),
                 "breaches": int(x.breach.sum()), "breach_rate": x.breach.mean() if len(x) else np.nan,
                 "unstaffed_shift": c[UNSTAFFED], "agents_own_shift": c[OWN], "unclear": c[UNCLEAR]})
    return pd.DataFrame(rows)


def standard_view(d: pd.DataFrame) -> pd.DataFrame:
    """Breaches the way the helpdesk's standard report books them: against the resolving agent's shift."""
    b = d[d.breach]
    key = b.resolver_shift.fillna("not resolved yet")
    out = pd.DataFrame({"standard_report_shift": SHIFTS + ["not resolved yet"]})
    out["breaches_booked"] = out.standard_report_shift.map(key.value_counts()).fillna(0).astype(int)
    out["of_which_created_in_unstaffed_shift"] = out.standard_report_shift.map(
        b[b.attribution == UNSTAFFED].assign(k=key).groupby("k").size()).fillna(0).astype(int)
    return out


def weekly_trend(tk: pd.DataFrame, week_start: pd.Timestamp, n_weeks: int) -> pd.DataFrame:
    rows = []
    for i in range(n_weeks - 1, -1, -1):
        ws = week_start - pd.Timedelta(weeks=i)
        d = tk[(tk.created_date >= ws) & (tk.created_date <= ws + pd.Timedelta(days=6))]
        if d.empty:
            continue
        c = attribution_counts(d)
        rows.append({"week_start": ws.date().isoformat(), "tickets": len(d), "breaches": int(d.breach.sum()),
                     "breach_rate": d.breach.mean(), "unstaffed_shift": c[UNSTAFFED], "agents_own_shift": c[OWN],
                     "unclear": c[UNCLEAR]})
    return pd.DataFrame(rows)


def agent_table(tk: pd.DataFrame, min_tickets: int, correction: str, alpha: float) -> tuple[pd.DataFrame, dict]:
    done = tk[tk.status.isin(DONE) & tk.resolver_shift.notna()]
    n_tier2 = done[done.resolver_tier != 1].agent_id.nunique()
    t1 = done[done.resolver_tier == 1]  # Tier 2 is measured on resolution days, not volume metrics (policy section 6)

    pool = t1[t1.own_shift]  # peer pool: Tier-1 tickets created in the resolver's own (staffed) shift
    chan = pool.groupby("channel").breach.agg(B="sum", N="size")

    rows = []
    for aid, d in t1.groupby("agent_id"):
        own = d[d.own_shift]
        last = d.sort_values("resolved_at_ist").iloc[-1]
        k, n = int(own.breach.sum()), len(own)
        groups = []
        for c, oc in own.groupby("channel"):
            B, N = chan.loc[c, "B"] - oc.breach.sum(), chan.loc[c, "N"] - len(oc)  # leave this agent out of her/his peers
            groups.append((len(oc), float(B / N) if N >= min_tickets else float(chan.B.sum() / chan.N.sum())))
        exp = sum(g[0] * g[1] for g in groups)
        lo, hi = wilson(k, n)
        rated = n >= min_tickets
        rows.append({
            "agent_id": aid, "name": last.resolver_name, "team": last.resolver_team, "site": last.resolver_site,
            "shift": last.resolver_shift, "resolved": len(d), "std_breaches": int(d.breach.sum()),
            "std_rate": d.breach.mean() if len(d) >= min_tickets else np.nan,
            "std_breaches_from_unstaffed_shift": int((d.attribution == UNSTAFFED).sum()),
            "own_shift_tickets": n, "own_shift_breaches": k,
            "own_shift_rate": k / n if rated else np.nan,
            "own_ci_low": lo if rated else np.nan, "own_ci_high": hi if rated else np.nan,
            "peer_expected_rate": exp / n if rated else np.nan,
            "p_raw": exact_two_sided_p(k, groups) if rated else np.nan,
        })
    a = pd.DataFrame(rows).set_index("agent_id")
    tested = a.p_raw.notna()
    a["p_adj"] = np.nan
    a.loc[tested, "p_adj"] = adjust_p(a.loc[tested, "p_raw"], correction)
    a["result"] = np.where(~tested, f"not rated (<{min_tickets} own-shift tickets)", "in line with peers")
    sig = tested & (a.p_adj < alpha)
    a.loc[sig & (a.own_shift_rate > a.peer_expected_rate), "result"] = "ABOVE peers"
    a.loc[sig & (a.own_shift_rate < a.peer_expected_rate), "result"] = "below peers"
    info = {"agents": len(a), "rated": int(tested.sum()), "tier2_excluded": int(n_tier2),
            "uncorrected_flags": int((tested & (a.p_raw < alpha)).sum()), "corrected_flags": int(sig.sum()),
            "correction": correction, "alpha": alpha}
    rank = a.result.map({"ABOVE peers": 0}).fillna(1)  # flagged-above first, then everyone by standard rate
    a = a.assign(_rank=rank, _std=a.std_rate.fillna(-1)).sort_values(["_rank", "_std"], ascending=[True, False])
    return a.drop(columns=["_rank", "_std"]), info


# --------------------------------------------------------------------------- money
def simulate_savings(tk: pd.DataFrame, groups: dict[str, pd.Series], credit: int, sims: int,
                     seed: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """What Rs 350 credits would have been avoided had unstaffed shifts been staffed.

    Point estimate (hand-checkable): for each (shift, channel), tickets created while the shift was unstaffed x that
    shift's breach rate (breaches / tickets) from when it WAS staffed = expected breaches; saving = (actual - expected) x credit.
    The simulation only supplies the range: the staffed rate is drawn from a Beta posterior so small samples carry honest
    uncertainty, and breaches are redrawn as binomials. A cross-check uses the staffed-shift rate of the same channel and
    period instead. Returns (one row per period, one row per period x shift x channel = the audit trail).
    """
    rng = np.random.default_rng(seed)
    staffed = tk[tk.headcount > 0]
    base = staffed.groupby(["created_shift", "channel"]).breach.agg(k="sum", n="size")
    fall = staffed.groupby("channel").breach.agg(k="sum", n="size")
    unst = tk[(tk.headcount == 0) & tk.status.isin(DONE)]
    keys = sorted(set(zip(unst.created_shift, unst.channel)))
    draws, basis = {}, {}
    for s, c in keys:
        own_hist = (s, c) in base.index and base.loc[(s, c)].n >= 30
        k, n = (base.loc[(s, c)] if own_hist else fall.loc[c]).tolist()
        basis[(s, c)] = (int(k), int(n), f"{s} while staffed" if own_hist else "all staffed shifts, same channel")
        draws[(s, c)] = rng.beta(k + 1, n - k + 1, sims)
    rows, steps = [], []
    for label, mask in groups.items():
        g_all = tk[mask]
        g = unst[unst.ticket_id.isin(g_all.ticket_id)]
        if g.empty:
            rows.append({"period": label, "unstaffed_tickets": 0, "actual_breaches": 0, "tickets_created": len(g_all)})
            continue
        sim_b = np.zeros(sims)
        exp_b = exp_alt = 0.0
        for (s, c), x in g.groupby(["created_shift", "channel"]):
            sim_b += rng.binomial(len(x), draws[(s, c)])
            bk, bn, src = basis[(s, c)]
            exp_c = len(x) * bk / bn
            exp_b += exp_c
            steps.append({"period": label, "shift": s, "channel": c, "unstaffed_tickets": len(x),
                          "actual_breaches": int(x.breach.sum()), "baseline_breaches": bk, "baseline_tickets": bn,
                          "baseline_source": src, "baseline_rate": bk / bn, "expected_breaches_if_staffed": exp_c,
                          "avoidable_breaches": int(x.breach.sum()) - exp_c, "saving_inr": (int(x.breach.sum()) - exp_c) * credit})
            peers = g_all[(g_all.headcount > 0) & (g_all.channel == c)]
            exp_alt += len(x) * (peers.breach.mean() if len(peers) else np.nan)
        actual = int(g.breach.sum())
        sav = (actual - sim_b) * credit
        rows.append({"period": label, "tickets_created": len(g_all), "unstaffed_tickets": len(g), "actual_breaches": actual,
                     "expected_breaches_if_staffed": exp_b, "saving_inr": (actual - exp_b) * credit,
                     "saving_p5": np.percentile(sav, 5), "saving_p95": np.percentile(sav, 95),
                     "saving_crosscheck_inr": (actual - exp_alt) * credit})
    return pd.DataFrame(rows), pd.DataFrame(steps)


def money_tables(tk: pd.DataFrame, week_end: pd.Timestamp, window_start: pd.Timestamp, a) -> tuple[pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:
    credit, sims, seed, weeks_q, vol = a.credit, a.sims, a.seed, 13, a.weekly_volume
    q = tk.groupby("quarter").agg(first=("created_date", "min"), tickets=("ticket_id", "size"), breaches=("breach", "sum"))
    issued = tk[tk.breach & tk.status.isin(DONE)]
    pending = tk[tk.breach & ~tk.status.isin(DONE)]
    q["credits_issued_inr"] = issued.groupby("quarter").size().reindex(q.index).fillna(0) * credit
    q["credits_pending_inr"] = pending.groupby("quarter").size().reindex(q.index).fillna(0) * credit
    q["credits_from_unstaffed_inr"] = issued[issued.headcount == 0].groupby("quarter").size().reindex(q.index).fillna(0) * credit
    q["quarter_complete"] = [pd.Period(i, "Q").end_time.normalize() <= week_end for i in q.index]
    groups = {i: tk.quarter == i for i in q.index}
    win_label = f"last {a.window_weeks} weeks"
    groups[win_label] = (tk.created_date >= window_start) & (tk.created_date <= week_end)
    sim, steps = simulate_savings(tk, groups, credit, sims, seed)
    sim = sim.set_index("period")

    num = ["unstaffed_tickets", "actual_breaches", "expected_breaches_if_staffed", "saving_inr", "saving_p5", "saving_p95",
           "saving_crosscheck_inr"]
    sim = sim.reindex(columns=["tickets_created"] + num)
    sim[num] = sim[num].fillna(0.0)  # periods with no unstaffed shift: nothing to save
    money = q.join(sim.drop(columns=["tickets_created"]), how="left").reset_index().rename(columns={"index": "quarter"})
    win = sim.loc[win_label]
    w = tk[groups[win_label]]
    per_ticket = win["saving_inr"] / len(w) if len(w) else 0.0
    wk_actual = len(w) / a.window_weeks
    credits_per_ticket = (w[w.breach & w.status.isin(DONE)].shape[0] * credit) / len(w) if len(w) else 0.0
    scale = {
        "window_label": win_label, "window_tickets": len(w), "avg_weekly_tickets": wk_actual,
        "saving_window_inr": win["saving_inr"], "saving_window_p5": win["saving_p5"],
        "saving_window_p95": win["saving_p95"], "saving_per_ticket": per_ticket,
        "saving_per_ticket_p5": win["saving_p5"] / len(w) if len(w) else 0.0,
        "saving_per_ticket_p95": win["saving_p95"] / len(w) if len(w) else 0.0,
        "credits_per_ticket": credits_per_ticket, "weekly_volume": vol, "weeks_per_quarter": weeks_q,
        "agent_hour_cost": a.agent_hour_cost, "shift_hours": 8,
        "seat_cost_per_quarter": a.agent_hour_cost * 8 * 7 * weeks_q,
    }
    return money, sim, scale, steps


# --------------------------------------------------------------------------- markdown
def md_table(df: pd.DataFrame, fmt: dict | None = None) -> str:
    fmt = fmt or {}
    cols = list(df.columns)

    def cell(c, v):
        if c in fmt:
            return fmt[c](v)
        if isinstance(v, float):
            return "" if np.isnan(v) else f"{v:,.2f}"
        return "" if v is None else str(v).replace("|", "/")

    num = [pd.api.types.is_numeric_dtype(df[c]) for c in cols]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("--:" if n else ":--" for n in num) + "|"]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(cell(c, r[c]) for c in cols) + " |")
    return "\n".join(lines)


pct = lambda v: "" if pd.isna(v) else f"{v:.1%}"
inr = lambda v: "" if pd.isna(v) else f"Rs {v:,.0f}"
integ = lambda v: "" if pd.isna(v) else f"{int(round(v)):,}"
dec1 = lambda v: "" if pd.isna(v) else f"{v:,.1f}"


def render(ctx: dict) -> str:
    wk, week_start, week_end, args = ctx["week"], ctx["week_start"], ctx["week_end"], ctx["args"]
    c = attribution_counts(wk)
    nb = int(wk.breach.sum())
    share = lambda x: f"{x / nb:.0%}" if nb else "-"
    cut = ctx["by_shift_week"]
    L = []
    L.append(f"# Vireo Audio - weekly first-response SLA breach report")
    L.append(f"**Week:** Mon {week_start:%d %b} - Sun {week_end:%d %b %Y} (tickets created, IST) | "
             f"**Run as of:** {args.asof_used:%d %b %Y} | **Data:** {ctx['n_tickets']:,} tickets created up to "
             f"{week_end:%d %b %Y} ({ctx['n_dupes']:,} duplicate rows removed from the export)\n")

    L.append("## 1. This week")
    iss = wk[wk.breach & wk.status.isin(DONE)]
    pen = wk[wk.breach & ~wk.status.isin(DONE)]
    L.append(f"- **{len(wk):,} tickets, {nb:,} first-response breaches ({pct(nb / len(wk)) if len(wk) else '-'}).** "
             f"SLA credits at Rs {args.credit}: {inr(len(iss) * args.credit)} issued, {inr(len(pen) * args.credit)} still to come on open/pending tickets.")
    L.append(f"- Who the breaches belong to: **{UNSTAFFED} {c[UNSTAFFED]} ({share(c[UNSTAFFED])})**, "
             f"{OWN} {c[OWN]} ({share(c[OWN])}), {UNCLEAR} {c[UNCLEAR]} ({share(c[UNCLEAR])}).")
    un = wk[(wk.attribution == UNSTAFFED) & wk.resolver_shift.notna()]
    if len(un):
        by = un.resolver_shift.value_counts()
        L.append(f"- Of the {c[UNSTAFFED]} unstaffed-shift breaches, {len(un)} are already resolved and will be booked in the "
                 f"helpdesk's standard report against the resolving agent's shift: "
                 + ", ".join(f"{k} {v}" for k, v in by.items()) + ".")
    empty = [s for s in SHIFTS if int(ctx["stf_end"][s]) == 0]
    gap = " / ".join(ctx["gap_shifts"]) or "the empty shift"
    if empty:
        L.append(f"- **Roster gap:** nobody is rostered on {', '.join(empty)} at the end of this week.")
    L.append("")
    L.append("*Unstaffed shift* = ticket created in a shift with no agent on the roster (any team). *Agent's own shift* = created during the "
             "resolving agent's own shift, so plausibly theirs. *Unclear* = everything else: resolved by a different shift, "
             "not resolved yet, or the resolver is not on the roster. `agent_id` is the resolver, not necessarily the first responder.\n")

    L.append("### Last weeks")
    L.append(md_table(ctx["trend"], {"breach_rate": pct}) + "\n")

    L.append("## 2. By creation shift")
    L.append(f"This week (rostered_on_last_day = agents on the roster on {week_end:%d %b}):\n")
    L.append(md_table(cut, {"breach_rate": pct}) + "\n")
    L.append(f"Last {args.window_weeks} weeks:\n")
    L.append(md_table(ctx["by_shift_window"], {"breach_rate": pct}) + "\n")
    L.append("The same breaches as the helpdesk's standard report books them (by the resolving agent's shift), this week:\n")
    L.append(md_table(ctx["standard_week"]) + "\n")
    L.append(f"And over the last {args.window_weeks} weeks:\n")
    L.append(md_table(ctx["standard_window"]) + "\n")

    L.append("## 3. Agents (Tier 1)")
    ai = ctx["agent_info"]
    L.append(f"Window: last {args.window_weeks} weeks to {week_end:%d %b %Y}; resolved/closed tickets only. "
             f"The **own-shift rate** counts only tickets created during the agent's own shift; the **standard rate** is the "
             f"helpdesk's view (every ticket they resolved, whenever it was created). Agents need at least {args.min_tickets} "
             f"own-shift tickets to be rated. Tier 2 ({ai['tier2_excluded']} agents) is excluded per policy section 6.\n")
    L.append(f"**Many agents are tested at once, so some will look unusual by luck.** {ai['rated']} agents are rated. "
             f"Without correction {ai['uncorrected_flags']} would be flagged at the {ai['alpha']:.0%} level; after "
             f"{'Holm-Bonferroni' if ai['correction'] == 'holm' else 'Benjamini-Hochberg'} correction "
             f"{ai['corrected_flags']} are. Each agent is compared with Tier-1 peers' own-shift rate on the same channel mix "
             f"(excluding themselves); exact two-sided test. A flag is a reason to look at the tickets, not a verdict.\n")
    a = ctx["agents"].reset_index()
    show = pd.DataFrame({
        "Agent": a.agent_id + " " + a.name, "Team": a.team, "Shift": a["shift"], "Resolved": a.resolved,
        "Standard rate": a.std_rate, "Breaches from unstaffed shift": a.std_breaches_from_unstaffed_shift,
        "Own-shift tickets": a.own_shift_tickets, "Own-shift rate": a.own_shift_rate,
        "95% CI": [f"{lo:.1%}-{hi:.1%}" if pd.notna(lo) else "" for lo, hi in zip(a.own_ci_low, a.own_ci_high)],
        "Peers expect": a.peer_expected_rate, "Adj. p": a.p_adj, "Result": a.result})
    L.append(md_table(show, {"Standard rate": pct, "Own-shift rate": pct, "Peers expect": pct,
                             "Adj. p": lambda v: "" if pd.isna(v) else f"{v:.3f}"}) + "\n")

    L.append("## 4. Money")
    sc = ctx["scale"]
    L.append(f"Policy section 3: Rs {args.credit} store credit per breached ticket, issued on resolution (resolved and auto-closed "
             f"tickets count as issued; open/pending are shown as pending). Quarters are calendar quarters of ticket creation; "
             f"the saving is what staffing the empty shift again would have avoided, simulated {args.sims:,} times "
             f"(seed {args.seed}) using that shift's own breach rate by channel from when it was staffed; the range is the 5th-95th percentile.\n")
    m = ctx["money"].copy()
    m["quarter"] = m.quarter + np.where(m.quarter_complete, "", " (partial)")
    m["saving_range"] = [f"{inr(lo)} to {inr(hi)}" if pd.notna(lo) else "" for lo, hi in zip(m.saving_p5, m.saving_p95)]
    mm = m[["quarter", "tickets", "breaches", "credits_issued_inr", "credits_pending_inr", "credits_from_unstaffed_inr",
            "unstaffed_tickets", "actual_breaches", "expected_breaches_if_staffed", "saving_inr", "saving_range",
            "saving_crosscheck_inr"]].rename(columns={
        "credits_issued_inr": "credits issued", "credits_pending_inr": "credits pending",
        "credits_from_unstaffed_inr": "of which unstaffed shift", "unstaffed_tickets": "unstaffed tickets (done)",
        "actual_breaches": "their breaches", "expected_breaches_if_staffed": "expected if staffed",
        "saving_inr": "simulated saving", "saving_range": "saving 5-95%", "saving_crosscheck_inr": "cross-check saving"})
    L.append(md_table(mm, {"tickets": integ, "breaches": integ, "credits issued": inr, "credits pending": inr,
                           "of which unstaffed shift": inr, "unstaffed tickets (done)": integ, "their breaches": integ,
                           "expected if staffed": dec1, "simulated saving": inr, "cross-check saving": inr}) + "\n")
    if not ctx["gap_shifts"]:
        L.append(f"No shift was unstaffed in the last {args.window_weeks} weeks, so there is no saving to simulate for this window.\n")
    else:
        ws = ctx["steps"][ctx["steps"].period == sc["window_label"]]
        L.append(f"**How the simulated saving is built (last {args.window_weeks} weeks).** For each shift and channel: (1) count tickets created "
                 f"while the shift had nobody rostered and that are resolved/closed; (2) take that shift's breach rate from when it was staffed "
                 f"(breaches / tickets); (3) expected breaches = (1) x (2); (4) avoidable breaches = actual - expected; (5) saving = avoidable x Rs {args.credit}.\n")
        L.append(md_table(ws.drop(columns=["period"]).rename(columns={
            "unstaffed_tickets": "(1) unstaffed tickets", "actual_breaches": "actual breaches", "baseline_breaches": "staffed breaches",
            "baseline_tickets": "staffed tickets", "baseline_source": "baseline from", "baseline_rate": "(2) rate",
            "expected_breaches_if_staffed": "(3) expected", "avoidable_breaches": "(4) avoidable", "saving_inr": "(5) saving"}),
            {"(2) rate": pct, "(3) expected": dec1, "(4) avoidable": dec1, "(5) saving": inr}) + "\n")
        L.append(f"Total (5) = {inr(ws.saving_inr.sum())}; the 5-95% range comes from re-drawing the staffed rate and the breaches "
                 f"{args.sims:,} times. Full audit trail for every quarter: `saving_steps_*.csv`.\n")
        L.append("*Cross-check saving* assumes the empty shift would have performed like the staffed shifts did on the same channel in the same quarter.\n")
        L.append(f"### Scaled to {sc['weekly_volume']:,} tickets a week")
        L.append(f"In the last {args.window_weeks} weeks the desk created {sc['window_tickets']:,} tickets "
                 f"({sc['avg_weekly_tickets']:,.0f} a week). Simulated saving over that window: {inr(sc['saving_window_inr'])} "
                 f"(range {inr(sc['saving_window_p5'])} to {inr(sc['saving_window_p95'])}), i.e. Rs {sc['saving_per_ticket']:,.2f} per ticket created ({inr(sc['saving_window_inr'])} / {sc['window_tickets']:,} tickets).\n")
        q650 = sc["saving_per_ticket"] * sc["weekly_volume"] * sc["weeks_per_quarter"]
        lo650 = sc["saving_per_ticket_p5"] * sc["weekly_volume"] * sc["weeks_per_quarter"]
        hi650 = sc["saving_per_ticket_p95"] * sc["weekly_volume"] * sc["weeks_per_quarter"]
        cur = sc["saving_per_ticket"] * sc["avg_weekly_tickets"] * sc["weeks_per_quarter"]
        cr650 = sc["credits_per_ticket"] * sc["weekly_volume"] * sc["weeks_per_quarter"]
        L.append(md_table(pd.DataFrame([
            {"volume": f"current ({sc['avg_weekly_tickets']:,.0f}/week)", "credits at current service": inr(sc["credits_per_ticket"] * sc["avg_weekly_tickets"] * sc["weeks_per_quarter"]),
             f"saving per quarter if {gap} staffed": inr(cur)},
            {"volume": f"{sc['weekly_volume']:,}/week", "credits at current service": inr(cr650),
             f"saving per quarter if {gap} staffed": f"{inr(q650)} ({inr(lo650)} to {inr(hi650)})"},
        ])) + "\n")
        L.append(f"Scaling assumes the same mix of channels and shifts as the last {args.window_weeks} weeks (about "
                 f"{ctx['night_share']:.0%} of tickets arrive in an unstaffed shift) and the same breach rates when staffed.\n")
        L.append(f"Cost context (policy section 4): an agent-hour is Rs {sc['agent_hour_cost']:.0f}, a shift {sc['shift_hours']} hours, so one agent covering "
                 f"the empty shift every day of the week costs Rs {sc['seat_cost_per_quarter']:,.0f} a quarter if it were new headcount. "
                 f"Headcount is frozen, so the realistic route is re-rostering existing agents, which is cost-neutral on payroll "
                 f"but not proven neutral on the other shifts' breach rates.\n")

    L.append("## 5. Method and caveats")
    L.append("- Export is UTC, converted to IST (+05:30); the voice-callback window 08:00-22:00 IST is used as a self-check on every run.")
    L.append("- Duplicate ticket_ids (migration re-import) are dropped keeping the helpdesk copy; legacy CSAT 0 is treated as blank.")
    L.append("- Shifts: Morning 06-14, Day 14-22, Night 22-06 IST; a Night shift belongs to the day it starts on. Staffing comes from the "
             "roster row in force on that day (one row per assignment).")
    L.append("- Resolver = `agent_id` on resolved/closed tickets, matched to the roster row on the resolution day. The data does not say who sent the first reply.")
    L.append("- The saving is a model, not an observation: it assumes the staffed rate seen before the gap (when the Night queue was smaller) still holds. "
             "Money figures use the status in the export; reports re-run for an earlier `--asof` still see the final status of each ticket.")
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Weekly first-response SLA breach report (fair by shift).",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--asof", type=pd.Timestamp, default=None, help="run date YYYY-MM-DD; reports the last complete Mon-Sun week "
                    "before it (default: day after the last ticket in the export)")
    ap.add_argument("--data-dir", type=Path, default=HERE.parent / "data")
    ap.add_argument("--out-dir", type=Path, default=HERE / "outputs")
    ap.add_argument("--window-weeks", type=int, default=13, help="trailing window for the agent table and scaling")
    ap.add_argument("--min-tickets", type=int, default=20, help="minimum own-shift tickets before an agent is rated")
    ap.add_argument("--correction", choices=["holm", "bh"], default="holm", help="multiple-testing correction")
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--credit", type=int, default=350, help="Rs per breached ticket")
    ap.add_argument("--weekly-volume", type=int, default=650, help="tickets/week for the scaled money view")
    ap.add_argument("--agent-hour-cost", type=float, default=165.0)
    ap.add_argument("--sims", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args(argv)
    if a.window_weeks < 1 or a.min_tickets < 1 or a.sims < 100:
        ap.error("--window-weeks and --min-tickets must be >= 1, --sims >= 100")

    raw, roster = load(a.data_dir)
    tk = clean(raw)
    asof = (a.asof if a.asof is not None else tk.created_date.max() + pd.Timedelta(days=1)).normalize()
    a.asof_used = asof
    week_start, week_end = last_complete_week(asof)
    tk = tk[tk.created_date <= week_end]  # nothing after the reported week
    if tk.empty or not ((tk.created_date >= week_start) & (tk.created_date <= week_end)).any():
        print(f"error: no tickets created in the week {week_start:%d %b %Y} - {week_end:%d %b %Y} "
              f"(export starts {raw.created_at.min()[:10]}); choose a later --asof", file=sys.stderr)
        return 2

    tk = classify(tk, roster)
    window_start = week_end - pd.Timedelta(days=7 * a.window_weeks - 1)
    wk = tk[(tk.created_date >= week_start)]
    win = tk[(tk.created_date >= window_start)]
    stf = staffing_table(roster, week_end - pd.Timedelta(days=1), week_end)
    stf_end = stf.loc[week_end]

    agents, ainfo = agent_table(win, a.min_tickets, a.correction, a.alpha)
    money, sim, scale, steps = money_tables(tk, week_end, window_start, a)
    ctx = {
        "args": a, "week": wk, "week_start": week_start, "week_end": week_end, "stf_end": stf_end,
        "n_tickets": len(tk), "n_dupes": len(raw) - raw.ticket_id.nunique(), "last_ticket": tk.created_at_ist.max(),
        "trend": weekly_trend(tk, week_start, 8), "by_shift_week": by_creation_shift(wk, stf_end),
        "by_shift_window": by_creation_shift(win, stf_end), "standard_week": standard_view(wk),
        "standard_window": standard_view(win), "agents": agents, "agent_info": ainfo, "money": money, "scale": scale, "steps": steps,
        "night_share": float((win.headcount == 0).mean()) if len(win) else 0.0,
        "gap_shifts": [s for s in SHIFTS if ((win.created_shift == s) & (win.headcount == 0)).any()],
    }

    a.out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{week_start:%Y-%m-%d}"
    cols = ["ticket_id", "created_at_ist", "created_shift", "channel", "priority", "assigned_team", "resp_min", "target_min",
            "status", "attribution", "reason", "resolver_name", "resolver_shift", "resolver_tier"]
    br = wk[wk.breach].copy()
    br["minutes_over_target"] = br.resp_min - br.target_min
    br["credit_inr"] = np.where(br.status.isin(DONE), a.credit, 0)
    br["credit_pending_inr"] = np.where(br.status.isin(DONE), 0, a.credit)
    br[cols + ["minutes_over_target", "credit_inr", "credit_pending_inr"]].sort_values("created_at_ist").to_csv(
        a.out_dir / f"breaches_{tag}.csv", index=False)
    ctx["by_shift_week"].to_csv(a.out_dir / f"by_creation_shift_{tag}.csv", index=False)
    agents.reset_index().to_csv(a.out_dir / f"agents_{tag}.csv", index=False)
    money.to_csv(a.out_dir / f"credits_by_quarter_{tag}.csv", index=False)
    ctx["trend"].to_csv(a.out_dir / f"weekly_trend_{tag}.csv", index=False)
    steps.to_csv(a.out_dir / f"saving_steps_{tag}.csv", index=False)
    report = a.out_dir / f"weekly_report_{tag}.md"
    report.write_text(render(ctx), encoding="utf-8")

    c = attribution_counts(wk)
    print(f"Week {week_start:%d %b} - {week_end:%d %b %Y}: {len(wk):,} tickets, {int(wk.breach.sum())} breaches "
          f"({c[UNSTAFFED]} unstaffed shift, {c[OWN]} own shift, {c[UNCLEAR]} unclear)")
    print(f"Wrote {report}")
    print(f"      + 6 CSVs in {a.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
