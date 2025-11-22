# Dice_Tool/ui/main.py
import multiprocessing
import tkinter as tk
from ui.main_window import MergedApp, apply_global_theme

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = MergedApp()
    apply_global_theme(app)
    app.mainloop()
