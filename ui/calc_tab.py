# Dice_Tool/ui/calc_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Tuple
from simulation_core import SimParams
from .widgets import ToolTip

class CalculatorTab(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.columnconfigure(0, weight=1)
        # MODIFIED FOR RESIZE: Ensure rows expand properly
        self.rowconfigure(1, weight=0)  # Input frame
        self.rowconfigure(2, weight=0)  # Values frame
        self.rowconfigure(3, weight=0)  # Sim control
        self.rowconfigure(4, weight=1)  # Output expands vertically

        # State variables
        self.balance_var = tk.StringVar(value="20")
        self.w_var = tk.StringVar(value="78")
        self.l_var = tk.StringVar(value="5")
        self.bet_div_var = tk.StringVar(value="500")
        self.profit_mult_var = tk.StringVar(value="100")
        self.buffer_var = tk.StringVar(value="25")
        self.n_trials_var = tk.StringVar(value="100")
        
        self.multiplier_var = tk.StringVar()
        self.bet_size_var = tk.StringVar()
        self.profit_stop_var = tk.StringVar()
        self.balance_target_var = tk.StringVar()
        
        # Collect all entries for bindings
        self.all_entries = []  # Moved here
        
        # Build UI sections
        self._build_input_frame()
        self._build_values_frame()
        self._build_sim_control_frame()
        self._build_output_frame()  

        # Traces for auto-calculation
        for var in [self.balance_var, self.w_var, self.l_var, self.bet_div_var, self.profit_mult_var, self.buffer_var]:
            var.trace_add('write', self.calculate_values)
        self.calculate_values()
        
        # Bindings for paste
        for entry in self.all_entries:
            entry.bind('<Control-v>', lambda event, e=entry: self.paste_to_entry(event, e))
            entry.bind('<Button-3>', lambda event, e=entry: self.right_click_menu(event, e))

        # Allow output to expand
        self.rowconfigure(4, weight=1)

    def _build_input_frame(self):
        input_frame = ttk.LabelFrame(self, text="Parameters")
        input_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")  # MODIFIED: sticky="ew"
        input_frame.columnconfigure((0,1,2,3), weight=1)
        # MODIFIED: No row weights needed as content is fixed
        
        # Row 0: Balance and Bet Divisor
        ttk.Label(input_frame, text="Balance:").grid(row=0, column=0, sticky="w", pady=2, padx=5)
        balance_entry = ttk.Entry(input_frame, textvariable=self.balance_var, width=12)
        balance_entry.grid(row=0, column=1, pady=2, padx=5)
        ToolTip(balance_entry, "Enter your current balance here.")
        self.all_entries.append(balance_entry)

        ttk.Label(input_frame, text="Balance Divisor:").grid(row=0, column=2, sticky="w", pady=2, padx=5)
        bet_div_entry = ttk.Entry(input_frame, textvariable=self.bet_div_var, width=12)
        bet_div_entry.grid(row=0, column=3, pady=2, padx=5)
        ToolTip(bet_div_entry, "Your balance will be divided by this number to determine bet size.")
        self.all_entries.append(bet_div_entry)

        # Row 1: Win Increase and Profit Multiplier
        ttk.Label(input_frame, text="Win Increase %:").grid(row=1, column=0, sticky="w", pady=2, padx=5)
        w_entry = ttk.Entry(input_frame, textvariable=self.w_var, width=12)
        w_entry.grid(row=1, column=1, pady=2, padx=5)
        ToolTip(w_entry, "The percentage your bet increases after a win.")
        self.all_entries.append(w_entry)

        ttk.Label(input_frame, text="Profit Multiplier:").grid(row=1, column=2, sticky="w", pady=2, padx=5)
        profit_mult_entry = ttk.Entry(input_frame, textvariable=self.profit_mult_var, width=12)
        profit_mult_entry.grid(row=1, column=3, pady=2, padx=5)
        ToolTip(profit_mult_entry, "Your bet size will be multiplied by this number to determine profit stop.")
        self.all_entries.append(profit_mult_entry)

        # Row 2: Loss Reset and Buffer
        ttk.Label(input_frame, text="Loss Reset (whole):").grid(row=2, column=0, sticky="w", pady=2, padx=5)
        l_entry = ttk.Entry(input_frame, textvariable=self.l_var, width=12)
        l_entry.grid(row=2, column=1, pady=2, padx=5)
        ToolTip(l_entry, "Number of consecutive losses before resetting the bet to base value.")
        self.all_entries.append(l_entry)

        ttk.Label(input_frame, text="Buffer (%):").grid(row=2, column=2, sticky="w", pady=2, padx=5)
        buffer_entry = ttk.Entry(input_frame, textvariable=self.buffer_var, width=12)
        buffer_entry.grid(row=2, column=3, pady=2, padx=5)
        ToolTip(buffer_entry, "Boosts the calculated multiplier to help ensure the balance remains higher after cycles.")
        self.all_entries.append(buffer_entry)

        # Button
        ttk.Button(input_frame, text="How To Set Up", command=self.show_getting_started_info).grid(row=3, column=0, columnspan=4, pady=10)

    def _build_values_frame(self):
        values_frame = ttk.LabelFrame(self, text="Calculated Values")
        values_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")  # MODIFIED: sticky        
        values_frame.columnconfigure((0,2), weight=0)
        values_frame.columnconfigure((1,3), weight=1)

        # Multiplier
        ttk.Label(values_frame, text="Multiplier:").grid(row=0, column=0, sticky="w", padx=5)
        multi_frame = ttk.Frame(values_frame)
        multi_frame.grid(row=0, column=1, sticky="ew")
        multi_value = ttk.Label(multi_frame, textvariable=self.multiplier_var, font=('Arial', 10, 'bold'))
        multi_value.grid(row=0, column=0, padx=5)
        multi_copy = ttk.Button(multi_frame, text="Copy", command=lambda: self.copy_with_check(self.multiplier_var.get(), self.multi_check))
        multi_copy.grid(row=0, column=1, padx=5)
        self.multi_check = ttk.Label(multi_frame, text="")
        self.multi_check.grid(row=0, column=2, padx=5)

        # Bet Size
        ttk.Label(values_frame, text="Bet Size:").grid(row=1, column=0, sticky="w", padx=5)
        bet_frame = ttk.Frame(values_frame)
        bet_frame.grid(row=1, column=1, sticky="ew")
        bet_value = ttk.Label(bet_frame, textvariable=self.bet_size_var, font=('Arial', 10, 'bold'))
        bet_value.grid(row=0, column=0, padx=5)
        bet_copy = ttk.Button(bet_frame, text="Copy", command=lambda: self.copy_with_check(self.bet_size_var.get(), self.bet_check))
        bet_copy.grid(row=0, column=1, padx=5)
        self.bet_check = ttk.Label(bet_frame, text="")
        self.bet_check.grid(row=0, column=2, padx=5)

        # Profit Stop
        ttk.Label(values_frame, text="Profit Stop:").grid(row=0, column=2, sticky="w", padx=5)
        profit_frame = ttk.Frame(values_frame)
        profit_frame.grid(row=0, column=3, sticky="ew")
        profit_value = ttk.Label(profit_frame, textvariable=self.profit_stop_var, font=('Arial', 10, 'bold'))
        profit_value.grid(row=0, column=0, padx=5)
        profit_copy = ttk.Button(profit_frame, text="Copy", command=lambda: self.copy_with_check(self.profit_stop_var.get(), self.profit_check))
        profit_copy.grid(row=0, column=1, padx=5)
        self.profit_check = ttk.Label(profit_frame, text="")
        self.profit_check.grid(row=0, column=2, padx=5)

        # Balance Target
        ttk.Label(values_frame, text="Balance Target:").grid(row=1, column=2, sticky="w", padx=5)
        balance_frame = ttk.Frame(values_frame)
        balance_frame.grid(row=1, column=3, sticky="ew")
        balance_value = ttk.Label(balance_frame, textvariable=self.balance_target_var, font=('Arial', 10, 'bold'))
        balance_value.grid(row=0, column=0, padx=5)
        balance_copy = ttk.Button(balance_frame, text="Copy", command=lambda: self.copy_with_check(self.balance_target_var.get(), self.balance_check))
        balance_copy.grid(row=0, column=1, padx=5)
        self.balance_check = ttk.Label(balance_frame, text="")
        self.balance_check.grid(row=0, column=2, padx=5)

    def _build_sim_control_frame(self):
        sim_frame = ttk.LabelFrame(self, text="Simulation Controls")
        sim_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        sim_frame.columnconfigure(0, weight=1)

        ttk.Label(sim_frame, text="Trials:").grid(row=0, column=0, sticky="w", padx=5)
        n_trials_entry = ttk.Entry(sim_frame, textvariable=self.n_trials_var, width=12)
        n_trials_entry.grid(row=0, column=1, padx=5)
        ToolTip(n_trials_entry, "Number of simulation trials to run.")
        self.all_entries.append(n_trials_entry)

        self.run_button = ttk.Button(sim_frame, text="Run Simulation")
        self.run_button.grid(row=0, column=2, padx=5, pady=5)
        self.sim_progress = ttk.Progressbar(sim_frame, orient="horizontal", mode="determinate", length=200)
        self.sim_progress.grid(row=0, column=3, padx=5, pady=5)

        ttk.Button(sim_frame, text="How Simulator Works", command=self.show_simulator_info).grid(row=0, column=4, padx=5, pady=5)

        self.sim_stop_button = ttk.Button(sim_frame, text="Stop", state="disabled")
        self.sim_stop_button.grid(row=0, column=5, padx=5, pady=5)

    def _build_output_frame(self):
        output_frame = ttk.LabelFrame(self, text="Simulation Results")
        output_frame.grid(row=4, column=0, padx=10, pady=10, sticky="nsew")  # MODIFIED: sticky="nsew" for full expansion
        output_frame.rowconfigure(0, weight=1)
        output_frame.columnconfigure(0, weight=1)

        self.sim_tree = ttk.Treeview(output_frame, columns=("stat", "value"), show='headings', height=17)        
        self.sim_tree.heading("stat", text="Statistic")
        self.sim_tree.heading("value", text="Value")
        self.sim_tree.column("stat", width=420, anchor="w")
        self.sim_tree.column("value", width=420, anchor="w")
        self.sim_tree.grid(row=0, column=0, sticky="nsew")  # MODIFIED: sticky for resize

        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.sim_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.sim_tree.configure(yscrollcommand=scrollbar.set)

    def calculate_values(self, *args):
        """Calculates derived values from inputs."""
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

    def copy_with_check(self, value, check_label):
        if not value or value == "Invalid":
            return
        self.master.clipboard_clear()
        self.master.clipboard_append(value)
        check_label.config(text="✓")
        check_label.after(1000, lambda: check_label.config(text=""))

    def paste_to_entry(self, event, entry):
        try:
            entry.insert(tk.INSERT, self.master.clipboard_get())
        except tk.TclError:
            pass
        return "break"

    def right_click_menu(self, event, entry):
        menu = tk.Menu(self, tearoff=0)
        try:
            menu.add_command(label="Paste", command=lambda: entry.insert(tk.INSERT, self.master.clipboard_get()))
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def show_simulator_info(self):
        info_text = (
            "1.) All values from the parameters and calculated values sections are used in the simulation.\n\n"
            "2.) Each time the profit stop is met, the cycle ends and counts as a successful cycle.\n\n"
            "3.) Next cycle begins using the ending balance from previous cycle until bust.\n\n"
            "4.) Each trial ends when balance hits 0.\n\n"
            "5.) Successful cycles are the cycles that reached the profit stop."
        )
        messagebox.showinfo("How The Simulator Works", info_text)

    def show_getting_started_info(self):
        info_text = (
            "STEP 1:\n\n"
            "In your dice game, make a new advanced strategy with the following conditions:\n\n"
            "1) On every 1 win increase bet amount by 'Win Increase %'\n\n"
            "2) On every streak of 'Loss Reset' losses, reset bet amount\n\n"
            "3) On greater than or equal to 'Profit Stop' profit/net gain, Stop autoplay\n\n\n"
            "STEP 2:\n\n"
            "Enter your starting balance and the remaining parameters. This will populate the calculated values section, where you will copy the Bet Size and Profit Stop into your game.\n\n\n"
            "STEP 3:\n\n"
            "When Profit Stop is met, update your balance Balance and repeat the process."
        )
        messagebox.showinfo("How To Set Up", info_text)

    def get_sim_params(self) -> SimParams:
        """Extracts simulation parameters from UI variables."""
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
            raise ValueError("Invalid input values")
        return SimParams(starting_balance, bet_div, profit_mult, w, l, buffer, n_trials)

    def display_sim_results(self, stats: List[Tuple[str, str]]):
        """Displays simulation results in the treeview."""
        for i in self.sim_tree.get_children():
            self.sim_tree.delete(i)
        for stat, val in stats:
            self.sim_tree.insert("", "end", values=(stat, val))