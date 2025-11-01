import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import secrets
import random
import struct
import queue
import pandas as pd
from statistics import mean, stdev

# GPU support REMOVED — using CPU only
import numpy as np

gpu_lock = threading.Lock()  # No longer used, but kept for structural consistency

# ---------- Utility: Tooltip ----------
class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        try:
            x, y, _, _ = self.widget.bbox("insert")
        except Exception:
            x, y = 0, 0
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background="#ffffe0",
                         relief='solid', borderwidth=1, wraplength=300, font=("Segoe UI", 9))
        label.pack(ipadx=1)
        self.tip_window = tw

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

# ---------- Core RNG (fast approximation of provably fair randomness) ----------
def fast_roll(rng):
    return rng.randint(0, 10000) / 10001.0

# ---------- Trial runner used by both tools (optimized loops, less overhead) ----------
def run_compounded_trial(starting_balance, bet_div, profit_mult, w, l, buffer):
    seed = int.from_bytes(secrets.token_bytes(8), "big")
    rng = random.Random(seed)

    balance = starting_balance
    peak = balance
    cycles = 0
    rounds = 0

    while balance > 0:
        bet = balance / bet_div
        profit_stop = bet * profit_mult
        target = balance + profit_stop

        m = ((1 + w) * l) * buffer
        if m == 0:
            win_chance = 0.0
        else:
            win_chance = max(0.0, min(1.0, (1 - 0.01) / m))

        current_bet = bet
        loss_streak = 0

        while balance > 0 and balance < target:
            roll = fast_roll(rng)
            rounds += 1
            if roll < win_chance:
                balance += current_bet * (m - 1)
                current_bet *= (1 + w)
                loss_streak = 0
            else:
                balance -= current_bet
                loss_streak += 1
                if loss_streak >= l:
                    current_bet = bet
                    loss_streak = 0
            if balance > peak:
                peak = balance

        if balance < target:
            break
        cycles += 1

    return {"highest_balance": peak, "cycles": cycles, "rounds": rounds}

# ---------- CPU batch runner (ONLY method now) ----------
def run_many_trials_cpu(n_trials, starting_balance, bet_div, profit_mult, w, l, buffer, stop_event=None, progress_callback=None):
    results = []
    for i in range(n_trials):
        if stop_event and stop_event.is_set():
            break
        r = run_compounded_trial(starting_balance, bet_div, profit_mult, w, l, buffer)
        results.append(r)
        if progress_callback:
            progress_callback(i + 1, n_trials)
    return results

# ---------- Wrapper: use CPU only ----------
def run_many_trials(n_trials, starting_balance, bet_div, profit_mult, w, l, buffer, stop_event=None, progress_callback=None):
    if stop_event and stop_event.is_set():
        return []
    return run_many_trials_cpu(n_trials, starting_balance, bet_div, profit_mult, w, l, buffer, stop_event=stop_event, progress_callback=progress_callback)

# ---------- Helpers for optimizer ranges (step-aware) ----------
def parse_range(text, integer=False):
    try:
        text = text.strip()
        if not text:
            return []
        # comma-separated explicit list
        if "," in text:
            parts = [p.strip() for p in text.split(",") if p.strip() != ""]
            if integer:
                return [int(float(p)) for p in parts]
            return [float(p) for p in parts]

        # optional step specification with semicolon: "start-end;step=0.5"
        step = None
        if ";" in text:
            left, right = text.split(";", 1)
            text = left.strip()
            if "=" in right:
                k, v = right.split("=", 1)
                if k.strip().lower() == "step":
                    step = float(v.strip()) if not integer else int(float(v.strip()))

        if "-" in text:
            start_s, end_s = text.split("-", 1)
            start = (int if integer else float)(start_s.strip())
            end = (int if integer else float)(end_s.strip())
            if step is not None:
                if step == 0:
                    return []
                # ensure proper direction
                if start <= end:
                    count = int(((end - start) / step) + 1)
                    return [(start + i * step) for i in range(count)]
                else:
                    count = int(((start - end) / step) + 1)
                    return [(start - i * step) for i in range(count)]
            if integer:
                return list(range(int(start), int(end) + 1)) if start <= end else list(range(int(start), int(end) - 1, -1))
            # default sampling: 10 samples across range
            if end == start:
                return [float(start)]
            return [start + i * (end - start) / 9 for i in range(10)]

        # single value
        return [(int(text) if integer else float(text))]
    except Exception:
        return []

# ---------- Optimizer's combo evaluator (aggregates fast trials) ----------
def run_trials_collect_stats(n_trials, starting_balance, bet_div, profit_mult, w, l, buffer, stop_event=None):
    highest_list = []
    cycles_list = []
    rounds_list = []
    successes = 0
    attempts = 0

    for i in range(n_trials):
        if stop_event and stop_event.is_set():
            break
        r = run_compounded_trial(starting_balance, bet_div, profit_mult, w, l, buffer)
        highest_list.append(r["highest_balance"])
        cycles_list.append(r["cycles"])
        rounds_list.append(r["rounds"])
        successes += r["cycles"]
        attempts += (r["cycles"] + 1)

    avg_high = mean(highest_list) if highest_list else 0.0
    std_high = stdev(highest_list) if len(highest_list) > 1 else 0.0
    max_high = max(highest_list) if highest_list else 0.0
    avg_cycles = mean(cycles_list) if cycles_list else 0.0
    avg_rounds = mean(rounds_list) if rounds_list else 0.0
    cycle_success_rate = (successes / attempts) * 100 if attempts > 0 else 0.0
    bust_rate = sum(1 for c in cycles_list if c == 0) / n_trials * 100 if n_trials > 0 else 0.0

    return avg_high, std_high, max_high, avg_cycles, avg_rounds, cycle_success_rate, bust_rate

def optimize_parameters_manual(starting_balance, n_trials,
                               bet_div_range, profit_mult_range,
                               w_range, l_range, buffer_range, q, stop_event):
    combos = list((bet_div, profit_mult, w, l, buffer)
                  for bet_div in bet_div_range
                  for profit_mult in profit_mult_range
                  for w in w_range
                  for l in l_range
                  for buffer in buffer_range)
    total = len(combos)
    results = []
    for i, (bet_div, profit_mult, w, l, buffer) in enumerate(combos, start=1):
        if stop_event.is_set():
            break
        avg_high, std_high, max_high, avg_cycles, avg_rounds, cycle_success_rate, bust_rate = run_trials_collect_stats(
            n_trials, starting_balance, bet_div, profit_mult, w, l, buffer, stop_event=stop_event
        )
        score = (avg_high - starting_balance) / std_high if std_high != 0 else 0.0

        results.append({
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
        })
        q.put(("progress", i / total))
    df = pd.DataFrame(results)
    if not df.empty:
        df = df.sort_values(by=["Score"], ascending=[False]).reset_index(drop=True)
    q.put(("done", df))

# ---------- Main Application ----------
class MergedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dice Tools: Calculator/Simulator + Optimizer")
        self.geometry("1000x760")
        self.resizable(False, False)
        self.queue = queue.Queue()
        self.optimize_thread = None
        self.sim_thread = None
        self.optimize_stop_event = threading.Event()
        self.sim_stop_event = threading.Event()
        self.build_ui()
        self.after(100, self.process_queue)

    def build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=6)

        tab_calc = ttk.Frame(nb)
        nb.add(tab_calc, text="Calculator / Simulator")
        self.build_calc_tab(tab_calc)

        tab_opt = ttk.Frame(nb)
        nb.add(tab_opt, text="Optimizer")
        self.build_opt_tab(tab_opt)

        tab_opt_res = ttk.Frame(nb)
        nb.add(tab_opt_res, text="Optimizer Results")
        self.build_opt_results_tab(tab_opt_res)

    # ---------------- Calculator Tab ----------------
    def build_calc_tab(self, parent):
        input_frame = ttk.LabelFrame(parent, text="Parameters")
        input_frame.place(x=10, y=10, width=960, height=120)

        ttk.Label(input_frame, text="Balance:").place(x=10, y=10)
        self.balance_var = tk.StringVar(value="20")
        balance_entry = ttk.Entry(input_frame, textvariable=self.balance_var, width=12)
        balance_entry.place(x=140, y=10)
        ToolTip(balance_entry, "Enter your current balance here.")
        self.add_help_icon(input_frame, 210, 10, "Enter your current balance here.")

        ttk.Label(input_frame, text="Win Increase %:").place(x=10, y=40)
        self.w_var = tk.StringVar(value="78")
        w_entry = ttk.Entry(input_frame, textvariable=self.w_var, width=12)
        w_entry.place(x=140, y=40)
        ToolTip(w_entry, "The percentage your bet increases after a win.")
        self.add_help_icon(input_frame, 210, 40, "The percentage your bet increases after a win.")

        ttk.Label(input_frame, text="Loss Reset (whole):").place(x=10, y=70)
        self.l_var = tk.StringVar(value="5")
        l_entry = ttk.Entry(input_frame, textvariable=self.l_var, width=12)
        l_entry.place(x=140, y=70)
        ToolTip(l_entry, "Number of consecutive losses before resetting the bet to base value.")
        self.add_help_icon(input_frame, 210, 70, "Number of consecutive losses before resetting the bet to base value. Use whole numbers only.")

        ttk.Label(input_frame, text="Balance Divisor:").place(x=300, y=10)
        self.bet_div_var = tk.StringVar(value="500")
        bet_div_entry = ttk.Entry(input_frame, textvariable=self.bet_div_var, width=12)
        bet_div_entry.place(x=420, y=10)
        ToolTip(bet_div_entry, "Your balance will be divided by this number to determine bet size.")
        self.add_help_icon(input_frame, 485, 10, "Your balance will be divided by this number to determine bet size.")

        ttk.Label(input_frame, text="Profit Multiplier:").place(x=300, y=40)
        self.profit_mult_var = tk.StringVar(value="100")
        profit_mult_entry = ttk.Entry(input_frame, textvariable=self.profit_mult_var, width=12)
        profit_mult_entry.place(x=420, y=40)
        ToolTip(profit_mult_entry, "Your bet size will be multiplied by this number to determine profit stop.")
        self.add_help_icon(input_frame, 485, 40, "Your bet size will be multiplied by this number to determine profit stop.")

        ttk.Label(input_frame, text="Buffer (%):").place(x=300, y=70)
        self.buffer_var = tk.StringVar(value="25")
        buffer_entry = ttk.Entry(input_frame, textvariable=self.buffer_var, width=12)
        buffer_entry.place(x=420, y=70)
        ToolTip(buffer_entry, "Boosts the calculated multiplier to help ensure the balance remains higher after cycles.")
        self.add_help_icon(input_frame, 485, 70, "Boosts the calculated multiplier. Setting 0 means breaking even.")

        click_me_button = ttk.Button(input_frame, text="Click Me To Get Started", command=self.show_getting_started_info)
        click_me_button.place(x=760, y=40, width=180, height=32)

        values_frame = ttk.LabelFrame(parent, text="Calculated Values")
        values_frame.place(x=10, y=140, width=960, height=90)

        self.multiplier_var = tk.StringVar()
        self.bet_size_var = tk.StringVar()
        self.profit_stop_var = tk.StringVar()
        self.balance_target_var = tk.StringVar()

        ttk.Label(values_frame, text="Multiplier:").place(x=10, y=10)
        ttk.Label(values_frame, textvariable=self.multiplier_var, font=('Arial', 10, 'bold')).place(x=140, y=10)

        ttk.Label(values_frame, text="Bet Size:").place(x=10, y=40)
        ttk.Label(values_frame, textvariable=self.bet_size_var, font=('Arial', 10, 'bold')).place(x=140, y=40)
        self.bet_copy_check = ttk.Label(values_frame, text="", foreground="green")
        ttk.Button(values_frame, text="Copy", width=6, command=lambda: self.copy_with_check(self.bet_size_var.get(), self.bet_copy_check)).place(x=220, y=37)
        self.bet_copy_check.place(x=275, y=40)

        ttk.Label(values_frame, text="Profit Stop:").place(x=320, y=10)
        ttk.Label(values_frame, textvariable=self.profit_stop_var, font=('Arial', 10, 'bold')).place(x=480, y=10)
        self.profit_copy_check = ttk.Label(values_frame, text="", foreground="green")
        ttk.Button(values_frame, text="Copy", width=6, command=lambda: self.copy_with_check(self.profit_stop_var.get(), self.profit_copy_check)).place(x=560, y=7)
        self.profit_copy_check.place(x=615, y=10)

        ttk.Label(values_frame, text="Balance Target:").place(x=320, y=40)
        ttk.Label(values_frame, textvariable=self.balance_target_var, font=('Arial', 10, 'bold')).place(x=480, y=40)
        self.target_copy_check = ttk.Label(values_frame, text="", foreground="green")
        ttk.Button(values_frame, text="Copy", width=6, command=lambda: self.copy_with_check(self.balance_target_var.get(), self.target_copy_check)).place(x=560, y=37)
        self.target_copy_check.place(x=615, y=40)

        for var in [self.balance_var, self.w_var, self.l_var, self.bet_div_var, self.profit_mult_var, self.buffer_var]:
            var.trace_add('write', lambda *args: self.calculate_values())
        self.calculate_values()

        sim_control_frame = ttk.LabelFrame(parent, text="Simulation Controls")
        sim_control_frame.place(x=10, y=240, width=960, height=80)

        how_it_works_button = ttk.Button(sim_control_frame, text="How Simulations Work", command=self.show_simulator_info)
        how_it_works_button.place(x=10, y=14, width=180, height=30)

        ttk.Label(sim_control_frame, text="Trials:").place(x=210, y=20)
        self.n_trials_var = tk.StringVar(value="100")
        n_trials_entry = ttk.Entry(sim_control_frame, textvariable=self.n_trials_var, width=10)
        n_trials_entry.place(x=260, y=20)

        self.sim_progress = ttk.Progressbar(sim_control_frame, orient="horizontal", length=340, mode="determinate")
        self.sim_progress.place(x=360, y=20, width=340, height=22)

        run_button = ttk.Button(sim_control_frame, text="Run Simulation", command=self.run_simulation)
        run_button.place(x=720, y=12, width=110, height=30)

        self.sim_stop_button = ttk.Button(sim_control_frame, text="Stop", state="disabled", command=self.request_sim_stop)
        self.sim_stop_button.place(x=840, y=12, width=60, height=30)

        output_frame = ttk.LabelFrame(parent, text="Simulation Results")
        output_frame.place(x=10, y=330, width=960, height=380)

        self.sim_tree = ttk.Treeview(output_frame, columns=("stat", "value"), show='headings', height=17)
        self.sim_tree.heading("stat", text="Statistic")
        self.sim_tree.heading("value", text="Value")
        self.sim_tree.column("stat", width=420)
        self.sim_tree.column("value", width=420)
        self.sim_tree.place(x=5, y=5)

        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.sim_tree.yview)
        scrollbar.place(x=915, y=5, height=325)
        self.sim_tree.configure(yscrollcommand=scrollbar.set)

        all_entries = [balance_entry, w_entry, l_entry, bet_div_entry, profit_mult_entry, buffer_entry, n_trials_entry]
        for entry in all_entries:
            entry.bind('<Control-v>', lambda event, e=entry: self.paste_to_entry(event, e))
            entry.bind('<Button-3>', lambda event, e=entry: self.right_click_menu(event, e))

    # ---------------- Optimizer Tab (controls only) ----------------
    def build_opt_tab(self, parent):
        frame = ttk.LabelFrame(parent, text="Parameter Ranges", padding=10)
        frame.place(x=10, y=10, width=960, height=300)

        self.opt_balance_var = tk.StringVar(value="20")
        self.opt_n_trials_var = tk.StringVar(value="10")
        self.opt_bet_div_var = tk.StringVar(value="256,500")
        self.opt_profit_mult_var = tk.StringVar(value="50,100")
        self.opt_w_var = tk.StringVar(value="50,100")
        self.opt_l_var = tk.StringVar(value="3-5")
        self.opt_buffer_var = tk.StringVar(value="25,30,40")

        labels = [
            ("Starting Balance", self.opt_balance_var, "Initial simulation balance"),
            ("Trials per Combo", self.opt_n_trials_var, "Number of runs per combo"),
            ("Bet Divisor Range", self.opt_bet_div_var, "e.g., 256-512;step=1 or 25,30,40"),
            ("Profit Multiplier Range", self.opt_profit_mult_var, "e.g., 25-150;step=5"),
            ("Win Increase % Range", self.opt_w_var, "e.g., 50-150;step=5"),
            ("Loss Reset (whole)", self.opt_l_var, "e.g., 3-8 (integers only)"),
            ("Buffer % Range", self.opt_buffer_var, "e.g., 20-40;step=2"),
        ]

        for i, (lbl, var, tip) in enumerate(labels):
            ttk.Label(frame, text=lbl, width=25, anchor="w").grid(row=i, column=0, padx=5, pady=4)
            e = ttk.Entry(frame, textvariable=var, width=40)
            e.grid(row=i, column=1, padx=5, pady=4)
            ToolTip(e, tip)

        self.opt_run_button = ttk.Button(frame, text="Run Optimizer", command=self.run_optimizer)
        self.opt_run_button.grid(row=len(labels), column=0, pady=10)
        ttk.Button(frame, text="Clear Results", command=self.clear_opt_results).grid(row=len(labels), column=1, pady=10)

        self.opt_progress = ttk.Progressbar(parent, orient="horizontal", length=920, mode="determinate")
        self.opt_progress.place(x=10, y=330, width=960, height=22)
        self.opt_status_label = ttk.Label(parent, text="Idle", anchor="center")
        self.opt_status_label.place(x=10, y=360, width=960, height=20)

        self.opt_stop_button = ttk.Button(parent, text="Stop", state="disabled", command=self.request_opt_stop)
        self.opt_stop_button.place(x=760, y=700, width=90, height=28)

    # ---------------- Optimizer Results Tab ----------------
    def build_opt_results_tab(self, parent):
        cols = ("BetDiv", "ProfitMult", "W%", "L", "Buffer%", "AvgHigh", "StdDev", "MaxHigh", "AvgCycles", "AvgRounds", "CycleSuccess%", "Bust%", "Score")
        self.res_tree = ttk.Treeview(parent, columns=cols, show="headings", height=20)
        for col in cols:
            self.res_tree.heading(col, text=col, command=lambda c=col: self.sort_res_column(c, False))
            self.res_tree.column(col, anchor="center", width=75)
        self.res_tree.place(x=10, y=10, width=960, height=640)

        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.res_tree.yview)
        scrollbar.place(x=965, y=10, height=640)
        self.res_tree.configure(yscrollcommand=scrollbar.set)

        ttk.Button(parent, text="Save to CSV", command=self.save_opt_csv).place(x=780, y=660, width=90, height=28)
        ttk.Button(parent, text="Apply Selected to Calculator", command=self.apply_selected_to_calculator).place(x=560, y=660, width=200, height=28)

    # ---------------- Generic helpers ----------------
    def add_help_icon(self, parent, x, y, text):
        label = tk.Label(parent, text="?", font=('Segoe UI', 8, 'bold'), fg="#777", cursor="question_arrow")
        label.place(x=x, y=y+2)
        ToolTip(label, text)

    def copy_with_check(self, value, check_label):
        if not value or value == "Invalid":
            return
        self.clipboard_clear()
        self.clipboard_append(value)
        check_label.config(text="Checkmark")
        check_label.after(1000, lambda: check_label.config(text=""))

    def paste_to_entry(self, event, entry):
        try:
            entry.insert(tk.INSERT, self.clipboard_get())
        except tk.TclError:
            pass
        return "break"

    def right_click_menu(self, event, entry):
        menu = tk.Menu(self, tearoff=0)
        try:
            menu.add_command(label="Paste", command=lambda e=entry: e.insert(tk.INSERT, self.clipboard_get()))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ---------------- Calculations ----------------
    def calculate_values(self):
        try:
            balance = float(self.balance_var.get())
            w = float(self.w_var.get()) / 100.0
            l = int(self.l_var.get())
            bet_div = float(self.bet_div_var.get())
            profit_mult = float(self.profit_mult_var.get())
            buffer = 1 + (float(self.buffer_var.get()) / 100.0)
            if balance <= 0 or l <= 0 or bet_div <= 0 or profit_mult <= 0 or buffer <= 0:
                raise ValueError
        except (ValueError, tk.TclError):
            self.multiplier_var.set("Invalid")
            self.bet_size_var.set("Invalid")
            self.profit_stop_var.set("Invalid")
            self.balance_target_var.set("Invalid")
            return

        m = ((1 + w) * l) * buffer
        bet_size = balance / bet_div
        profit_stop = bet_size * profit_mult
        balance_target = balance + profit_stop

        self.multiplier_var.set(f"{m:.2f}x")
        self.bet_size_var.set(f"{bet_size:.2f}")
        self.profit_stop_var.set(f"{profit_stop:.2f}")
        self.balance_target_var.set(f"{balance_target:.2f}")

    # ---------- Simulation flow ----------
    def run_simulation(self):
        try:
            starting_balance = float(self.balance_var.get())
            bet_div = float(self.bet_div_var.get())
            profit_mult = float(self.profit_mult_var.get())
            w = float(self.w_var.get()) / 100.0
            l = int(self.l_var.get())
            buffer = 1 + (float(self.buffer_var.get()) / 100.0)
            n_trials = int(self.n_trials_var.get())
            if starting_balance <= 0 or bet_div <= 0 or profit_mult <= 0 or l <= 0 or buffer <= 0 or n_trials <= 0:
                raise ValueError
        except (ValueError, tk.TclError):
            messagebox.showerror("Invalid Input", "Please enter positive numeric values for all fields.")
            return

        self.sim_progress["value"] = 0
        self.sim_stop_event.clear()
        self.sim_stop_button.config(state="normal")
        self.sim_thread = threading.Thread(
            target=self._sim_thread_fn,
            args=(n_trials, starting_balance, bet_div, profit_mult, w, l, buffer),
            daemon=True
        )
        self.sim_thread.start()

    def request_sim_stop(self):
        self.sim_stop_event.set()
        self.sim_stop_button.config(state="disabled")

    def _sim_thread_fn(self, n_trials, starting_balance, bet_div, profit_mult, w, l, buffer):
        def progress_cb(done, total):
            try:
                percent = done / total * 100
            except ZeroDivisionError:
                percent = 0
            self.sim_progress["value"] = percent
        results = run_many_trials(n_trials, starting_balance, bet_div, profit_mult, w, l, buffer,
                                  stop_event=self.sim_stop_event,
                                  progress_callback=progress_cb)
        df = pd.DataFrame(results) if results else pd.DataFrame(columns=["highest_balance", "cycles", "rounds"])
        highest_balances = df["highest_balance"] if "highest_balance" in df.columns else pd.Series(dtype=float)
        cycles = df["cycles"] if "cycles" in df.columns else pd.Series(dtype=float)
        rounds = df["rounds"] if "rounds" in df.columns else pd.Series(dtype=float)

        total_successful_cycles = cycles.sum()
        total_attempted_cycles = (cycles.sum() + len(df)) if len(df) > 0 else 0
        cycle_success_rate = (total_successful_cycles / total_attempted_cycles) * 100 if total_attempted_cycles > 0 else 0
        bust_rate = (len(df[df['cycles'] == 0]) / len(df) * 100) if len(df) > 0 else 0

        stats = [
            ("Average highest balance", f"${highest_balances.mean():.2f}" if not highest_balances.empty else "N/A"),
            ("Std dev (highest)", f"${highest_balances.std():.2f}" if not highest_balances.empty else "N/A"),
            ("Max highest balance", f"${highest_balances.max():.2f}" if not highest_balances.empty else "N/A"),
            ("Average cycles", f"{cycles.mean():.2f}" if not cycles.empty else "N/A"),
            ("Average rounds", f"{rounds.mean():.2f}" if not rounds.empty else "N/A"),
            ("Cycle success rate", f"{cycle_success_rate:.2f}%"),
            ("Bust rate", f"{bust_rate:.2f}%"),
        ]

        self.queue.put(("sim_done", stats))
        self.sim_stop_button.config(state="disabled")
        self.sim_progress["value"] = 100

    # ---------- Optimizer flow ----------
    def run_optimizer(self):
        try:
            starting_balance = float(self.opt_balance_var.get())
            n_trials = int(self.opt_n_trials_var.get())

            bet_div_range = parse_range(self.opt_bet_div_var.get())
            profit_mult_range = parse_range(self.opt_profit_mult_var.get())
            w_range = [x / 100 for x in parse_range(self.opt_w_var.get())]
            l_range = parse_range(self.opt_l_var.get(), integer=True)
            buffer_range = [1 + x / 100 for x in parse_range(self.opt_buffer_var.get())]

            if not bet_div_range or not profit_mult_range or not w_range or not l_range or not buffer_range:
                raise ValueError
        except:
            messagebox.showerror("Invalid Input", "Please enter valid numeric ranges.")
            return

        total_combos = (
            len(bet_div_range)
            * len(profit_mult_range)
            * len(w_range)
            * len(l_range)
            * len(buffer_range)
        )

        if total_combos > 50000:
            proceed = messagebox.askyesno(
                "Large Search Warning",
                f"{total_combos} parameter combinations.\nThis may take a long time and use significant CPU resources.\nContinue?"
            )
            if not proceed:
                return

        self.opt_progress["value"] = 0
        self.opt_status_label.config(text=f"Running {total_combos} combos...")
        self.opt_run_button.config(state="disabled")
        self.opt_stop_button.config(state="normal")
        self.optimize_stop_event.clear()

        t = threading.Thread(
            target=optimize_parameters_manual,
            args=(starting_balance, n_trials, bet_div_range, profit_mult_range,
                  w_range, l_range, buffer_range, self.queue, self.optimize_stop_event),
            daemon=True)
        t.start()
        self.optimize_thread = t

    def request_opt_stop(self):
        self.optimize_stop_event.set()
        self.opt_stop_button.config(state="disabled")

    def process_queue(self):
        try:
            while True:
                msg, data = self.queue.get_nowait()
                if msg == "progress":
                    self.opt_progress["value"] = data * 100
                    self.opt_status_label.config(text=f"Progress: {data*100:.1f}%")
                elif msg == "done":
                    self.display_opt_results(data)
                    self.opt_status_label.config(text="Done")
                    self.opt_run_button.config(state="normal")
                    self.opt_stop_button.config(state="disabled")
                elif msg == "sim_done":
                    self.display_sim_results(data)
        except queue.Empty:
            pass
        self.after(100, self.process_queue)

    def display_opt_results(self, df):
        for i in self.res_tree.get_children():
            self.res_tree.delete(i)
        if df is None or df.empty:
            messagebox.showinfo("No Results", "No results were produced (stopped or no combos).")
            return
        for _, row in df.iterrows():
            vals = (
                f"{row['BetDiv']:.2f}",
                f"{row['ProfitMult']:.2f}",
                f"{row['W%']:.2f}",
                f"{int(row['L'])}",
                f"{row['Buffer%']:.2f}",
                f"{row['AvgHigh']:.2f}",
                f"{row['StdDev']:.2f}",
                f"{row['MaxHigh']:.2f}",
                f"{row['AvgCycles']:.2f}",
                f"{row['AvgRounds']:.2f}",
                f"{row['CycleSuccess%']:.2f}",
                f"{row['Bust%']:.2f}",
                f"{row['Score']:.2f}",
            )
            self.res_tree.insert("", "end", values=vals)
        df.to_csv("optimization_results_manual.csv", index=False)
        self.opt_status_label.config(text=f"Done. Total combinations: {len(df)}. Saved to optimization_results_manual.csv")

    def clear_opt_results(self):
        for i in self.res_tree.get_children():
            self.res_tree.delete(i)
        self.opt_progress["value"] = 0
        self.opt_status_label.config(text="Cleared")
        self.opt_run_button.config(state="normal")
        self.opt_stop_button.config(state="disabled")

    def save_opt_csv(self):
        rows = [self.res_tree.item(i)["values"] for i in self.res_tree.get_children()]
        if not rows:
            messagebox.showinfo("No Data", "No results to save.")
            return
        columns = ["BetDiv", "ProfitMult", "W%", "L", "Buffer%", "AvgHigh", "StdDev", "MaxHigh", "AvgCycles", "AvgRounds", "CycleSuccess%", "Bust%", "Score"]
        file = filedialog.asksaveasfilename(defaultextension=".csv",
                                            filetypes=[("CSV Files", "*.csv")])
        if not file:
            return
        pd.DataFrame(rows, columns=columns).to_csv(file, index=False)
        messagebox.showinfo("Saved", f"Results saved to {file}")

    def sort_res_column(self, col, reverse):
        l = [(self.res_tree.set(k, col), k) for k in self.res_tree.get_children("")]
        try:
            l.sort(key=lambda t: float(t[0]), reverse=reverse)
        except ValueError:
            l.sort(reverse=reverse)
        for index, (val, k) in enumerate(l):
            self.res_tree.move(k, "", index)
        self.res_tree.heading(col, command=lambda: self.sort_res_column(col, not reverse))

    # ---------- Display helpers ----------
    def display_sim_results(self, stats):
        for i in self.sim_tree.get_children():
            self.sim_tree.delete(i)
        for stat, val in stats:
            self.sim_tree.insert("", "end", values=(stat, val))

    def show_simulator_info(self):
        info_text = (
            "1.) All values from the parameters and calculated sections are used in the simulation.\n\n"
            "2.) Each time the profit stop is met, the cycle ends and counts as a successful cycle.\n\n"
            "3.) Next cycle begins using the ending balance from previous cycle until bust.\n\n"
            "4.) Each trial ends when balance hits 0.\n\n"
            "5.) Successful cycles are the cycles that reached the profit stop."
        )
        messagebox.showinfo("How The Simulator Works", info_text)

    def show_getting_started_info(self):
        info_text = (
            "STEP 1:\n\n"
            "Set conditions:\n"
            "1) On win increase bet by 'Win Increase %'\n"
            "2) On loss streak of 'Loss Reset' reset bet to base\n"
            "3) Use 'Profit Stop' as net gain stop\n\n"
            "STEP 2:\n\n"
            "Enter starting balance and parameters. Use tooltips for guidance. Copy Bet Size and Profit Stop to your game.\n\n"
            "STEP 3:\n\n"
            "When Profit Stop met update Balance and repeat."
        )
        messagebox.showinfo("Click Me To Get Started", info_text)

    # ---------- New feature: apply selected optimizer result to calculator ----------
    def apply_selected_to_calculator(self):
        sel = self.res_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a row in Optimizer Results first.")
            return
        vals = self.res_tree.item(sel[0])["values"]
        try:
            bet_div = vals[0]
            profit_mult = vals[1]
            w_pct = vals[2]
            l = vals[3]
            buffer_pct = vals[4]

            self.bet_div_var.set(str(float(bet_div)))
            self.profit_mult_var.set(str(float(profit_mult)))
            self.w_var.set(str(float(w_pct)))
            self.l_var.set(str(int(float(l))))
            self.buffer_var.set(str(float(buffer_pct)))
            self.calculate_values()
            messagebox.showinfo("Applied", "Selected parameters applied to Calculator / Simulator tab.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not apply values: {e}")

if __name__ == "__main__":
    app = MergedApp()
    app.mainloop()
