# Dice_Tool/simulation_core.py
import os
import hmac
import secrets
from hashlib import sha256
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional, Tuple
import threading
from statistics import mean, stdev, median
from concurrent.futures import ProcessPoolExecutor, as_completed


try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:
    _HAS_NUMPY = False

@dataclass
class SimParams:
    """Parameters for a single simulation run."""
    starting_balance: float
    bet_div: float
    profit_mult: float
    w: float  
    l: int    
    buffer: float 
    n_trials: int = 1  

class StakeRNG:
    """
    Stake-style provably fair RNG implementation.
    Preserves exact HMAC-SHA256 based byte stream and the roll conversion:
        roll = f * 10001 / 100
    where f is constructed from consecutive bytes as in original algorithm.
    This class adds efficient batching while keeping byte order and nonce logic intact.
    """

    def __init__(self, server_seed: Optional[str] = None, client_seed: Optional[str] = None, nonce: int = 0):
        self.server_seed = server_seed or secrets.token_hex(32)
        self.client_seed = client_seed or secrets.token_hex(32)
        self.nonce = nonce
        self._byte_iter = self._byte_generator()
        self._cache: List[int] = []

    def _byte_generator(self):
        """Yield bytes deterministically from HMAC_SHA256(server_seed, f'{client_seed}:{nonce}:{round}')."""
        round_idx = 0
        while True:
            msg = f"{self.client_seed}:{self.nonce}:{round_idx}".encode()
            h = hmac.new(self.server_seed.encode(), msg, sha256)
            buffer = h.digest()
            for b in buffer:
                yield b
            round_idx += 1

    def _ensure_bytes(self, n: int):
        """Ensure there are at least n bytes in the cache."""
        while len(self._cache) < n:
            try:
                self._cache.append(next(self._byte_iter))
            except StopIteration:
                self._byte_iter = self._byte_generator()
                self._cache.append(next(self._byte_iter))

    def next_roll_batch(self, count: int) -> List[float]:
        """
        Generate `count` dice rolls in a single batched operation.
        Each roll consumes 4 bytes (same as original implementation).
        Nonce is advanced by count to reflect contiguous consumption.
        Returns list of floats in the [0.00,100.00+] scale used by the rest of the code.
        """
        if count <= 0:
            return []
        needed_bytes = count * 4
        self._ensure_bytes(needed_bytes)
        floats = []
        for i in range(count):
            chunk = self._cache[i*4:(i+1)*4]
            result = sum(value / (256 ** (j + 1)) for j, value in enumerate(chunk))
            roll = result * 10001 / 100
            floats.append(roll)
        del self._cache[:needed_bytes]
        self.nonce += count
        return floats

def run_compounded_trial(params: SimParams, batch_size: int = 1024) -> Dict[str, float]:
    """
    Runs a single compounded trial simulation preserving Stake logic.
    Uses StakeRNG.next_roll_batch to fetch rolls in batches for efficiency.
    Returns {"highest_balance": float, "cycles": int, "rounds": int}
    """
    rng = StakeRNG()  
    balance = params.starting_balance
    peak = balance
    cycles = 0
    rounds = 0

    while balance > 0:
        bet = balance / params.bet_div
        profit_stop = bet * params.profit_mult
        target = balance + profit_stop
        m = ((1 + params.w) * params.l) * params.buffer
        if m == 0:
            win_chance = 0.0
        else:
            win_chance = max(0.0, min(1.0, (1 - 0.01) / m))

        current_bet = bet
        loss_streak = 0
        batch: List[float] = []
        idx = 0
        while balance > 0 and balance < target:
            if idx >= len(batch):
                batch = rng.next_roll_batch(batch_size)
                idx = 0
                if not batch:
                    break
            roll = batch[idx]
            idx += 1

            rounds += 1
            if roll < win_chance * 100:
                balance += current_bet * (m - 1)
                current_bet *= (1 + params.w)
                loss_streak = 0
            else:
                balance -= current_bet
                loss_streak += 1
                if loss_streak >= params.l:
                    current_bet = bet
                    loss_streak = 0

            if balance > peak:
                peak = balance

        if balance < target:
            break
        cycles += 1

    return {"highest_balance": peak, "cycles": cycles, "rounds": rounds}

def run_many_trials(params: SimParams,
                    stop_event: Optional[threading.Event] = None,
                    progress_callback: Optional[Callable[[int, int], None]] = None,
                    parallel: bool = True) -> List[Dict[str, float]]:
    """
    Run multiple trials and return the list of results.
    - parallel: if True, uses ProcessPoolExecutor to parallelize independent trials.
      If False, runs sequentially in current process (used by optimizer workers to avoid oversubscription).
    - progress_callback(done, total) is called as trials complete.
    - stop_event if set will prevent further submissions. Already-started worker processes cannot be forcibly killed here.
    """
    results: List[Dict[str, float]] = []
    total = max(1, params.n_trials)

    if not parallel or params.n_trials <= 1:
        for i in range(params.n_trials):
            if stop_event and stop_event.is_set():
                break
            r = run_compounded_trial(params)
            results.append(r)
            if progress_callback:
                progress_callback(i + 1, params.n_trials)
        return results

    cpu_count = os.cpu_count() or 1
    max_workers = min(cpu_count, params.n_trials,  max(1, cpu_count))
    futures = []
    with ProcessPoolExecutor(max_workers=max_workers) as exe:
        submitted = 0
        for _ in range(params.n_trials):
            if stop_event and stop_event.is_set():
                break
            futures.append(exe.submit(run_compounded_trial, params))
            submitted += 1
        done_count = 0
        for fut in as_completed(futures):
            try:
                res = fut.result()
            except Exception:
                res = {"highest_balance": 0.0, "cycles": 0, "rounds": 0}
            results.append(res)
            done_count += 1
            if progress_callback:
                progress_callback(done_count, submitted)
            if stop_event and stop_event.is_set():
                break
    return results

def run_trials_collect_stats(params: SimParams,
                             stop_event: Optional[threading.Event] = None,
                             parallel: bool = True) -> Tuple[float, float, float, float, float, float, float]:
    """
    Runs multiple trials (possibly parallel) and computes aggregated statistics.
    Returns tuple:
      (avg_high, std_high, max_high, avg_cycles, avg_rounds, cycle_success_rate, bust_rate)
    parallel: forwarded to run_many_trials to control internal parallelism (optimizer uses parallel=False).
    """
    results = run_many_trials(params, stop_event=stop_event, progress_callback=None, parallel=parallel)

    highest_list = [r["highest_balance"] for r in results]
    cycles_list = [r["cycles"] for r in results]
    rounds_list = [r["rounds"] for r in results]
    successes = sum(cycles_list)
    attempts = len(results) + successes

    if _HAS_NUMPY and highest_list:
        arr = np.array(highest_list, dtype=np.float64)
        avg_high = float(np.median(arr))
        std_high = float(arr.std(ddof=1)) if arr.size > 1 else 0.0
        max_high = float(arr.max())
    else:
        avg_high = mean(highest_list) if highest_list else 0.0
        std_high = stdev(highest_list) if len(highest_list) > 1 else 0.0
        max_high = max(highest_list) if highest_list else 0.0

    avg_cycles = mean(cycles_list) if cycles_list else 0.0
    avg_rounds = mean(rounds_list) if rounds_list else 0.0
    cycle_success_rate = (successes / attempts * 100) if attempts > 0 else 0.0
    bust_rate = (sum(1 for c in cycles_list if c == 0) / params.n_trials * 100) if params.n_trials > 0 else 0.0

    return avg_high, std_high, max_high, avg_cycles, avg_rounds, cycle_success_rate, bust_rate
