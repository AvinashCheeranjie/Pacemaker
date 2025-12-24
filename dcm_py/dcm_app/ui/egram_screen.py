import tkinter as tk
from tkinter import ttk

from dcm_app.models.egram import EgramSample


class EgramFrame(ttk.Frame):
    """Simple real-time egram plot for A/V or both using Canvas."""

    def __init__(self, parent, app, egram_queue):
        super().__init__(parent)
        self.app = app
        self.queue = egram_queue

        self.chamber_var = tk.StringVar(value="both")

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=5)

        ttk.Label(controls, text="Chamber:").pack(side="left", padx=5)
        ttk.Radiobutton(controls, text="A", variable=self.chamber_var, value="A",
                        command=self._on_chamber_change).pack(side="left")
        ttk.Radiobutton(controls, text="V", variable=self.chamber_var, value="V",
                        command=self._on_chamber_change).pack(side="left")
        ttk.Radiobutton(controls, text="Both", variable=self.chamber_var, value="both",
                        command=self._on_chamber_change).pack(side="left")

        ttk.Button(controls, text="Start", command=self._on_start).pack(side="left", padx=5)
        ttk.Button(controls, text="Stop", command=self._on_stop).pack(side="left", padx=5)

        self.canvas = tk.Canvas(self, bg="black", height=300)
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

        self.samples_A = []
        self.samples_V = []

        self.after(50, self._update_canvas)

    def _on_chamber_change(self):
        self.app.comms.start_egram_stream(self.chamber_var.get())

    def _on_start(self):
        self.app.comms.start_egram_stream(self.chamber_var.get())

    def _on_stop(self):
        self.app.comms.stop_egram_stream()

    def _update_canvas(self):
        # Drain queue
        try:
            while True:
                sample: EgramSample = self.queue.get_nowait()
                if sample.chamber == "A":
                    self.samples_A.append(sample.value_mv)
                else:
                    self.samples_V.append(sample.value_mv)
        except Exception:
            pass

        # Limit length
        max_len = 200
        self.samples_A = self.samples_A[-max_len:]
        self.samples_V = self.samples_V[-max_len:]

        self.canvas.delete("all")
        w = int(self.canvas.winfo_width())
        h = int(self.canvas.winfo_height())
        mid = h // 2

        def draw_series(series, offset, color):
            if len(series) < 2:
                return
            scale = h / 4 or 1
            step = max(1, int(w / max_len))
            points = []
            for i, val in enumerate(series):
                x = i * step
                y = mid + offset - int(val * scale)
                points.append((x, y))
            for (x1, y1), (x2, y2) in zip(points[:-1], points[1:]):
                self.canvas.create_line(x1, y1, x2, y2, fill=color)

        if self.chamber_var.get() in ("A", "both"):
            draw_series(self.samples_A, -50, "green")
        if self.chamber_var.get() in ("V", "both"):
            draw_series(self.samples_V, 50, "cyan")

        self.after(50, self._update_canvas)
