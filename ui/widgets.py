# Dice_Tool/ui/widgets.py
import tkinter as tk
from typing import Optional

TIP_BACKGROUND = "#EEEECD"
TIP_FONT = ("Segoe UI", 9)
TIP_WRAPLENGTH = 300

class ToolTip:
    """A simple tooltip widget for displaying help text on hover."""

    def __init__(self, widget: tk.Widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window: Optional[tk.Toplevel] = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event: Optional[tk.Event] = None) -> None:
        """Shows the tooltip window."""
        if self.tip_window or not self.text:
            return
        try:
            x, y, _, _ = self.widget.bbox("insert")
        except Exception:
            x, y = 0, 0
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, background=TIP_BACKGROUND,
                         relief='solid', borderwidth=1, wraplength=TIP_WRAPLENGTH, font=TIP_FONT)
        label.pack(ipadx=1)
        self.tip_window = tw

    def hide_tip(self, event: Optional[tk.Event] = None) -> None:
        """Hides the tooltip window."""
        tw = self.tip_window
        self.tip_window = None
        if tw:
            tw.destroy()

