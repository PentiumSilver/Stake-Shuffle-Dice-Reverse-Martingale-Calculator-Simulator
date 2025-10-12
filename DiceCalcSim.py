import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import hashlib
import struct
import secrets

# -----------------------------
# Tooltip Helper Class
# -----------------------------
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
        x, y, cx, cy = self.widget.bbox("insert")
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify='left',
            background="#ffffe0",
            relief='solid',
            borderwidth=1,
            wraplength=300,
            font=("Segoe UI", 9)
        )
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

# -----------------------------
# Core Simulation Logic
# -----------------------------
def sha256_roll(server_seed, client_seed, nonce):
    msg = f"{server_seed}:{client_seed}:{nonce}".encode()
    h = hashlib.sha256(msg).digest()
    int_val = struct.unpack('>I', h[:4])[0]
    return int_val / 2**32

def run_compounded_trial(starting_balance, bet_div, profit_mult, w, l, buffer, server_seed, client_seed):
    balance = starting_balance
    highest_balance = balance
    cycles = 0
    rounds = 0
    nonce = 0
    peak = balance
    while balance > 0:
        bet = balance / bet_div
        profit_stop = bet * profit_mult
        target = balance + profit_stop
        m = ((1 + w) * l) * buffer
        win_chance = (1 - 0.01) / m

        current_bet = bet
        loss_streak = 0
        while balance > 0 and balance < target:
            roll = sha256_roll(server_seed, client_seed, nonce)
            nonce += 1
            rounds += 1
            if roll < win_chance:
                profit = current_bet * (m - 1)
                balance += profit
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

def run_many_trials(n_trials, starting_balance, bet_div, profit_mult, w, l, buffer):
    results = []
    for i in range(n_trials):
        server_seed = secrets.token_hex(32)
        client_seed = secrets.token_hex(32)
        result = run_compounded_trial(starting_balance, bet_div, profit_mult, w, l, buffer, server_seed, client_seed)
        results.append(result)
    return results

# -----------------------------
# GUI Class
# -----------------------------
class DiceStrategyGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Dice Simulator/Calculator")
        self.geometry("750x670")
        self.resizable(False, False)

        # -----------------------------
        # Parameters Section
        # -----------------------------
        input_frame = ttk.LabelFrame(self, text="Parameters")
        input_frame.place(x=15, y=10, width=720, height=110)

        # Balance
        ttk.Label(input_frame, text="Balance:").place(x=10, y=10)
        self.balance_var = tk.StringVar(value="0")
        balance_entry = ttk.Entry(input_frame, textvariable=self.balance_var, width=10)
        balance_entry.place(x=120, y=10)
        self.add_help_icon(input_frame, 185, 10, "Enter your current balance here.")

        # Win Increase %
        ttk.Label(input_frame, text="Win Increase %:").place(x=10, y=40)
        self.w_var = tk.StringVar(value="0")
        w_entry = ttk.Entry(input_frame, textvariable=self.w_var, width=10)
        w_entry.place(x=120, y=40)
        self.add_help_icon(input_frame, 185, 40, "The percentage your bet increases after a win.")

        # Loss Reset
        ttk.Label(input_frame, text="Loss Reset:").place(x=10, y=70)
        self.l_var = tk.StringVar(value="0")
        l_entry = ttk.Entry(input_frame, textvariable=self.l_var, width=10)
        l_entry.place(x=120, y=70)
        self.add_help_icon(input_frame, 185, 70, "Number of consecutive losses before resetting the bet to base value.")

        # Balance Divisor
        ttk.Label(input_frame, text="Balance Divisor:").place(x=300, y=10)
        self.bet_div_var = tk.StringVar(value="0")
        bet_div_entry = ttk.Entry(input_frame, textvariable=self.bet_div_var, width=10)
        bet_div_entry.place(x=420, y=10)
        self.add_help_icon(input_frame, 485, 10, "Your balance will be divided by this number to determine bet size.")

        # Profit Multiplier
        ttk.Label(input_frame, text="Profit Multiplier:").place(x=300, y=40)
        self.profit_mult_var = tk.StringVar(value="0")
        profit_mult_entry = ttk.Entry(input_frame, textvariable=self.profit_mult_var, width=10)
        profit_mult_entry.place(x=420, y=40)
        self.add_help_icon(input_frame, 485, 40, "Your bet size will be multiplied by this number to determine profit stop.")

        # Buffer
        ttk.Label(input_frame, text="Buffer (%):").place(x=300, y=70)
        self.buffer_var = tk.StringVar(value="0")
        buffer_entry = ttk.Entry(input_frame, textvariable=self.buffer_var, width=10)
        buffer_entry.place(x=420, y=70)
        self.add_help_icon(input_frame, 485, 70, "Boosts the calculated multiplier to help ensure the balance remains higher than the starting balance after a full win/loss/reset cycle.\n\nSetting this to 0 means breaking even through any win/loss/reset cycle.")

        # --- NEW BUTTON LOCATION ---
        # Click Me To Get Started Button (In the red rectangle location)
        click_me_button = ttk.Button(input_frame, text="Click Me To Get Started", command=self.show_getting_started_info)
        click_me_button.place(x=520, y=38, width=180, height=30)
        # --- END NEW BUTTON LOCATION ---

        # -----------------------------
        # Calculated Values Section (Symmetrical Layout)
        # -----------------------------
        values_frame = ttk.LabelFrame(self, text="Calculated Values")
        values_frame.place(x=15, y=130, width=720, height=80)

        self.multiplier_var = tk.StringVar()
        self.bet_size_var = tk.StringVar()
        self.profit_stop_var = tk.StringVar()
        self.balance_target_var = tk.StringVar()

        # Multiplier
        ttk.Label(values_frame, text="Multiplier:").place(x=10, y=10)
        ttk.Label(values_frame, textvariable=self.multiplier_var, font=('Arial', 10, 'bold')).place(x=120, y=10)

        # Bet Size
        ttk.Label(values_frame, text="Bet Size:").place(x=10, y=40)
        ttk.Label(values_frame, textvariable=self.bet_size_var, font=('Arial', 10, 'bold')).place(x=120, y=40)
        self.bet_copy_check = ttk.Label(values_frame, text="", foreground="green")
        ttk.Button(values_frame, text="Copy", width=6, command=lambda: self.copy_with_check(self.bet_size_var.get(), self.bet_copy_check)).place(x=220, y=37)
        self.bet_copy_check.place(x=275, y=40)
        
        # Profit Stop
        ttk.Label(values_frame, text="Profit Stop:").place(x=300, y=10)
        ttk.Label(values_frame, textvariable=self.profit_stop_var, font=('Arial', 10, 'bold')).place(x=420, y=10)
        self.profit_copy_check = ttk.Label(values_frame, text="", foreground="green")
        ttk.Button(values_frame, text="Copy", width=6, command=lambda: self.copy_with_check(self.profit_stop_var.get(), self.profit_copy_check)).place(x=520, y=7)
        self.profit_copy_check.place(x=575, y=10)

        # Balance Target
        ttk.Label(values_frame, text="Balance Target:").place(x=300, y=40)
        ttk.Label(values_frame, textvariable=self.balance_target_var, font=('Arial', 10, 'bold')).place(x=420, y=40)
        self.target_copy_check = ttk.Label(values_frame, text="", foreground="green")
        ttk.Button(values_frame, text="Copy", width=6, command=lambda: self.copy_with_check(self.balance_target_var.get(), self.target_copy_check)).place(x=520, y=37)
        self.target_copy_check.place(x=575, y=40)

        # -----------------------------
        # Simulation Controls Section
        # -----------------------------
        sim_control_frame = ttk.LabelFrame(self, text="Simulation Controls")
        sim_control_frame.place(x=15, y=220, width=720, height=70)

        # How It Works Button 
        how_it_works_button = ttk.Button(sim_control_frame, text="How Simulations Work", command=self.show_simulator_info)
        how_it_works_button.place(x=10, y=12, width=180, height=30)
        
        # Trials
        ttk.Label(sim_control_frame, text="Trials:").place(x=205, y=15)
        self.n_trials_var = tk.StringVar(value="0")
        n_trials_entry = ttk.Entry(sim_control_frame, textvariable=self.n_trials_var, width=10)
        n_trials_entry.place(x=255, y=15)

        # Run Simulation Button
        run_button = ttk.Button(sim_control_frame, text="Run Simulation", command=self.run_simulation)
        run_button.place(x=365, y=12, width=120, height=30)
        
        # Bind paste and right-click to all entry fields
        all_entries = [balance_entry, w_entry, l_entry, bet_div_entry, profit_mult_entry, buffer_entry, n_trials_entry]
        for entry in all_entries:
            entry.bind('<Control-v>', lambda event, e=entry: self.paste_to_entry(event, e))
            entry.bind('<Button-3>', lambda event, e=entry: self.right_click_menu(event, e))

        # -----------------------------
        # Simulation Results
        # -----------------------------
        output_frame = ttk.LabelFrame(self, text="Simulation Results")
        output_frame.place(x=15, y=300, width=720, height=350)

        self.tree = ttk.Treeview(output_frame, columns=("stat", "value"), show='headings', height=15)
        self.tree.heading("stat", text="Statistic")
        self.tree.heading("value", text="Value")
        self.tree.column("stat", width=320)
        self.tree.column("value", width=320)
        self.tree.place(x=5, y=5)

        scrollbar = ttk.Scrollbar(output_frame, orient="vertical", command=self.tree.yview)
        scrollbar.place(x=670, y=5, height=325)
        self.tree.configure(yscrollcommand=scrollbar.set)

        for var in [self.balance_var, self.w_var, self.l_var, self.bet_div_var, self.profit_mult_var, self.buffer_var]:
            var.trace_add('write', lambda *args: self.calculate_values())

        self.calculate_values()

    # -----------------------------
    # Helper Functions
    # -----------------------------
    def add_help_icon(self, parent, x, y, text):
        label = tk.Label(parent, text="?", font=('Segoe UI', 8, 'bold'), fg="#777", cursor="question_arrow")
        label.place(x=x, y=y+2)
        ToolTip(label, text)

    def copy_with_check(self, value, check_label):
        if not value or value == "Invalid": return
        self.clipboard_clear()
        self.clipboard_append(value)
        check_label.config(text="✅")
        check_label.after(1000, lambda: check_label.config(text=""))

    def paste_to_entry(self, event, entry):
        try:
            entry.insert(tk.INSERT, self.clipboard_get())
        except tk.TclError:
            pass
        return "break"

    def right_click_menu(self, event, entry):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Paste", command=lambda e=entry: e.insert(tk.INSERT, self.clipboard_get()))
        menu.tk_popup(event.x_root, event.y_root)

    # -----------------------------
    # Calculation + Simulation
    # -----------------------------
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

        self.multiplier_var.set(f"{m:.4f}x")
        self.bet_size_var.set(f"{bet_size:.8f}")
        self.profit_stop_var.set(f"{profit_stop:.8f}")
        self.balance_target_var.set(f"{balance_target:.8f}")

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

        results = run_many_trials(n_trials, starting_balance, bet_div, profit_mult, w, l, buffer)
        df = pd.DataFrame(results)

        highest_balances = df["highest_balance"]
        cycles = df["cycles"]
        rounds = df["rounds"]
        stats = [
            ("Average highest balance", f"${highest_balances.mean():.2f}"),
            ("Std dev (highest)", f"${highest_balances.std():.2f}"),
            ("Max highest balance", f"${highest_balances.max():.2f}"),
            ("% trials > $100", f"{(highest_balances > 100).mean()*100:.1f}%"),
            ("% trials > $500", f"{(highest_balances > 500).mean()*100:.1f}%"),
            ("% trials > $1000", f"{(highest_balances > 1000).mean()*100:.1f}%"),
            ("Average cycles", f"{cycles.mean():.2f}"),
            ("Average rounds", f"{rounds.mean():.2f}"),
        ]

        for i in self.tree.get_children():
            self.tree.delete(i)
        for stat, val in stats:
            self.tree.insert("", "end", values=(stat, val))

    def show_simulator_info(self):
        """Displays a message box explaining the simulation process (Original 'How It Works')."""
        info_text = (
            "1.) All values from the parameters section, and calculated values section, are used in the simulation. \n\n"
            "2.) The simulation will start with your balance, bet size, and profit stop.\n\n"
            "3.) Each time the profit stop is met, the cycle ends, and is counted as one successful cycle.\n\n"
            "4.) The next cycle will begin using the ending balance from the previous cycle. The new bet size, and profit stop values will be calculated, and also used.\n\n"
            "5.) This process will continue until the strategy finally busts, and the balance hits 0.\n\n"
            "6.) Each time the balance hits 0 and the profit stop is NOT met, will be counted as one unsuccessful cycle.\n\n"
            "7.) Each trial is concluded when the balance hits 0."
        )
        messagebox.showinfo("How The Simulator Works", info_text)

    def show_getting_started_info(self):
        """Displays a message box with the four-step 'Click Me To Get Started' instructions."""
        info_text = (
            "STEP 1:\n\n"
            "Create a new dice strategy with the following conditions:\n\n"
            "Condition 1.) On Every 1 Wins  ->  Increase bet amount \"__\" %    (Enter the \"Win Increase %\")\n\n"
            "Condition 2.) On Every streak of \"_\" Losses  ->  Reset bet amount    (Enter the \"Loss Reset\")\n\n"
            "Condition 3.) On Greater than or equal to \"__.__\"  Net Gain/Profit  ->  Stop autoplay    (Copy the \"Profit Stop\" and paste into this condition)\n\n\n"

            "STEP 2:\n\n"
            "1.) Enter your starting balance into the \"Balance\" box\n\n"
            "2.) Enter values into the 5 remaining boxes. You can hover your mouse over the \"?\" to better understand each parameter\n\n"
            "3.) Enter the multiplier from the Calculated Values section into your dice game\n\n"
            "4.) Copy the \"Bet Size\" from the Calculated Values section, and paste it as your bet amount\n\n"
            "5.) Copy the \"Profit Stop\" from the Calculated Values section, and paste it into Condition 3\n\n"
            "6.) Start autoplay\n\n\n"

            "STEP 3:\n\n"
            "1.) Once the \"Profit Stop\" is met, and the autoplay has stopped, enter your NEW balance into the \"Balance\" box\n\n"
            "2.) Copy the NEW \"Bet Size\" from the Calculated Values section, and paste it as your NEW bet amount**\n\n"
            "3.) Copy the NEW \"Profit Stop\" from the Calculated Values section, and update Condition 3\n\n"
            "4.) Start autoplay\n\n\n"

            "STEP 4:\n\n"
            "1.) Repeat \"STEP 3\""
        )
        messagebox.showinfo("Click Me To Get Started", info_text)


if __name__ == "__main__":
    app = DiceStrategyGUI()
    app.mainloop()