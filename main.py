import multiprocessing
import sys
import os
import tkinter as tk
from ui.main_window import MergedApp

def try_load_azure_theme(app: tk.Tk, mode: str = "light") -> bool:
    """
    Try to source an azure.tcl file into the given Tk app's interpreter and set the requested mode.
    Returns True if a file was found and sourced without raising an error.
    """
    candidates = [
        os.path.join(os.path.dirname(__file__), "azure.tcl"),
        os.path.join(os.path.dirname(__file__), "ui", "azure.tcl"),
        os.path.join(os.getcwd(), "azure.tcl"),
        os.path.join(os.getcwd(), "ui", "azure.tcl"),
    ]
    if getattr(sys, '_MEIPASS', None):
        candidates.insert(0, os.path.join(sys._MEIPASS, "azure.tcl"))
    for path in candidates:
        if os.path.exists(path):
            try:
                app.tk.call("source", path)
                # set_theme is provided by the azure.tcl script; wrap in try in case it isn't present
                try:
                    app.tk.call("set_theme", mode)
                except tk.TclError:
                    pass
                return True
            except tk.TclError:
                # If sourcing failed, continue to other candidates
                continue
    return False

if __name__ == "__main__":
    multiprocessing.freeze_support()
    # Create the real application first (we must source theme into this interpreter).
    app = MergedApp()

    # Attempt to load an Azure theme file if available, default to light.
    try_load_azure_theme(app, mode="light")

    app.mainloop()