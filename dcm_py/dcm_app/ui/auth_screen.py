import tkinter as tk
from tkinter import ttk, messagebox


class AuthScreen(ttk.Frame):
    """Login / registration screen (max 10 users)."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.username_var = tk.StringVar()
        self.password_var = tk.StringVar()

        self._build()

    def _build(self):
        title = ttk.Label(self, text="Pacemaker DCM - Login / Register", font=("Segoe UI", 18, "bold"))
        title.pack(pady=20)

        form = ttk.Frame(self)
        form.pack(pady=10)

        ttk.Label(form, text="Username:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(form, textvariable=self.username_var, width=30).grid(row=0, column=1, pady=5)

        ttk.Label(form, text="Password:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        ttk.Entry(form, textvariable=self.password_var, width=30, show="*").grid(row=1, column=1, pady=5)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text="Login", command=self._on_login).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Register", command=self._on_register).grid(row=0, column=1, padx=5)

        # note = ttk.Label(
        #     self,
        #     # text="Up to 5 users are stored locally. This DCM is for educational use only.",
        #     foreground="gray"
        # )
        # note.pack(pady=10)

    def _on_login(self):
        u = self.username_var.get().strip()
        p = self.password_var.get().strip()
        if not u or not p:
            messagebox.showerror("Error", "Please enter both username and password.")
            return
        if not self.app.storage.validate_login(u, p):
            messagebox.showerror("Error", "Invalid username or password.")
            return
        self.app.login_success(u)

    def _on_register(self):
        u = self.username_var.get().strip()
        p = self.password_var.get().strip()
        if not u or not p:
            messagebox.showerror("Error", "Please enter both username and password.")
            return
        if not self.app.storage.register_user(u, p):
            messagebox.showerror("Error", "Registration failed (user exists or max users reached).")
            return
        messagebox.showinfo("Registered", "User registered. Logging in.")
        self.app.login_success(u)

    def on_show(self):
        self.username_var.set("")
        self.password_var.set("")
