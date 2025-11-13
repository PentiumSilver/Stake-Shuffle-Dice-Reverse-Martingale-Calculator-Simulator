# Dice_Tool/ui/terms_tab.py
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

TERMS_TEXT = r"""
**CALCULATOR / SIMULATOR TAB**

*PARAMETERS*
Balance – Your total bankroll for each simulation or calculation.
Win Increase % – The percentage amount the bet increases after every win.
Loss Reset – The number of consecutive losses required before resetting the bet to its base size.
Balance Divisor – A number dividing the balance to determine the starting bet size. (Higher numbers create smaller bet sizes).
Profit Multiplier – The multiplier applied to the base bet that defines the profit stop.
Buffer % – An additional percentage added to the multiplier for extra margin or protection.

*CALCULATED VALUES*
Multiplier – The payout odds or target multiplier determined by input parameters.
Bet Size – The first wager placed based on the current balance and balance divisor.
Profit Stop – The profit goal for the current cycle, derived from the bet and multiplier.
Balance Target – The balance amount where the simulation stops a successful cycle.

*SIMULATION CONTROLS*
Trials – The number of simulated runs to execute. Higher values improve accuracy but take longer.
Run Simulation – Starts the simulation with the selected settings.
Stop – Cancels an ongoing simulation process.

*SIMULATION RESULTS*
Cycle – A completed round reaching the profit target or failing (bust).
Average highest balance – The median of all highest balances reached across all trials.
Std dev (highest) – The standard deviation of highest balances, showing consistency or volatility.
Max highest balance – The single greatest balance achieved in all trials.
Average cycles – The average count of successful profit cycles per trial.
Average rounds – The average number of dice rolls per trial.
Cycle success rate – The percentage of total cycles that reached profit target before failure.
Bust rate – The percentage of trials that failed to meet the first profit stop.


**OPTIMIZER TAB**

*PARAMETER RANGES*
Combo – A single set of parameter values tested by the optimizer.
Starting Balance – The initial balance applied to all combos during optimization.
Trials per Combo – The number of simulations run for each parameter combination.
Bet Divisor Range – Range or list of values to test for bet divisors.
Profit Multiplier Range – Range or list of values to test for profit multipliers.
Win Increase % Range – Range or list of win increase percentages to test.
Loss Reset – Range or list of loss reset counts to test.
Buffer % Range – Range or list of buffer percentages to test.

*BUTTONS*
Run Optimizer – Begins testing all combinations using the provided ranges.
Clear Results – Removes existing results from the results tab.
Stop – Terminates the optimization process currently running. (*Note:* If you get the 'Large Search Warning' popup, you won't be able to use the 'Stop' button to stop the process. Doing so may potentially break the optimizer and you will need to close the app and relaunch it again to use the optimizer.. )


**OPTIMIZER RESULTS TAB**

*RESULTS DEFINITIONS*
BetDiv – Bet divisor used in the tested combo.
ProfitMult – Profit multiplier applied to that combo.
W% – Win increase percentage value.
L – Number of losses before reset.
Buffer% – Additional buffer percentage applied to the multiplier.
AvgHigh – The average of highest balances across trials.
StdDev – The standard deviation of highest balances, measuring risk.
MaxHigh – The maximum balance achieved in any trial.
AvgCycles – Average successful profit cycles achieved per trial.
AvgRounds – Average number of rolls executed per trial.
CycleSuccess% – Percentage of cycles that reached profit targets successfully.
Bust% – Percentage of trials that ended with no successful cycles (busts).
Score – Performance metric calculated as (AvgHigh - Start) / StdDev.

*BUTTONS*
Apply Selected to Calculator – Loads parameters from a selected result row into the Calculator tab for testing.
Save to CSV – Exports all result rows into a CSV file for later review.
"""


class TermsTab(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)  # MODIFIED: Already present, but confirm expansion

        self.text = ScrolledText(self, wrap="word", state="normal", font=("Segoe UI", 10))
        self.text.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)  # MODIFIED: Already sticky, good for resize
        # Define tags for bold and backgrounds
        self.text.tag_config("bold", font=("Segoe UI", 12, "bold"))
        self.text.tag_config("subbold", font=("Segoe UI", 11, "bold"))

        background_colors = ["#add8e6", "#90ee90", "#ffe0ea"]  # Light blue, light green, light yellow
        bg_index = -1  # Start before first increment
        current_bg_tag = None

        # Split TERMS_TEXT into lines
        lines = TERMS_TEXT.splitlines()

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("**") and stripped.endswith("**"):
                # New major section, increment bg_index
                bg_index += 1
                if bg_index < len(background_colors):
                    current_bg_tag = f"bg{bg_index}"
                    self.text.tag_config(current_bg_tag, background=background_colors[bg_index])
                header_text = stripped[2:-2]
                tags = ("bold", current_bg_tag) if current_bg_tag else ("bold",)
                self.text.insert("end", header_text + "\n", tags)
            elif stripped.startswith("*") and stripped.endswith("*"):
                header_text = stripped[1:-1]
                tags = ("subbold", current_bg_tag) if current_bg_tag else ("subbold",)
                self.text.insert("end", header_text + "\n", tags)
            else:
                tags = (current_bg_tag,) if current_bg_tag else ()
                self.text.insert("end", line + "\n", tags)

        self.text.configure(state="disabled")