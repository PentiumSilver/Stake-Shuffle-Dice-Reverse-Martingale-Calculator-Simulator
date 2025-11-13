# Dice_Tool/ui/opt_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List
from optimizer import OptParams, parse_range
from .widgets import ToolTip

class OptimizerTab(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        style = ttk.Style()
        style.configure("Optimizer.TFrame", background="#90ee90")  # Light green - Matches Optimizer in TermsTab

        self.configure(style="Optimizer.TFrame")
        
        # MODIFIED FOR RESIZE: Allow full expansion
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=0)  # Params frame fixed
        self.rowconfigure(2, weight=0)  # Progress fixed
        self.rowconfigure(3, weight=0)  # Status fixed
        self.rowconfigure(4, weight=1)  # Buttons expand vertically if needed

        # State variables (unchanged)
        self.opt_balance_var = tk.StringVar(value="20")
        self.opt_n_trials_var = tk.StringVar(value="10")
        self.opt_bet_div_var = tk.StringVar(value="256,500")
        self.opt_profit_mult_var = tk.StringVar(value="50,100")
        self.opt_w_var = tk.StringVar(value="50,100")
        self.opt_l_var = tk.StringVar(value="3-5")
        self.opt_buffer_var = tk.StringVar(value="25,30,40")
        
        self._build_param_frame()
        
        self.opt_progress = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.opt_progress.grid(row=2, column=0, padx=10, pady=5, sticky="ew")  # MODIFIED: sticky for full width

        self.opt_status_label = ttk.Label(self, text="Idle", anchor="center")
        self.opt_status_label.grid(row=3, column=0, padx=10, pady=5, sticky="ew")  # MODIFIED: sticky

        self.opt_stop_button = ttk.Button(self, text="Stop", state="disabled")
        self.opt_stop_button.grid(row=4, column=0, pady=10, sticky="e", padx=10)

        self.clear_button = ttk.Button(self, text="Clear Results")
        self.clear_button.grid(row=4, column=0, pady=10, sticky="w", padx=10)

    def _build_param_frame(self):
        frame = ttk.LabelFrame(self, text="Parameter Ranges", padding=10)
        frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")  # MODIFIED: sticky="ew"
        frame.columnconfigure(1, weight=1)
        
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
            ttk.Label(frame, text=lbl, anchor="w").grid(row=i, column=0, padx=5, pady=4, sticky="w")
            e = ttk.Entry(frame, textvariable=var)
            e.grid(row=i, column=1, padx=5, pady=4, sticky="ew")
            ToolTip(e, tip)

        self.opt_run_button = ttk.Button(frame, text="Run Optimizer")
        self.opt_run_button.grid(row=len(labels), column=0, pady=10, sticky="w")

    def get_opt_params(self) -> OptParams:
        """Extracts optimization parameters from UI variables."""
        try:
            starting_balance = float(self.opt_balance_var.get())
            n_trials = int(self.opt_n_trials_var.get())
            bet_div_range = parse_range(self.opt_bet_div_var.get())
            profit_mult_range = parse_range(self.opt_profit_mult_var.get())
            w_range = parse_range(self.opt_w_var.get())
            l_range = parse_range(self.opt_l_var.get(), integer=True)
            buffer_range = parse_range(self.opt_buffer_var.get())
            if not all([bet_div_range, profit_mult_range, w_range, l_range, buffer_range]):
                raise ValueError
        except (ValueError, tk.TclError):
            raise ValueError("Invalid input values")
        return OptParams(starting_balance, bet_div_range, profit_mult_range, w_range, l_range, buffer_range, n_trials)

    def update_progress(self, value: float):
        self.opt_progress["value"] = value * 100
        self.opt_status_label.config(text=f"Progress: {value*100:.1f}%")

    def job_finished(self):
        self.opt_status_label.config(text="Done")
        self.opt_run_button.config(state="normal")
        self.opt_stop_button.config(state="disabled")