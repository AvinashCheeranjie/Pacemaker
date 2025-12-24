import tkinter as tk
from tkinter import ttk, messagebox
import queue

from dcm_app.ui.mode_config_screen import ModeConfigFrame
from dcm_app.ui.egram_screen import EgramFrame


class DashboardScreen(ttk.Frame):
    """Main dashboard with tabs for modes/parameters and egram display."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.egram_queue = queue.Queue()
        self.app.comms.attach_egram_queue(self.egram_queue)

        self._build()

    def _build(self):
        top_bar = ttk.Frame(self)
        top_bar.pack(fill="x", pady=5)

        # User label
        self.user_label = ttk.Label(top_bar, text="User: -")
        self.user_label.pack(side="left", padx=10)

        # Connection status label
        self.conn_label = ttk.Label(top_bar, text="Connection: Disconnected", foreground="red")
        self.conn_label.pack(side="left", padx=10)

        # --- COM port controls ---
        port_frame = ttk.Frame(top_bar)
        port_frame.pack(side="left", padx=10)

        ttk.Label(port_frame, text="Port:").pack(side="left")

        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(
            port_frame,
            textvariable=self.port_var,
            width=12,
            state="readonly",
            values=[],
        )
        self.port_combo.pack(side="left", padx=(4, 4))

        ttk.Button(port_frame, text="Refresh", command=self._refresh_ports).pack(side="left", padx=(0, 4))
        ttk.Button(port_frame, text="Connect", command=self._on_connect).pack(side="left", padx=(0, 4))
        ttk.Button(port_frame, text="Test", command=self._on_test_connection).pack(side="left")

        # Right side: Disconnect + Logout
        ttk.Button(top_bar, text="Disconnect", command=self._on_disconnect).pack(side="right", padx=5)
        ttk.Button(top_bar, text="Logout", command=self._on_logout).pack(side="right", padx=5)

        # Main notebook (tabs)
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, pady=10, padx=10)

        self.mode_frame = ModeConfigFrame(notebook, self.app)
        self.egram_frame = EgramFrame(notebook, self.app, self.egram_queue)

        notebook.add(self.mode_frame, text="Modes & Parameters")
        notebook.add(self.egram_frame, text="Egrams")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_show(self):
        user = self.app.current_user or "-"
        self.user_label.config(text=f"User: {user}")

        self._refresh_ports()

        if self.app.comms.is_connected:
            port = self.app.comms.current_port or "Unknown"
            self.conn_label.config(text=f"Connection: {port}", foreground="green")
        else:
            self.conn_label.config(text="Connection: Disconnected", foreground="red")

        self.mode_frame.refresh_from_settings()

    # ------------------------------------------------------------------
    # UI callbacks
    # ------------------------------------------------------------------
    def _on_logout(self):
        self.app.current_user = None
        # Clear persisted session
        try:
            self.app.storage.set_current_user(None)
        except Exception:
            pass
        self.app.show_frame("AuthScreen")

    def _on_disconnect(self):
        self.app.comms.disconnect()
        messagebox.showinfo("Disconnected", "Disconnected from device.")
        self.conn_label.config(text="Connection: Disconnected", foreground="red")

    def _refresh_ports(self):
        """Ask CommsService for available ports and repopulate the combobox."""
        ports = self.app.comms.list_ports()
        self.port_combo["values"] = ports

        if ports:
            current = self.app.comms.current_port
            if current in ports:
                self.port_var.set(current)
            else:
                self.port_var.set(ports[0])
        else:
            self.port_var.set("")

    def _on_connect(self):
        """Connect to the selected COM port via CommsService."""
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("No Port Selected", "Please select a serial port first.")
            return

        success, error = self.app.comms.connect(port)

        if success:
            self.conn_label.config(text=f"Connection: {port}", foreground="green")
            messagebox.showinfo("Connected", f"Successfully connected to {port}.")
            # Optional: start egram streaming automatically
            # self.app.comms.start_egram_stream()
        else:
            self.conn_label.config(text="Connection: Error", foreground="red")
            messagebox.showerror("Connection Failed", error or f"Failed to connect to {port}.")

    def _on_test_connection(self):
        """
        Verify that the serial port the DCM thinks it's connected to
        is actually open and responsive at the OS/driver level.
        """
        if not self.app.comms.is_connected:
            messagebox.showwarning(
                "Not Connected",
                "No open serial connection. Please connect to a port first."
            )
            return

        ok, msg = self.app.comms.test_connection()
        port = self.app.comms.current_port or "Unknown"

        if ok:
            self.conn_label.config(text=f"Connection: {port} (OK)", foreground="green")
            messagebox.showinfo("Connection Test", msg)
        else:
            self.conn_label.config(text=f"Connection: {port} (Error)", foreground="red")
            messagebox.showerror("Connection Test Failed", msg)
