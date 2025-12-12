# Dice_Tool/ui/main.py
import multiprocessing
import tkinter as tk
from ui.main_window import MergedApp  # removed apply_global_theme import

if __name__ == "__main__":
    multiprocessing.freeze_support()
    app = MergedApp()
    app.apply_theme("Original")  # apply default theme
    app.mainloop()