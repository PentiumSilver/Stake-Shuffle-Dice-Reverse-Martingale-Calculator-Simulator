# Dice_Tool/optimizer.py
import os
from typing import List, Tuple, Dict
import pandas as pd
from dataclasses import dataclass
import queue
from simulation_core import SimParams, run_trials_collect_stats
from concurrent.futures import ProcessPoolExecutor, as_completed
import threading

@dataclass
class OptParams:
    """Parameters for optimization runs."""
    starting_balance: float
    bet_div_range: List[float]
    profit_mult_range: List[float]
    w_range: List[float]  # In percentage (raw numbers, will be divided by 100)
    l_range: List[int]
    buffer_range: List[float]  # In percentage (raw numbers, e.g. 25 -> 25)
    n_trials: int

def parse_range(text: str, integer: bool = False) -> List:
    """
    Parses a range string into a list of values.
    Supports comma-separated lists, ranges like 'start-end', and optional step with ';step=val'.
    """
    try:
        text = text.strip()
        if not text:
            return []
        if "," in text:
            parts = [p.strip() for p in text.split(",") if p.strip()]
            return [int(float(p)) if integer else float(p) for p in parts]

        step = None
        if ";" in text:
            left, right = text.split(";", 1)
            text = left.strip()
            if "=" in right:
                k, v = [s.strip() for s in right.split("=", 1)]
                if k.lower() == "step":
                    step = int(float(v)) if integer else float(v)

        if "-" in text:
            start_s, end_s = text.split("-", 1)
            start = int(start_s.strip()) if integer else float(start_s.strip())
            end = int(end_s.strip()) if integer else float(end_s.strip())
            if step is not None:
                if step == 0:
                    return []
                if start <= end:
                    count = int((end - start) / step) + 1
                    return [start + i * step for i in range(count)]
                else:
                    count = int((start - end) / step) + 1
                    return [start - i * step for i in range(count)]
            if integer:
                step_dir = 1 if start <= end else -1
                return list(range(int(start), int(end) + step_dir, step_dir))
            if start == end:
                return [float(start)]
            # default to 10 evenly spaced values when step unspecified
            return [start + i * (end - start) / 9 for i in range(10)]

        return [int(text) if integer else float(text)]
    except Exception:
        return []

def _run_one_combo(args):
    """
    Worker function run inside a process pool.
    Runs trials sequentially (parallel=False passed to avoid nested process pools).
    Returns the result dict for this combo.
    """
    (bet_div, profit_mult, w, l, buffer, starting_balance, n_trials) = args
    params = SimParams(starting_balance, bet_div, profit_mult, w, l, buffer, n_trials)
    # run_trials_collect_stats called with parallel=False to avoid nested process pools
    avg_high, std_high, max_high, avg_cycles, avg_rounds, cycle_success_rate, bust_rate = run_trials_collect_stats(params, stop_event=None, parallel=False)
    score = (avg_high - starting_balance) / std_high if std_high != 0 else 0.0
    return {
        "BetDiv": round(float(bet_div), 2),
        "ProfitMult": round(float(profit_mult), 2),
        "W%": round((w * 100), 2),
        "L": int(l),
        "Buffer%": round((buffer - 1) * 100, 2),
        "AvgHigh": round(avg_high, 2),
        "StdDev": round(std_high, 2),
        "MaxHigh": round(max_high, 2),
        "AvgCycles": round(avg_cycles, 2),
        "AvgRounds": round(avg_rounds, 2),
        "CycleSuccess%": round(cycle_success_rate, 2),
        "Bust%": round(bust_rate, 2),
        "Score": round(score, 2)
    }

def optimize_parameters_manual(opt_params: OptParams,
                               q: queue.Queue,
                               stop_event: threading.Event) -> None:
    """
    Runs optimization over parameter combinations and reports results via queue.
    Uses ProcessPoolExecutor to parallelize combos. Each worker runs per-combo trials sequentially.
    stop_event is checked between combo submissions and while collecting results to allow early termination.
    """
    combos: List[Tuple[float, float, float, int, float, float, int]] = [
        (bet_div, profit_mult, w / 100.0, l, 1 + buffer / 100.0, opt_params.starting_balance, opt_params.n_trials)
        for bet_div in opt_params.bet_div_range
        for profit_mult in opt_params.profit_mult_range
        for w in opt_params.w_range
        for l in opt_params.l_range
        for buffer in opt_params.buffer_range
    ]
    total = len(combos)
    results = []

    if total == 0:
        q.put(("done", pd.DataFrame()))
        return

    # limit workers to a reasonable number to avoid oversubscription
    cpu_count = min(32, (os.cpu_count() or 1))
    max_workers = min(cpu_count, total)

    with ProcessPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_run_one_combo, combo): combo for combo in combos}

        done = 0
        for fut in as_completed(futures):
            if stop_event.is_set():
                # cannot forcefully kill running worker processes here. We stop collecting more results.
                break
            try:
                res = fut.result()
            except Exception:
                # On failure produce a safe dummy row
                res = {
                    "BetDiv": 0.0, "ProfitMult": 0.0, "W%": 0.0, "L": 0, "Buffer%": 0.0,
                    "AvgHigh": 0.0, "StdDev": 0.0, "MaxHigh": 0.0, "AvgCycles": 0.0, "AvgRounds": 0.0,
                    "CycleSuccess%": 0.0, "Bust%": 100.0, "Score": 0.0
                }
            results.append(res)
            done += 1
            q.put(("progress", done / total))

    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by=["Score"], ascending=[False]).reset_index(drop=True)
    q.put(("done", df))
