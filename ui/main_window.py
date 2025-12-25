# Dice_Tool/ui/main_window.py
import tkinter as tk
from tkinter import ttk, messagebox
import queue
import threading
from typing import List, Tuple
from statistics import mean, stdev, median
import traceback

from simulation_core import SimParams, run_many_trials
from optimizer import OptParams, parse_range, optimize_parameters_manual
from .calc_tab import CalculatorTab
from .opt_tab import OptimizerTab
from .results_tab import ResultsTab
from .terms_tab import TermsTab
from .settings_tab import SettingsTab

# New: import state manager
from .state_manager import save_state, load_state, default_state_path

THEMES = {
    "Original": {
        "bg": "#3f3f3f",
        "fg": "#17c7b8",
        "label_fg": "#249f87",
        "field_bg": "#2d2d2d",
        "select_bg": "#17c7b8",
        "select_fg": "#000000",
        "button_bg": "#333333",
        "button_active": "#555555",
        "heading_bg": "#333333",
        "trough": "#555555",
        "progress_bg": "#00ff80",
        "root_bg": "#17c7b8",
        "text_bg": "#2e2e2e",
        "text_fg": "#ffffff",
        "text_select_bg": "#249f87",
    },
    "Stake": {
        "bg": "#162a35",
        "fg": "#c9d1d9",
        "label_fg": "#c9d1d9",
        "field_bg": "#071824",
        "select_bg": "#1f333e",
        "select_fg": "#c9d1d9",
        "button_bg": "#071824",
        "button_active": "#1a2c38",
        "heading_bg": "#071824",
        "trough": "#071824",
        "progress_bg": "#00ff80",
        "root_bg": "#162a35",
        "text_bg": "#0f212e",
        "text_fg": "#071824",
        "text_select_bg": "#1a2c38",
    },
    "Shuffle": {
        "bg": "#131313",
        "fg": "#ffffff",
        "label_fg": "#a855f7",
        "field_bg": "#363636",
        "select_bg": "#a855f7",
        "select_fg": "#131313",
        "button_bg": "#363636",
        "button_active": "#a855f7",
        "heading_bg": "#363636",
        "trough": "#222222",
        "progress_bg": "#a855f7",
        "root_bg": "#131313",
        "text_bg": "#363636",
        "text_fg": "#ffffff",
        "text_select_bg": "#a855f7",
    },
}

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

        self.large_fonts = tk.BooleanVar(value=False)
        self.keep_previous_results = tk.BooleanVar(value=False)
        self.current_theme = tk.StringVar(value="Original")
        self.THEMES = THEMES

        # Build UI
        self._build_ui()

        # Load saved state if any (non-fatal)
        try:
            state = load_state(default_state_path())
            self.restore_app_state(state)
        except Exception:
            # ignore loading errors
            pass

        # Apply theme after possibly restoring theme setting
        self.apply_theme(self.current_theme.get())

        # Bind to close to save the state
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.after(100, self.process_queue)

    def on_close(self):
        """Save state and close the app."""
        try:
            state = self.get_app_state()
            save_state(state, default_state_path())
        except Exception:
            # never block close on save error
            try:
                traceback.print_exc()
            except Exception:
                pass
        # destroy the window and exit
        try:
            self.destroy()
        except Exception:
            pass

    def get_app_state(self) -> dict:
        """Collect the application state into a serializable dict."""
        st = {
            "settings": {
                "current_theme": self.current_theme.get(),
                "large_fonts": bool(self.large_fonts.get()),
                "keep_previous_results": bool(self.keep_previous_results.get())
            },
            "calculator": {},
            "optimizer": {},
            "results": {}
        }
        # Calculator inputs (if calc_tab exists)
        try:
            if hasattr(self, "calc_tab"):
                st["calculator"] = {
                    "balance": self.calc_tab.balance_var.get(),
                    "bet_div": self.calc_tab.bet_div_var.get(),
                    "profit_mult": self.calc_tab.profit_mult_var.get(),
                    "w": self.calc_tab.w_var.get(),
                    "l": self.calc_tab.l_var.get(),
                    "buffer": self.calc_tab.buffer_var.get(),
                    "n_trials": self.calc_tab.n_trials_var.get(),
                }
        except Exception:
            pass

        # Optimizer inputs
        try:
            if hasattr(self, "opt_tab"):
                st["optimizer"] = {
                    "starting_balance": self.opt_tab.opt_balance_var.get(),
                    "n_trials": self.opt_tab.opt_n_trials_var.get(),
                    "bet_div_range": self.opt_tab.opt_bet_div_var.get(),
                    "profit_mult_range": self.opt_tab.opt_profit_mult_var.get(),
                    "w_range": self.opt_tab.opt_w_var.get(),
                    "l_range": self.opt_tab.opt_l_var.get(),
                    "buffer_range": self.opt_tab.opt_buffer_var.get(),
                }
        except Exception:
            pass

        # Results table rows and columns (best-effort)
        try:
            if hasattr(self, "results_tab"):
                cols = []
                try:
                    # Try known attribute first
                    cols = list(getattr(self.results_tab, "cols", []))
                    if not cols:
                        # Fall back to treeview columns
                        cols = list(self.results_tab.res_tree["columns"])
                except Exception:
                    cols = list(self.results_tab.res_tree["columns"]) if hasattr(self.results_tab, "res_tree") else []
                rows = []
                if hasattr(self.results_tab, "res_tree"):
                    for i in self.results_tab.res_tree.get_children():
                        vals = self.results_tab.res_tree.item(i).get("values", [])
                        # Convert to strings for JSON safety
                        rows.append([str(v) for v in vals])
                st["results"] = {"cols": cols, "rows": rows}
        except Exception:
            st["results"] = {"cols": [], "rows": []}

        return st

    def restore_app_state(self, state: dict):
        """Restore the UI state from previously saved dict."""
        if not isinstance(state, dict):
            return

        # Settings
        try:
            s = state.get("settings", {})
            theme = s.get("current_theme")
            if theme:
                self.current_theme.set(theme)
                # Ensure the Settings tab combobox reflects the restored value
                try:
                    if hasattr(self, "settings_tab") and hasattr(self.settings_tab, "theme_combo"):
                        self.settings_tab.theme_combo.set(theme)
                except Exception:
                    pass
            lf = s.get("large_fonts")
            if lf is not None:
                self.large_fonts.set(bool(lf))
            kp = s.get("keep_previous_results")
            if kp is not None:
                self.keep_previous_results.set(bool(kp))
        except Exception:
            pass

        # Calculator
        try:
            calc = state.get("calculator", {})
            if calc and hasattr(self, "calc_tab"):
                # set string values directly to avoid conversion exceptions
                for k, v in calc.items():
                    if hasattr(self.calc_tab, f"{k}_var"):
                        var = getattr(self.calc_tab, f"{k}_var")
                        try:
                            var.set(str(v))
                        except Exception:
                            pass
                # refresh calculated values if method exists
                try:
                    self.calc_tab.calculate_values()
                except Exception:
                    pass
        except Exception:
            pass

        # Optimizer
        try:
            opt = state.get("optimizer", {})
            if opt and hasattr(self, "opt_tab"):
                mapping = {
                    "starting_balance": "opt_balance_var",
                    "n_trials": "opt_n_trials_var",
                    "bet_div_range": "opt_bet_div_var",
                    "profit_mult_range": "opt_profit_mult_var",
                    "w_range": "opt_w_var",
                    "l_range": "opt_l_var",
                    "buffer_range": "opt_buffer_var",
                }
                for k, varname in mapping.items():
                    if k in opt and hasattr(self.opt_tab, varname):
                        try:
                            getattr(self.opt_tab, varname).set(str(opt[k]))
                        except Exception:
                            pass
        except Exception:
            pass

        # Results
        try:
            results_state = state.get("results", {})
            if results_state and hasattr(self, "results_tab"):
                rows = results_state.get("rows", [])
                # Clear existing rows if possible
                try:
                    if hasattr(self.results_tab, "clear_opt_results"):
                        self.results_tab.clear_opt_results()
                    else:
                        # fallback: delete tree children directly
                        if hasattr(self.results_tab, "res_tree"):
                            for c in self.results_tab.res_tree.get_children():
                                self.results_tab.res_tree.delete(c)
                except Exception:
                    pass

                # Insert saved rows
                try:
                    if hasattr(self.results_tab, "res_tree"):
                        for row in rows:
                            # ensure tuple values
                            try:
                                self.results_tab.res_tree.insert("", "end", values=tuple(row))
                            except Exception:
                                # best-effort insertion
                                try:
                                    self.results_tab.res_tree.insert("", "end", values=tuple([str(r) for r in row]))
                                except Exception:
                                    pass
                        # Try to update colors if method present
                        try:
                            if hasattr(self.results_tab, "update_row_colors"):
                                self.results_tab.update_row_colors()
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    def apply_theme(self, theme_name: str):
        self.current_theme.set(theme_name)
        colors = THEMES.get(theme_name, THEMES["Original"])
        base_font_size = 13 if self.large_fonts.get() else 9

        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure('.', background=colors["bg"], foreground=colors["fg"],
                        font=('Segoe UI', base_font_size))
        style.configure('TFrame', background=colors["bg"])
        style.configure('TLabel', background=colors["bg"], foreground=colors["label_fg"])
        style.configure('Treeview', rowheight=base_font_size + 9)  # dynamic row height

        # Proper theming for ttk.Entry / TCombobox / Treeview / Progressbar
        style.configure('TEntry',
                        fieldbackground=colors["field_bg"],
                        foreground=colors["fg"])
        style.map('TEntry',
                  fieldbackground=[('selected', colors["select_bg"]),
                                   ('readonly', colors["field_bg"])],
                  selectbackground=[('selected', colors["select_bg"])],
                  selectforeground=[('selected', colors["select_fg"])])

        style.configure('TCombobox',
                        fieldbackground=colors["field_bg"],
                        foreground=colors["fg"])
        style.map('TCombobox',
                  fieldbackground=[('readonly', colors["field_bg"])])

        style.configure('Treeview',
                        background=colors["field_bg"],
                        fieldbackground=colors["bg"],
                        foreground=colors["fg"])
        style.map('Treeview',
                  background=[('selected', colors["select_bg"])],
                  foreground=[('selected', colors["select_fg"])])

        style.configure('Treeview.Heading',
                        background=colors.get("heading_bg", colors["bg"]),
                        foreground=colors["fg"],
                        font=('Segoe UI', base_font_size, 'bold'))
        style.map('Treeview.Heading',
                  background=[('active', colors["button_active"])],
                  foreground=[('active', colors["fg"])])

        style.configure('Horizontal.TProgressbar',
                        background=colors["progress_bg"],
                        troughcolor=colors["trough"])

        # Notebook tab styling
        style.configure('TNotebook', background=colors["root_bg"])
        style.configure('TNotebook.Tab', background=colors["bg"], foreground=colors["label_fg"])
        style.map('TNotebook.Tab',
                  background=[('selected', colors["select_bg"])],
                  foreground=[('selected', colors["select_fg"])])

        self.configure(bg=colors["root_bg"])

        if hasattr(self, 'terms_tab'):
            self.terms_tab.text.configure(
                bg=colors["text_bg"], fg=colors["text_fg"],
                insertbackground=colors["text_fg"],
                selectbackground=colors["text_select_bg"],
                selectforeground="black",
                font=('Segoe UI', base_font_size)
            )
            heading_size = base_font_size + 4
            self.terms_tab.text.tag_config("heading", foreground=colors["label_fg"],
                                            font=('Segoe UI', heading_size + 4, "bold"))
            self.terms_tab.text.tag_config("subheading", foreground=colors["label_fg"],
                                            font=('Segoe UI', heading_size + 2, "bold"))
            self.terms_tab.text.tag_config("label", foreground=colors["label_fg"],
                                            font=('Segoe UI', base_font_size, "bold"))
            self.terms_tab.text.tag_config("definition", font=('Segoe UI', base_font_size))

        if hasattr(self, 'settings_tab'):
            self.settings_tab.update_fonts(base_font_size + 3)

        def update_recursive(parent):
            for child in parent.winfo_children():
                if isinstance(child, tk.LabelFrame):
                    child.configure(bg=colors["bg"], fg=colors["label_fg"],
                                    highlightbackground=colors["label_fg"])
                if isinstance(child, tk.Text):  # Only tk.Text gets manual bg (ScrolledText internal). ttk.Entry is themed via style above.
                    child.configure(bg=colors["text_bg"], fg=colors["text_fg"],
                                    insertbackground=colors["text_fg"],
                                    font=('Segoe UI', base_font_size))
                update_recursive(child)
        update_recursive(self)

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

        self.settings_tab = SettingsTab(nb, self)
        nb.add(self.settings_tab, text="Settings")

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
