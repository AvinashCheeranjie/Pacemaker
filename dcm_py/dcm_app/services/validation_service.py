from typing import List, Tuple

from dcm_app.models.settings import PacemakerSettings


class ValidationService:
    """Validate PacemakerSettings against simplified Table-7 constraints."""

    def validate_settings(self, s: PacemakerSettings) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # Lower Rate Limit: 30–175 (with piecewise increments, but we just bound)
        if not (30 <= s.lower_rate_limit <= 175):
            errors.append("Lower Rate Limit must be between 30 and 175 ppm.")

        # Upper Rate Limit
        if not (s.lower_rate_limit <= s.upper_rate_limit <= 175):
            errors.append("Upper Rate Limit must be between LRL and 175 ppm.")

        # Maximum Sensor Rate
        if not (50 <= s.maximum_sensor_rate <= 175):
            errors.append("Maximum Sensor Rate must be between 50 and 175 ppm.")

        # Pulse amplitudes (simplified: 0.1–7.0 V)
        for name, val in [
            ("Atrial Amplitude", s.atrial_amplitude),
            ("Ventricular Amplitude", s.ventricular_amplitude),
        ]:
            if not (0.1 <= val <= 7.0):
                errors.append(f"{name} must be between 0.1 and 7.0 V.")

        # Pulse widths (0.05–1.9 ms)
        for name, val in [
            ("Atrial Pulse Width", s.atrial_pulse_width),
            ("Ventricular Pulse Width", s.ventricular_pulse_width),
        ]:
            if not (0.05 <= val <= 1.9):
                errors.append(f"{name} must be between 0.05 and 1.9 ms.")

        # Sensitivities (0–10 mV)
        for name, val in [
            ("Atrial Sensitivity", s.atrial_sensitivity),
            ("Ventricular Sensitivity", s.ventricular_sensitivity),
        ]:
            if not (0.0 <= val <= 10.0):
                errors.append(f"{name} must be between 0.0 and 10.0 mV.")

        # Refractory periods and PVARP
        for name, val in [
            ("VRP", s.ventricular_refractory_period),
            ("ARP", s.atrial_refractory_period),
            ("PVARP", s.pvarp),
        ]:
            if not (150 <= val <= 500):
                errors.append(f"{name} must be between 150 and 500 ms.")

        # AV delay
        if not (70 <= s.fixed_av_delay <= 300):
            errors.append("Fixed AV Delay must be between 70 and 300 ms.")

        # Dynamic AV delay minimum
        if not (30 <= s.min_dynamic_av_delay <= 100):
            errors.append("Min Dynamic AV Delay must be between 30 and 100 ms.")

        # Sensed AV offset (0 or negative)
        if not (-100 <= s.sensed_av_delay_offset <= 0):
            errors.append("Sensed AV Delay Offset must be between 0 and -100 ms.")

        # Activity threshold
        if s.activity_threshold not in ["V-Low", "Low", "Med-Low", "Med", "Med-High", "High", "V-High"]:
            errors.append("Activity Threshold must be one of the predefined categories.")

        return (len(errors) == 0), errors
