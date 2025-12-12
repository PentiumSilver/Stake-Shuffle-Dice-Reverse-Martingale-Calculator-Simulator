# Dice_Tool/ui/calc_tab.py
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Tuple
from simulation_core import SimParams
from .widgets import ToolTip
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import json


def make_handler(calc_tab):
    class CustomHandler(BaseHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            self.calc_tab = calc_tab
            super().__init__(*args, **kwargs)

        def do_GET(self):
            if self.path == '/get_values':
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                values = {
                    'bet_size': self.calc_tab.bet_size_var.get(),
                    'profit_stop': self.calc_tab.profit_stop_var.get(),
                    'multiplier': self.calc_tab.multiplier_var.get()[:-1],
                    'win_increase': self.calc_tab.w_var.get(),
                    'loss_reset': self.calc_tab.l_var.get(),
                }
                self.wfile.write(json.dumps(values).encode('utf-8'))
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == '/set_balance':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(post_data)
                balance = data.get('balance')
                if balance:
                    self.calc_tab.after(0, lambda: self.calc_tab.balance_var.set(balance))
                    self.calc_tab.after(0, self.calc_tab.calculate_values)
                    self.send_response(200)
                    self.end_headers()
                else:
                    self.send_error(400)
            else:
                self.send_error(404)

    return CustomHandler


class CalculatorTab(ttk.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=0)
        self.rowconfigure(2, weight=0)
        self.rowconfigure(3, weight=1)

        
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

        self.all_entries = []

        self.server = None
        self.server_thread = None

        self._build_calculated_values()
        self._build_parameters()
        self._build_controls()
        self._build_results()

        for var in [
            self.balance_var,
            self.w_var,
            self.l_var,
            self.bet_div_var,
            self.profit_mult_var,
            self.buffer_var,
        ]:
            var.trace_add("write", self.calculate_values)
        self.calculate_values()

        for entry in self.all_entries:
            entry.bind(
                "<Control-v>",
                lambda e, w=entry: (w.insert(tk.INSERT, self.clipboard_get()), "break"),
            )
            entry.bind("<Button-3>", lambda e, w=entry: self.right_click_menu(e, w))

    def _build_calculated_values(self):
        frame = tk.LabelFrame(self)
        frame.grid(row=0, column=0, rowspan=3, padx=(10, 5), pady=5, sticky="nsew")
        
        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=0)

        rows = [
            ("Multiplier:", self.multiplier_var),
            ("Bet Size:", self.bet_size_var),
            ("Profit Stop:", self.profit_stop_var),
            ("Balance Target:", self.balance_target_var),
        ]
        for i, (text, var) in enumerate(rows):
            ttk.Label(frame, text=text, font=("", 11, "bold")).grid(
                row=i, column=0, sticky="ew", padx=12, pady=5
            )
            ttk.Entry(
                frame,
                width=8,
                textvariable=var,
                state="readonly",
                font=("", 9),
            ).grid(row=i, column=1, sticky="ew", padx=10, pady=5)
            
            copy_btn = ttk.Button(
                frame,
                text="Copy",
                width=5,
                command=lambda var=var: self._copy_to_clipboard(var.get()),
            )
            copy_btn.grid(row=i, column=2, sticky="ew", padx=8, pady=5)

        frame.configure(
            relief="sunken",
            font="-family {Times New Roman} -size 12 -weight bold -slant italic -underline 1",
            foreground="#249f87",
            background="#3f3f3f",
            highlightbackground="#249f87",
            highlightcolor="#a9ebde",
            highlightthickness=2,
            padx=10,
            pady=10,
            takefocus=0  # Fixed: was "2"
        )
        frame.configure(text="Calculated Values")

    def _build_parameters(self):
        frame = tk.LabelFrame(self)
        frame.grid(row=0, column=1, padx=(5, 10), pady=5, sticky="nsew")

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        frame.configure(relief="sunken")
        frame.configure(
            font="-family {Times New Roman} -size 12 -weight bold -slant italic -underline 1"
        )
        frame.configure(foreground="#249f87")
        frame.configure(text="Parameters")
        frame.configure(background="#3f3f3f")
        frame.configure(highlightbackground="#249f87")
        frame.configure(highlightcolor="#a9ebde")
        frame.configure(highlightthickness="2")
        frame.configure(padx="2")
        frame.configure(pady="2")

        left_side = [
            ("Balance:", self.balance_var, "Enter your current balance here"),
            (
                "Win Increase %:",
                self.w_var,
                "The percentage your bet increases after a win",
            ),
            (
                "Loss Reset:",
                self.l_var,
                "Number of consecutive losses before resetting the bet to base value",
            ),
        ]
        right_side = [
            (
                "Balance Divisor:",
                self.bet_div_var,
                "Your balance will be divided by this number to determine bet size",
            ),
            (
                "Profit Multiplier:",
                self.profit_mult_var,
                "Your bet size will be multiplied by this number to determine the profit stop",
            ),
            (
                "Buffer %:",
                self.buffer_var,
                "Boosts the calculated multiplier to help ensure the balance remains higher after cycles",
            ),
        ]

        for i, (text, var, tip) in enumerate(left_side):
            ttk.Label(frame, text=text, font=("", 11, "bold")).grid(
                row=i, column=0, sticky="ew", padx=12, pady=4
            )
            entry = ttk.Entry(frame, textvariable=var, width=7)
            entry.grid(row=i, column=1, sticky="ew", padx=10, pady=4)
            self.all_entries.append(entry)
            ToolTip(entry, tip)

        for i, (text, var, tip) in enumerate(right_side):
            ttk.Label(frame, text=text, font=("", 11, "bold")).grid(
                row=i, column=2, sticky="ew", padx=12, pady=4
            )
            entry = ttk.Entry(frame, textvariable=var, width=7)
            entry.grid(row=i, column=3, sticky="ew", padx=10, pady=4)
            self.all_entries.append(entry)
            ToolTip(entry, tip)

        ttk.Button(
            frame, text="How To Setup", command=self.show_getting_started_info
        ).grid(row=3, column=3, pady=6, sticky="ew", padx=12)

        self.start_server_btn = ttk.Button(
            frame, text="Start Local Server", command=self.toggle_server
        )
        self.start_server_btn.grid(row=3, column=0, columnspan=3, pady=6, sticky="ew", padx=12)

    def _build_controls(self):
        frame = tk.LabelFrame(self)
        frame.grid(row=1, column=1, padx=(5, 10), pady=(0, 5), sticky="ew")
        
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=1)
        frame.columnconfigure(3, weight=1)

        self.run_button = ttk.Button(frame, text="Run Simulation")
        self.run_button.grid(row=0, column=0, padx=12, pady=5, sticky="ew")

        ttk.Label(frame, text="Trials:", font=("", 11, "bold")).grid(
            row=0, column=1, padx=(30, 5), sticky="e"
        )
        trials_entry = ttk.Entry(frame, textvariable=self.n_trials_var, width=7)
        trials_entry.grid(row=0, column=2, padx=5, pady=5, sticky="ew")
        self.all_entries.append(trials_entry)

        ttk.Button(
            frame, text="How Simulator Works", command=self.show_simulator_info
        ).grid(row=0, column=3, padx=12, pady=5, sticky="ew")

        self.sim_stop_button = ttk.Button(frame, text="Stop", state="disabled")
        self.sim_stop_button.grid(row=1, column=0, padx=12, pady=4, sticky="ew")

        self.sim_progress = ttk.Progressbar(
            frame, orient="horizontal", mode="determinate"
        )
        self.sim_progress.grid(row=1, column=1, columnspan=3, sticky="ew", padx=12, pady=4)

        frame.configure(relief="sunken")
        frame.configure(
            font="-family {Times New Roman} -size 12 -weight bold -slant italic -underline 1"
        )
        frame.configure(foreground="#249f87")
        frame.configure(text="Simulation Controls")
        frame.configure(background="#3f3f3f")
        frame.configure(highlightbackground="#249f87")
        frame.configure(highlightcolor="#a9ebde")
        frame.configure(highlightthickness="2")
        frame.configure(padx="2")
        frame.configure(pady="2")
        frame.configure(takefocus="2")

    def _build_results(self):
        frame = tk.LabelFrame(self)
        frame.grid(row=3, column=0, columnspan=2, padx=10, pady=(0, 5), sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.sim_tree = ttk.Treeview(
            frame, columns=("Stat", "Value"), show="headings", height=8
        )
        self.sim_tree.heading("Stat", text="Statistic")
        self.sim_tree.heading("Value", text="Value")
        self.sim_tree.column("Stat", width=200, anchor="w")
        self.sim_tree.column("Value", width=150, anchor="center")
        self.sim_tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.sim_tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.sim_tree.configure(yscrollcommand=scrollbar.set)

        frame.configure(relief="sunken")
        frame.configure(
            font="-family {Times New Roman} -size 12 -weight bold -slant italic -underline 1"
        )
        frame.configure(foreground="#249f87")
        frame.configure(text="Simulation Results")
        frame.configure(background="#3f3f3f")
        frame.configure(highlightbackground="#249f87")
        frame.configure(highlightcolor="#a9ebde")
        frame.configure(highlightthickness="2")
        frame.configure(padx="2")
        frame.configure(pady="2")
        frame.configure(takefocus="2")

    def _copy_to_clipboard(self, text):
        if text and "Invalid" not in text:
            self.clipboard_clear()
            self.clipboard_append(text)

    def calculate_values(self, *args):
        try:
            balance = float(self.balance_var.get())
            w = float(self.w_var.get()) / 100.0
            l = int(self.l_var.get())
            bet_div = float(self.bet_div_var.get())
            profit_mult = float(self.profit_mult_var.get())
            buffer = 1 + (float(self.buffer_var.get()) / 100.0)

            m = ((1 + w) * l) * buffer
            bet_size = balance / bet_div
            profit_stop = bet_size * profit_mult
            balance_target = balance + profit_stop

            self.multiplier_var.set(f"{m:.2f}x")
            self.bet_size_var.set(f"{bet_size:.4f}")
            self.profit_stop_var.set(f"{profit_stop:.2f}")
            self.balance_target_var.set(f"{balance_target:.2f}")
        except Exception:
            for var in [
                self.multiplier_var,
                self.bet_size_var,
                self.profit_stop_var,
                self.balance_target_var,
            ]:
                var.set("Invalid")

    def right_click_menu(self, event, entry):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Paste",
            command=lambda: entry.insert(tk.INSERT, self.clipboard_get()),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def show_simulator_info(self):
        messagebox.showinfo(
            "How The Simulator Works",
            "How The Simulator Works\n\n"
            "1.) All values from the parameters and calculated values\n"
            "sections are used in the simulation.\n\n"
            "2.) Each time the profit stop is met, the cycle ends and counts\n"
            "as a successful cycle.\n\n"
            "3.) Next cycle begins using the ending balance from previous\n"
            "cycle until bust.\n\n"
            "4.) Each trial ends when balance hits 0.\n\n"
            "5.) Successful cycles are the cycles that reached the profit\n"
            "stop.",
        )

    def show_getting_started_info(self):
        messagebox.showinfo(
            "How To Setup",
            "How To Set Up\n\n"
            "STEP 1:\n"
            "In your dice game, make a new advanced strategy with the\n"
            "following conditions:\n"
            "1.) On every 1 win increase bet amount by 'Win Increase %'\n"
            "2.) On every streak of 'Loss Reset' losses, reset bet amount\n"
            "3.) On greater than or equal to 'Profit Stop' profit/net gain,\n"
            "Stop autoplay\n\n"
            "STEP 2:\n"
            "Enter your starting balance and the remaining parameters.\n"
            "This will populate the calculated values section, where you\n"
            "will copy the Bet Size and Profit Stop into your game.\n\n"
            "STEP 3:\n"
            "When Profit Stop is met, update your balance Balance and\n"
            "repeat the process.",
        )

    def get_sim_params(self) -> SimParams:
        return SimParams(
            starting_balance=float(self.balance_var.get()),
            bet_div=float(self.bet_div_var.get()),
            profit_mult=float(self.profit_mult_var.get()),
            w=float(self.w_var.get()) / 100.0,
            l=int(self.l_var.get()),
            buffer=1 + float(self.buffer_var.get()) / 100.0,
            n_trials=int(self.n_trials_var.get()),
        )

    def display_sim_results(self, stats: List[Tuple[str, str]]):
        for item in self.sim_tree.get_children():
            self.sim_tree.delete(item)
        for stat, value in stats:
            self.sim_tree.insert("", "end", values=(stat, value))

    def toggle_server(self):
        if self.server:
            self.shutdown_server()
            self.start_server_btn.config(text="Start Local Server")
            messagebox.showinfo("Server Stopped", "Local server has been stopped.")
        else:
            self.start_local_server()
            self.start_server_btn.config(text="Stop Local Server")
            messagebox.showinfo("Server Started", "Local server started at http://localhost:8000")

    def start_local_server(self):
        handler_class = make_handler(self)
        self.server = HTTPServer(('localhost', 8000), handler_class)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def shutdown_server(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.server_thread.join()
            self.server = None
            self.server_thread = None