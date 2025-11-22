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

# Dice_Tool/ui/main_window.py
# (Only the apply_global_theme function needs to be updated/replaced)

def apply_global_theme(root: tk.Tk):
    style = ttk.Style(root)
    style.theme_use('clam')  # 'clam' gives us full control over colors

    # Main color scheme (consistent with your new sunken frames)
    bg              = "#3f3f3f"   # Frame background
    fg              = "#17c7b8"   # Main text / accent
    label_fg        = "#249f87"   # LabelFrame title color
    field_bg        = "#2d2d2d"   # Entry / Treeview background
    select_bg       = "#17c7b8"   # Selected row/item
    select_fg       = "#000000"
    button_bg       = "#333333"
    button_active   = "#555555"
    heading_bg      = "#333333"
    trough          = "#555555"

    # Global widget defaults
    style.configure('.', background=bg, foreground=fg, font=('Segoe UI', 9))
    style.configure('TFrame', background=bg)
    style.configure('TLabel', background=bg, foreground=fg)

    # LabelFrames (your new style)
    style.configure('TLabelFrame', background=bg, foreground=label_fg,
                    font=('Times New Roman', 9, 'bold', 'italic', 'underline'),
                    relief='sunken', borderwidth=2, highlightbackground="#249f87",
                    highlightcolor="#a9ebde", highlightthickness=1)
    style.configure('TLabelFrame.Label', foreground=label_fg, background=bg)

    # Buttons
    style.configure('TButton', font=('Segoe UI', 8), padding=4)
    style.map('TButton',
              background=[('active', button_active), ('disabled', button_bg)],
              foreground=[('disabled', '#888888')])

    # Entries
    style.configure('TEntry', fieldbackground=field_bg, foreground=fg,
                    insertcolor=fg, font=('Segoe UI', 9))

    # Treeview - compact and matching your new look
    style.configure('Treeview',
                    background=field_bg,
                    foreground=fg,
                    fieldbackground=field_bg,
                    rowheight=18,                    # Much more compact
                    font=('Segoe UI', 9))
    style.configure('Treeview.Heading',
                    background=heading_bg,
                    foreground=fg,
                    font=('Segoe UI', 9, 'bold'),
                    relief='flat')
    style.map('Treeview',
              background=[('selected', select_bg)],
              foreground=[('selected', select_fg)])

    # Progressbar
    style.configure('Horizontal.TProgressbar',
                    troughcolor=trough,
                    background='#00ff80',
                    thickness=14)

    # Notebook & Tabs
    style.configure('TNotebook', background=bg, borderwidth=0)
    style.configure('TNotebook.Tab',
                    padding=[10, 4],
                    font=('Segoe UI', 9))
    style.map('TNotebook.Tab',
              background=[('selected', bg), ('active', '#444444')],
              foreground=[('selected', fg), ('active', fg)])
    
class AppController:
    def __init__(self, q: queue.Queue):
        self.queue = q

    def start_simulation(self, params: SimParams):
        stop_event = threading.Event()
        def target():
            def progress_cb(done: int, total: int):
                self.queue.put(("sim_progress", done / total * 100))
            results = run_many_trials(params, stop_event, progress_cb, parallel=True)
            highest_balances = [r["highest_balance"] for r in results]
            cycles = [r["cycles"] for r in results]
            rounds = [r["rounds"] for r in results]
            total_successful = sum(cycles)
            total_cycles = len(results) + total_successful
            cycle_success = (total_successful / total_cycles * 100) if total_cycles else 0
            bust_rate = sum(1 for c in cycles if c == 0) / len(results) * 100 if results else 0

            stats = [
                ("Average highest balance", f"${median(highest_balances):.2f}" if highest_balances else "N/A"),
                ("Std dev (highest)", f"${stdev(highest_balances):.2f}" if len(highest_balances) > 1 else "N/A"),
                ("Max highest balance", f"${max(highest_balances):.2f}" if highest_balances else "N/A"),
                ("Average cycles", f"{mean(cycles):.2f}" if cycles else "N/A"),
                ("Average rounds", f"{mean(rounds):.2f}" if rounds else "N/A"),
                ("Cycle success rate", f"{cycle_success:.2f}%"),
                ("Bust rate", f"{bust_rate:.2f}%"),
            ]
            self.queue.put(("sim_done", stats))
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        return thread, stop_event

    def start_optimizer(self, opt_params: OptParams):
        stop_event = threading.Event()
        thread = threading.Thread(target=optimize_parameters_manual,
                                 args=(opt_params, self.queue, stop_event), daemon=True)
        thread.start()
        return thread, stop_event


class MergedApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dice Tools: Calculator/Simulator + Optimizer")
        self.geometry("1100x780")
        self.minsize(900, 650)
        self.configure(bg="#17c7b8")

        self.queue = queue.Queue()
        self.controller = AppController(self.queue)

        self.sim_thread = None
        self.sim_stop_event = None
        self.opt_thread = None
        self.opt_stop_event = None

        self._build_ui()
        self.after(100, self.process_queue)

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=2, pady=2)

        self.calc_tab = CalculatorTab(nb)
        nb.add(self.calc_tab, text="Calculator / Simulator")

        self.opt_tab = OptimizerTab(nb)
        nb.add(self.opt_tab, text="Optimizer")

        self.results_tab = ResultsTab(nb)
        nb.add(self.results_tab, text="Optimizer Results")

        self.terms_tab = TermsTab(nb)
        nb.add(self.terms_tab, text="Terms")

        # Connect buttons
        self.calc_tab.run_button.config(command=self.run_simulation)
        self.calc_tab.sim_stop_button.config(command=self.stop_simulation)
        self.opt_tab.opt_run_button.config(command=self.run_optimizer)
        self.opt_tab.opt_stop_button.config(command=self.stop_optimizer)
        self.opt_tab.clear_button.config(command=self.results_tab.clear_opt_results)
        self.results_tab.apply_button.config(command=lambda: self.results_tab.apply_selected_to_calculator(self.calc_tab))

    def run_simulation(self):
        try:
            params = self.calc_tab.get_sim_params()
            self.calc_tab.sim_progress["value"] = 0
            self.sim_thread, self.sim_stop_event = self.controller.start_simulation(params)
            self.calc_tab.sim_stop_button.config(state="normal")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid positive numbers.")

    def stop_simulation(self):
        if self.sim_stop_event:
            self.sim_stop_event.set()
        self.calc_tab.sim_stop_button.config(state="disabled")

    def run_optimizer(self):
        try:
            params = self.opt_tab.get_opt_params()
            combos = (len(params.bet_div_range) * len(params.profit_mult_range) *
                     len(params.w_range) * len(params.l_range) * len(params.buffer_range))
            if combos > 50000:
                if not messagebox.askyesno("Large Search", f"{combos} combinations may take a long time. Continue?"):
                    return
            self.opt_tab.opt_progress["value"] = 0
            self.opt_tab.opt_status_label.config(text="Running...")
            self.opt_tab.opt_run_button.config(state="disabled")
            self.opt_tab.opt_stop_button.config(state="normal")
            self.opt_thread, self.opt_stop_event = self.controller.start_optimizer(params)
        except ValueError:
            messagebox.showerror("Invalid Range", "Check your range syntax (e.g., 100-500 or 20,30,40)")

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
