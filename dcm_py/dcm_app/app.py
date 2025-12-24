# This is the 


import tkinter as tk
from tkinter import ttk, messagebox

from dcm_app.services.storage_service import StorageService
from dcm_app.services.comms_service import CommsService
from dcm_app.services.validation_service import ValidationService
from dcm_app.models.settings import PacemakerSettings
from dcm_app.ui.auth_screen import AuthScreen
from dcm_app.ui.dashboard_screen import DashboardScreen


class DCMApp(tk.Tk):
    """Root Tkinter application for the Pacemaker Device Controller-Monitor."""

    def __init__(self):
        super().__init__()
        self.title("Pacemaker DCM - 3K04")
        self.geometry("1100x700")

        # core services
        self.storage = StorageService()
        self.comms = CommsService()
        self.validator = ValidationService()

        # Logged-in user and current mode
        self.current_user = None  # type: ignore
        self.current_settings = PacemakerSettings.default(owner_username="system", mode="VVI")

        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self._frames = {}
        for F in (AuthScreen, DashboardScreen):
            frame = F(parent=container, app=self)
            self._frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Attempt auto-login if a session exists
        remembered_user = self.storage.get_current_user()
        if remembered_user:
            self.login_success(remembered_user)
        else:
            self.show_frame("AuthScreen")

    def show_frame(self, name: str):
        frame = self._frames.get(name)
        if frame is None:
            messagebox.showerror("Error", f"Unknown screen: {name}")
            return
        frame.tkraise()
        if hasattr(frame, "on_show"):
            frame.on_show()

    def login_success(self, username: str):
        self.current_user = username
        # Persist session
        self.storage.set_current_user(username)
        # Load last settings for this user if present
        settings = self.storage.load_settings(username)
        if settings:
            self.current_settings = settings
        else:
            # Create fresh default settings for new user
            self.current_settings = PacemakerSettings.default(owner_username=username, mode="VVI")
        self.show_frame("DashboardScreen")

    def run(self):
        self.mainloop()
