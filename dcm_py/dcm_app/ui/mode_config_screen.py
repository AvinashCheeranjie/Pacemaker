import tkinter as tk
from tkinter import ttk, messagebox

from dcm_app.models.settings import PacemakerSettings


SUPPORTED_MODES = [
    "AOO", "VOO", "AAI", "VVI",
    "AOOR", "VOOR", "AAIR", "VVIR",
    "DDD", "DDDR"
]


class ModeConfigFrame(ttk.Frame):
    """Mode selection + full parameter configuration."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        self.mode_var = tk.StringVar(value=self.app.current_settings.mode)

        # Basic vars
        self.basic_vars = {
            "lower_rate_limit": tk.StringVar(),
            "upper_rate_limit": tk.StringVar(),
            "maximum_sensor_rate": tk.StringVar(),
            "atrial_amplitude": tk.StringVar(),
            "atrial_pulse_width": tk.StringVar(),
            "ventricular_amplitude": tk.StringVar(),
            "ventricular_pulse_width": tk.StringVar(),
            "ventricular_refractory_period": tk.StringVar(),
            "atrial_refractory_period": tk.StringVar(),
            "pvarp": tk.StringVar(),
            "atrial_sensitivity": tk.StringVar(),
            "ventricular_sensitivity": tk.StringVar(),
        }

        # Advanced vars
        self.fixed_av_delay = tk.StringVar()
        self.dynamic_av_delay_on = tk.BooleanVar()
        self.min_dynamic_av_delay = tk.StringVar()
        self.sensed_av_delay_offset = tk.StringVar()
        self.pvarp_extension = tk.StringVar()
        self.hysteresis_rate_limit = tk.StringVar()
        self.rate_smoothing_percent = tk.StringVar()
        self.atr_mode_on = tk.BooleanVar()
        self.atr_duration = tk.StringVar()
        self.atr_fallback_time = tk.StringVar()
        self.ventricular_blanking = tk.StringVar()
        self.activity_threshold = tk.StringVar()
        self.reaction_time = tk.StringVar()
        self.response_factor = tk.StringVar()
        self.recovery_time = tk.StringVar()

        self._build()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=5)

        ttk.Label(top, text="Pacing Mode:").pack(side="left", padx=5)
        mode_box = ttk.Combobox(top, textvariable=self.mode_var, values=SUPPORTED_MODES, width=10, state="readonly")
        mode_box.pack(side="left", padx=5)

        ttk.Button(top, text="Apply to DCM", command=self._on_apply).pack(side="left", padx=10)
        ttk.Button(top, text="Send to Device", command=self._on_send).pack(side="left", padx=5)
        ttk.Button(top, text="Read & Verify", command=self._on_verify).pack(side="left", padx=5)
        ttk.Button(top, text="UART Loopback Test", command=self._on_uart_test).pack(side="left", padx=5)
        
        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        left = ttk.LabelFrame(main, text="Basic Parameters")
        right = ttk.LabelFrame(main, text="Advanced Timing & Rate Response")
        left.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        right.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        # Basic grid
        row = 0
        for label, key in [
            ("Lower Rate Limit (ppm)", "lower_rate_limit"),
            ("Upper Rate Limit (ppm)", "upper_rate_limit"),
            ("Max Sensor Rate (ppm)", "maximum_sensor_rate"),
            ("Atrial Amplitude (V)", "atrial_amplitude"),
            ("Atrial Pulse Width (ms)", "atrial_pulse_width"),
            ("Ventricular Amplitude (V)", "ventricular_amplitude"),
            ("Ventricular Pulse Width (ms)", "ventricular_pulse_width"),
            ("VRP (ms)", "ventricular_refractory_period"),
            ("ARP (ms)", "atrial_refractory_period"),
            ("PVARP (ms)", "pvarp"),
            ("Atrial Sensitivity (mV)", "atrial_sensitivity"),
            ("Ventricular Sensitivity (mV)", "ventricular_sensitivity"),
        ]:
            ttk.Label(left, text=label).grid(row=row, column=0, sticky="e", padx=4, pady=2)
            ttk.Entry(left, textvariable=self.basic_vars[key], width=12).grid(row=row, column=1, padx=4, pady=2)
            row += 1

        # Advanced fields
        row = 0
        def add_adv(label, var, col_span=1, widget_type="entry", values=None):
            nonlocal row
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="e", padx=4, pady=2)
            if widget_type == "entry":
                ttk.Entry(right, textvariable=var, width=12).grid(row=row, column=1, padx=4, pady=2, columnspan=col_span)
            elif widget_type == "check":
                ttk.Checkbutton(right, variable=var).grid(row=row, column=1, sticky="w", padx=4, pady=2)
            elif widget_type == "combo":
                cb = ttk.Combobox(right, textvariable=var, values=values or [], width=12, state="readonly")
                cb.grid(row=row, column=1, padx=4, pady=2)
            row += 1

        add_adv("Fixed AV Delay (ms)", self.fixed_av_delay)
        add_adv("Dynamic AV Delay", self.dynamic_av_delay_on, widget_type="check")
        add_adv("Min Dynamic AV Delay (ms)", self.min_dynamic_av_delay)
        add_adv("Sensed AV Offset (ms)", self.sensed_av_delay_offset)
        add_adv("PVARP Extension (ms)", self.pvarp_extension)
        add_adv("Hysteresis Rate Limit (ppm)", self.hysteresis_rate_limit)
        add_adv("Rate Smoothing (%)", self.rate_smoothing_percent)
        add_adv("ATR Mode On", self.atr_mode_on, widget_type="check")
        add_adv("ATR Duration (cycles)", self.atr_duration)
        add_adv("ATR Fallback Time (min)", self.atr_fallback_time)
        add_adv("Ventricular Blanking (ms)", self.ventricular_blanking)
        add_adv("Activity Threshold", self.activity_threshold, widget_type="combo",
                values=["V-Low", "Low", "Med-Low", "Med", "Med-High", "High", "V-High"])
        add_adv("Reaction Time (s)", self.reaction_time)
        add_adv("Response Factor", self.response_factor)
        add_adv("Recovery Time (min)", self.recovery_time)

    def refresh_from_settings(self):
        s = self.app.current_settings
        self.mode_var.set(s.mode)
        for k, var in self.basic_vars.items():
            var.set(str(getattr(s, k)))
        self.fixed_av_delay.set(str(s.fixed_av_delay))
        self.dynamic_av_delay_on.set(bool(s.dynamic_av_delay_on))
        self.min_dynamic_av_delay.set(str(s.min_dynamic_av_delay))
        self.sensed_av_delay_offset.set(str(s.sensed_av_delay_offset))
        self.pvarp_extension.set(str(s.pvarp_extension))
        self.hysteresis_rate_limit.set(str(s.hysteresis_rate_limit))
        self.rate_smoothing_percent.set(str(s.rate_smoothing_percent))
        self.atr_mode_on.set(bool(s.atr_mode_on))
        self.atr_duration.set(str(s.atr_duration))
        self.atr_fallback_time.set(str(s.atr_fallback_time))
        self.ventricular_blanking.set(str(s.ventricular_blanking))
        self.activity_threshold.set(s.activity_threshold)
        self.reaction_time.set(str(s.reaction_time))
        self.response_factor.set(str(s.response_factor))
        self.recovery_time.set(str(s.recovery_time))

    def _build_settings_from_form(self) -> PacemakerSettings:
        s = PacemakerSettings.default(
            owner_username=self.app.current_user or "system",
            mode=self.mode_var.get(),
        )
        for k, var in self.basic_vars.items():
            val = float(var.get()) if "amplitude" in k or "width" in k or "sensitivity" in k else float(var.get())
        # parse numerics carefully
        s.lower_rate_limit = int(self.basic_vars["lower_rate_limit"].get())
        s.upper_rate_limit = int(self.basic_vars["upper_rate_limit"].get())
        s.maximum_sensor_rate = int(self.basic_vars["maximum_sensor_rate"].get())
        s.atrial_amplitude = float(self.basic_vars["atrial_amplitude"].get())
        s.atrial_pulse_width = float(self.basic_vars["atrial_pulse_width"].get())
        s.ventricular_amplitude = float(self.basic_vars["ventricular_amplitude"].get())
        s.ventricular_pulse_width = float(self.basic_vars["ventricular_pulse_width"].get())
        s.ventricular_refractory_period = int(self.basic_vars["ventricular_refractory_period"].get())
        s.atrial_refractory_period = int(self.basic_vars["atrial_refractory_period"].get())
        s.pvarp = int(self.basic_vars["pvarp"].get())
        s.atrial_sensitivity = float(self.basic_vars["atrial_sensitivity"].get())
        s.ventricular_sensitivity = float(self.basic_vars["ventricular_sensitivity"].get())

        s.fixed_av_delay = int(self.fixed_av_delay.get())
        s.dynamic_av_delay_on = bool(self.dynamic_av_delay_on.get())
        s.min_dynamic_av_delay = int(self.min_dynamic_av_delay.get())
        s.sensed_av_delay_offset = int(self.sensed_av_delay_offset.get())
        s.pvarp_extension = int(self.pvarp_extension.get())
        s.hysteresis_rate_limit = int(self.hysteresis_rate_limit.get())
        s.rate_smoothing_percent = int(self.rate_smoothing_percent.get())
        s.atr_mode_on = bool(self.atr_mode_on.get())
        s.atr_duration = int(self.atr_duration.get())
        s.atr_fallback_time = int(self.atr_fallback_time.get())
        s.ventricular_blanking = int(self.ventricular_blanking.get())
        s.activity_threshold = self.activity_threshold.get()
        s.reaction_time = int(self.reaction_time.get())
        s.response_factor = int(self.response_factor.get())
        s.recovery_time = int(self.recovery_time.get())

        return s

    def _on_apply(self):
        try:
            s = self._build_settings_from_form()
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
            return

        ok, errors = self.app.validator.validate_settings(s)
        if not ok:
            messagebox.showerror("Validation failed", "\n".join(errors))
            return

        self.app.current_settings = s
        self.app.storage.save_settings(s)
        messagebox.showinfo("Applied", "Settings applied locally to DCM.")

    def _on_send(self):
        try:
            s = self._build_settings_from_form()
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
            return

        ok, errors = self.app.validator.validate_settings(s)
        if not ok:
            messagebox.showerror("Validation failed", "\n".join(errors))
            return

        self.app.current_settings = s
        self.app.storage.save_settings(s)
        try:
            self.app.comms.send_parameters(s)
        except Exception as e:
            messagebox.showerror("Comm Error", str(e))
            return
        messagebox.showinfo("Sent", "Parameters sent to device (mock or serial).")

    def _on_verify(self):
        mode = self.mode_var.get()
        try:
            device_settings = self.app.comms.read_parameters(mode)
        except Exception as e:
            messagebox.showerror("Comm Error", str(e))
            return

        if device_settings is None:
            messagebox.showerror("Verify Failed", "No settings returned from device.")
            return

        local = self._build_settings_from_form()

        differing = []
        for field in self.app.comms.FIELD_ORDER:
            if getattr(local, field) != getattr(device_settings, field):
                differing.append(f"{field}: local={getattr(local, field)}, device={getattr(device_settings, field)}")

        if differing:
            messagebox.showwarning("Verification Mismatch", "Some parameters differ:\n" + "\n".join(differing))
        else:
            messagebox.showinfo("Verification OK", "Device parameters match DCM parameters for this mode.")

    def _on_uart_test(self):
        """
        UI handler: perform a UART loopback test.

        - Builds a test frame from the current form's PacemakerSettings
        - Uses CommsService.roundtrip_from_settings() to send and poll for a response
        - Shows a message box with the result
        """
        # Make sure we are connected to some COM port
        if not self.app.comms.is_connected:
            messagebox.showerror("UART Loopback Test", "Not connected to any device/COM port.")
            return

        # Try to build settings from the form; if invalid, fall back to last/current settings
        try:
            settings = self._build_settings_from_form()
        except ValueError as e:
            # If parsing fails, try using whatever current_settings we have
            settings = self.app.current_settings
            if settings is None:
                messagebox.showerror("UART Loopback Test", f"Invalid form inputs and no current settings: {e}")
                return

        # Run the loopback test (this blocks the UI briefly, but only for up to ~1 second)
        ok, msg = self.app.comms.roundtrip_from_settings(settings, timeout=1.0, poll_interval=0.02)

        if ok:
            messagebox.showinfo("UART Loopback Test", msg)
        else:
            messagebox.showerror("UART Loopback Test", msg)
