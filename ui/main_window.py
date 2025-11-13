# Dice_Tool/ui/main_window.py
import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
from typing import List, Tuple
from statistics import mean, stdev, median
from simulation_core import SimParams, run_many_trials
from optimizer import OptParams, parse_range, optimize_parameters_manual
from .calc_tab import CalculatorTab
from .opt_tab import OptimizerTab
from .results_tab import ResultsTab
from .terms_tab import TermsTab

class AppController:
    """Controller for managing background tasks and logic."""

    def __init__(self, q: queue.Queue):
        self.queue = q

    def start_simulation(self, params: SimParams) -> Tuple[threading.Thread, threading.Event]:
        stop_event = threading.Event()
        def target():
            def progress_cb(done: int, total: int):
                self.queue.put(("sim_progress", done / total * 100))
            results = run_many_trials(params, stop_event, progress_cb)
            highest_balances = [r["highest_balance"] for r in results]
            cycles = [r["cycles"] for r in results]
            rounds = [r["rounds"] for r in results]
            total_successful_cycles = sum(cycles)
            total_attempted_cycles = total_successful_cycles + len(results)
            cycle_success_rate = (total_successful_cycles / total_attempted_cycles * 100) if total_attempted_cycles > 0 else 0.0
            bust_rate = (sum(1 for c in cycles if c == 0) / len(results) * 100) if len(results) > 0 else 0.0

            stats: List[Tuple[str, str]] = [
                ("Average highest balance", f"${median(highest_balances):.2f}" if highest_balances else "N/A"),
                ("Std dev (highest)", f"${stdev(highest_balances):.2f}" if len(highest_balances) > 1 else "N/A"),
                ("Max highest balance", f"${max(highest_balances):.2f}" if highest_balances else "N/A"),
                ("Average cycles", f"{mean(cycles):.2f}" if cycles else "N/A"),
                ("Average rounds", f"{mean(rounds):.2f}" if rounds else "N/A"),
                ("Cycle success rate", f"{cycle_success_rate:.2f}%"),
                ("Bust rate", f"{bust_rate:.2f}%"),
            ]
            self.queue.put(("sim_done", stats))
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread, stop_event

    def start_optimizer(self, opt_params: OptParams) -> Tuple[threading.Thread, threading.Event]:
        stop_event = threading.Event()
        thread = threading.Thread(target=optimize_parameters_manual, args=(opt_params, self.queue, stop_event), daemon=True)
        thread.start()
        return thread, stop_event

class MergedApp(tk.Tk):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.title("Dice Tools: Calculator/Simulator + Optimizer")
        self.geometry("1000x760")
        self.resizable(True, True)
        self.wm_minsize(800, 600)
        
        # MODIFIED FOR CRISP PAINTING: Disable auto-scaling for precise pixel control (adjust if DPI issues)
        self.tk.call("tk", "scaling", 1.0)
        
        self.queue = queue.Queue()
        self.controller = AppController(self.queue)
        
        self.sim_thread: threading.Thread = None
        self.sim_stop_event: threading.Event = None
        self.opt_thread: threading.Thread = None
        self.opt_stop_event: threading.Event = None
        
        self._build_ui()
        self.after(100, self.process_queue)

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=6)

        # --- Calculator / Simulator tab ---
        self.calc_tab = CalculatorTab(nb)
        nb.add(self.calc_tab, text="Calculator / Simulator")
        self.calc_tab.run_button.config(command=self.run_simulation)
        self.calc_tab.sim_stop_button.config(command=self.stop_simulation)

        # --- Results tab (needed before Optimizer) ---
        self.results_tab = ResultsTab(nb)

        # --- Optimizer tab ---
        self.opt_tab = OptimizerTab(nb)
        nb.add(self.opt_tab, text="Optimizer")
        self.opt_tab.opt_run_button.config(command=self.run_optimizer)
        self.opt_tab.opt_stop_button.config(command=self.stop_optimizer)
        self.opt_tab.clear_button.config(command=self.results_tab.clear_opt_results)

        # --- Optimizer Results tab ---
        nb.add(self.results_tab, text="Optimizer Results")
        self.results_tab.apply_button.config(
            command=lambda: self.results_tab.apply_selected_to_calculator(self.calc_tab)
        )

        # --- Terms & Definitions tab ---
        self.terms_tab = TermsTab(nb)
        nb.add(self.terms_tab, text="Terms")

        # Add colored headers for visual mapping
        for frame, color, title in [
            (self.calc_tab, "#add8e6", "Calculator / Simulator"),
            (self.opt_tab, "#90ee90", "Optimizer"),
            (self.results_tab, "#ffe0ea", "Optimizer Results"),
            (self.terms_tab, "#dcdcdc", "Terms & Definitions"),
        ]:
            header = tk.Label(frame, text=title, bg=color, font=("Segoe UI", 11, "bold"), anchor="center")
            header.grid(row=0, column=0, sticky="ew")  # Changed columnspan=99 to sticky="ew" (no need for large span)
            frame.rowconfigure(0, weight=0)
            
    def run_simulation(self):
        try:
            params = self.calc_tab.get_sim_params()
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter positive numeric values for all fields.")
            return
        self.calc_tab.sim_progress["value"] = 0
        self.sim_thread, self.sim_stop_event = self.controller.start_simulation(params)
        self.calc_tab.sim_stop_button.config(state="normal")

    def stop_simulation(self):
        if self.sim_stop_event:
            self.sim_stop_event.set()
        self.calc_tab.sim_stop_button.config(state="disabled")

    def run_optimizer(self):
        try:
            params = self.opt_tab.get_opt_params()
            total_combos = (
                len(params.bet_div_range) *
                len(params.profit_mult_range) *
                len(params.w_range) *
                len(params.l_range) *
                len(params.buffer_range)
            )
            if total_combos > 50000:
                proceed = messagebox.askyesno(
                    "Large Search Warning",
                    f"{total_combos} parameter combinations.\nThis may take a long time and use significant CPU resources.\nContinue?"
                )
                if not proceed:
                    return
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric ranges.")
            return
        self.opt_tab.opt_progress["value"] = 0
        self.opt_tab.opt_status_label.config(text=f"Running {total_combos} combos...")
        self.opt_tab.opt_run_button.config(state="disabled")
        self.opt_tab.opt_stop_button.config(state="normal")
        self.opt_thread, self.opt_stop_event = self.controller.start_optimizer(params)

    def stop_optimizer(self):
        if self.opt_stop_event:
            self.opt_stop_event.set()
        self.opt_tab.opt_stop_button.config(state="disabled")

    def process_queue(self):
        try:
            while True:
                msg, data = self.queue.get_nowait()
                if msg == "sim_progress":
                    self.calc_tab.sim_progress["value"] = data
                elif msg == "sim_done":
                    self.calc_tab.display_sim_results(data)
                    self.calc_tab.sim_stop_button.config(state="disabled")
                elif msg == "progress":
                    self.opt_tab.update_progress(data)
                elif msg == "done":
                    self.results_tab.display_opt_results(data)
                    self.opt_tab.job_finished()
        except queue.Empty:
            pass
        self.after(100, self.process_queue)