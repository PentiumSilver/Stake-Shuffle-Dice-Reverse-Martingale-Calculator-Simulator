# Dice_Tool/ui/results_tab.py
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter import filedialog
import pandas as pd
from ui.calc_tab import CalculatorTab

class ResultsTab(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        style = ttk.Style()
        style.configure("Results.TFrame", background="#ffe0ea")

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)  # For scrollbars
        self.rowconfigure(1, weight=1)  # Treeview expands
        self.rowconfigure(2, weight=0)  # H-scrollbar
        self.rowconfigure(3, weight=0)  # Buttons

        # MODIFIED FOR PRECISE MEASUREMENT: Set minwidth on columns
        self.cols = ("BetDiv", "ProfitMult", "W%", "L", "Buffer%", "AvgHigh", "StdDev", "MaxHigh", "AvgCycles", "AvgRounds", "CycleSuccess%", "Bust%", "Score")
        self.res_tree = ttk.Treeview(self, columns=self.cols, show="headings", height=20)
        for col in self.cols:
            self.res_tree.heading(col, text=col, command=lambda c=col: self.sort_res_column(c, False))
            self.res_tree.column(col, anchor="center", minwidth=80, width=100)  # MODIFIED: minwidth for precision
        self.res_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)  # MODIFIED: sticky
        v_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.res_tree.yview)
        v_scrollbar.grid(row=1, column=2, sticky="ns")  # Changed from row=0
        self.res_tree.configure(yscrollcommand=v_scrollbar.set)

        h_scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.res_tree.xview)
        h_scrollbar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.res_tree.configure(xscrollcommand=h_scrollbar.set)

        ttk.Button(self, text="Save to CSV", command=self.save_opt_csv).grid(row=3, column=0, pady=5, sticky="e")
        self.apply_button = ttk.Button(self, text="Apply Selected to Calculator")
        self.apply_button.grid(row=3, column=0, pady=5, sticky="w")
        
    def display_opt_results(self, df: pd.DataFrame):
        self.clear_opt_results()
        if df.empty:
            messagebox.showinfo("No Results", "No results were produced.")
            return
        for _, row in df.iterrows():
            vals = (
                f"{row['BetDiv']:.2f}",
                f"{row['ProfitMult']:.2f}",
                f"{row['W%']:.2f}",
                f"{row['L']}",
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

    def clear_opt_results(self):
        for i in self.res_tree.get_children():
            self.res_tree.delete(i)

    def save_opt_csv(self):
        rows = [self.res_tree.item(i)["values"] for i in self.res_tree.get_children()]
        if not rows:
            messagebox.showinfo("No Data", "No results to save.")
            return
        file = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if not file:
            return
        pd.DataFrame(rows, columns=self.cols).to_csv(file, index=False)
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

    def apply_selected_to_calculator(self, calc_tab: "CalculatorTab"):
        sel = self.res_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a row in Optimizer Results first.")
            return
        vals = self.res_tree.item(sel[0])["values"]
        try:
            bet_div = float(vals[0])
            profit_mult = float(vals[1])
            w_pct = float(vals[2])
            l = int(float(vals[3]))
            buffer_pct = float(vals[4])

            calc_tab.bet_div_var.set(str(bet_div))
            calc_tab.profit_mult_var.set(str(profit_mult))
            calc_tab.w_var.set(str(w_pct))
            calc_tab.l_var.set(str(l))
            calc_tab.buffer_var.set(str(buffer_pct))
            calc_tab.calculate_values()
            messagebox.showinfo("Applied", "Selected parameters applied to Calculator / Simulator tab.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not apply values: {e}")