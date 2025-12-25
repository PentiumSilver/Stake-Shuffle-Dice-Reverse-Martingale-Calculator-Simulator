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

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=0)
        self.rowconfigure(1, weight=1)
        self.rowconfigure(2, weight=0)
        self.rowconfigure(3, weight=0)

        # Updated column order with new columns
        self.cols = ("StartingBalance", "Trials", "BetDiv", "ProfitMult", "W%", "L", "Buffer%",
                     "AvgHigh", "StdDev", "MaxHigh", "AvgCycles", "AvgRounds",
                     "CycleSuccess%", "Bust%", "Score")

        self.res_tree = ttk.Treeview(self, columns=self.cols, show="headings", height=20)
        style.configure('Treeview', rowheight=18)
        for col in self.cols:
            self.res_tree.heading(col, text=col, command=lambda c=col: self.sort_res_column(c, False))
            self.res_tree.column(col, anchor="center", minwidth=80, width=100)
        self.res_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=10)

        v_scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.res_tree.yview)
        v_scrollbar.grid(row=1, column=2, sticky="ns")
        self.res_tree.configure(yscrollcommand=v_scrollbar.set)

        h_scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.res_tree.xview)
        h_scrollbar.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.res_tree.configure(xscrollcommand=h_scrollbar.set)

        ttk.Button(self, text="Save to CSV", command=self.save_opt_csv).grid(row=3, column=0, pady=5, sticky="e")
        self.apply_button = ttk.Button(self, text="Apply Selected to Calculator")
        self.apply_button.grid(row=3, column=0, pady=5, sticky="w")

        # Configure tags for alternating row shading (using dark shades to match common themes)
        self.res_tree.tag_configure("evenrow", background="#2d2d2d")
        self.res_tree.tag_configure("oddrow", background="#383838")

    def display_opt_results(self, df: pd.DataFrame):
        app = self.master.master  # MergedApp instance
        if not app.keep_previous_results.get():
            self.clear_opt_results()
        if df.empty:
            messagebox.showinfo("No Results", "No results were produced.")
            return
        for _, row in df.iterrows():
            vals = (
                f"{row['StartingBalance']:.2f}",
                f"{row['Trials']}",
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
        self.update_row_colors()

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
        self.update_row_colors()

    def apply_selected_to_calculator(self, calc_tab: "CalculatorTab"):
        sel = self.res_tree.selection()
        if not sel:
            messagebox.showinfo("No Selection", "Select a row in Optimizer Results first.")
            return
        vals = self.res_tree.item(sel[0])["values"]
        try:
            # StartingBalance and Trials are now present but not used for apply
            bet_div = float(vals[2])
            profit_mult = float(vals[3])
            w_pct = float(vals[4])
            l = int(float(vals[5]))
            buffer_pct = float(vals[6])

            calc_tab.bet_div_var.set(str(bet_div))
            calc_tab.profit_mult_var.set(str(profit_mult))
            calc_tab.w_var.set(str(w_pct))
            calc_tab.l_var.set(str(l))
            calc_tab.buffer_var.set(str(buffer_pct))
            calc_tab.calculate_values()
            messagebox.showinfo("Applied", "Selected parameters applied to Calculator / Simulator tab.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not apply values: {e}")

    def update_row_colors(self):
        """Apply alternating row colors based on current display order."""
        children = self.res_tree.get_children()
        for i, iid in enumerate(children):
            tag = "evenrow" if i % 2 == 0 else "oddrow"
            self.res_tree.item(iid, tags=(tag,))

# Add these methods to the ResultsTab class in ui/results_tab.py

    def get_results_state(self) -> dict:
        """
        Return a serializable representation of current optimizer results table:
        { "cols": [...], "rows": [[...], ...] }
        """
        try:
            cols = getattr(self, "cols", None)
            if not cols:
                # attempt to get from treeview headings
                cols = [self.res_tree.heading(c)["text"] for c in self.res_tree["columns"]]
            rows = [self.res_tree.item(i)["values"] for i in self.res_tree.get_children()]
            # Convert any non-serializable types to strings
            serial_rows = []
            for row in rows:
                serial_rows.append([str(v) for v in row])
            return {"cols": list(cols), "rows": serial_rows}
        except Exception:
            return {"cols": [], "rows": []}

    def load_results_state(self, state: dict):
        """
        Load results state previously saved by get_results_state.
        Expects { "cols": [...], "rows": [[...], ...] }
        """
        try:
            if not isinstance(state, dict):
                return
            rows = state.get("rows", [])
            # Clear existing rows
            self.clear_opt_results()
            # Insert rows (make sure to convert to appropriate types/formatting if necessary)
            for row in rows:
                # row is a list of strings; insert as-is
                self.res_tree.insert("", "end", values=tuple(row))
            self.update_row_colors()
        except Exception:
            pass
