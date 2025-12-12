# Dice_Tool/ui/settings_tab.py
import tkinter as tk
from tkinter import ttk

class SettingsTab(ttk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.setting_labels = []

        # Main layout container - limits width to keep things readable
        # instead of stretching across the whole 1100px window
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        center_frame = ttk.Frame(self)
        center_frame.grid(row=0, column=0, sticky="n", pady=30)
        center_frame.columnconfigure(0, minsize=400) # Minimum width for settings block

        # --- Appearance Section ---
        app_frame = ttk.LabelFrame(center_frame, text=" Interface Appearance ", padding=(20, 10))
        app_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))
        app_frame.columnconfigure(1, weight=1) # Push controls to the right

        # Theme Selector
        lbl_theme = ttk.Label(app_frame, text="Color Theme", font=("Segoe UI", 10, "bold"))
        lbl_theme.grid(row=0, column=0, sticky="w", pady=10)
        self.setting_labels.append(lbl_theme)

        theme_combo = ttk.Combobox(
            app_frame, 
            textvariable=self.app.current_theme,
            values=list(self.app.THEMES.keys()),
            state="readonly",
            width=18
        )
        theme_combo.grid(row=0, column=1, sticky="e", padx=5, pady=10)
        theme_combo.bind("<<ComboboxSelected>>", 
                         lambda e: self.app.apply_theme(self.app.current_theme.get()))

        # Separator
        ttk.Separator(app_frame, orient="horizontal").grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=5
        )

        # Large Fonts
        lbl_font = ttk.Label(app_frame, text="Large Fonts Mode (+4pt)", font=("Segoe UI", 10, "bold"))
        lbl_font.grid(row=2, column=0, sticky="w", pady=10)
        self.setting_labels.append(lbl_font)

        # Checkbutton with immediate apply
        font_chk = ttk.Checkbutton(
            app_frame, 
            variable=self.app.large_fonts,
            command=lambda: self.app.apply_theme(self.app.current_theme.get())
        )
        font_chk.grid(row=2, column=1, sticky="e", padx=5, pady=10)

        # --- Optimizer Section ---
        opt_frame = ttk.LabelFrame(center_frame, text=" Optimizer Behavior ", padding=(20, 10))
        opt_frame.grid(row=1, column=0, sticky="ew")
        opt_frame.columnconfigure(1, weight=1)

        # Keep Results
        lbl_res = ttk.Label(opt_frame, text="Append Results", font=("Segoe UI", 10, "bold"))
        lbl_res.grid(row=0, column=0, sticky="w", pady=(10, 0))
        self.setting_labels.append(lbl_res)

        res_chk = ttk.Checkbutton(opt_frame, variable=self.app.keep_previous_results)
        res_chk.grid(row=0, column=1, sticky="e", padx=5, pady=(10, 0))

        # Description text (smaller, italic)
        desc_lbl = ttk.Label(
            opt_frame, 
            text="If checked, new optimization runs will be added to the\nexisting table instead of clearing it.",
            font=("Segoe UI", 9, "italic"),
            foreground="gray" # Note: Theme might override this, which is fine
        )
        desc_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 10))

    def update_fonts(self, base_size: int):
        """Called by main_window to resize manual font definitions"""
        # Update the bold labels
        label_size = base_size + 1
        for lbl in self.setting_labels:
            lbl.configure(font=("Segoe UI", label_size, "bold"))