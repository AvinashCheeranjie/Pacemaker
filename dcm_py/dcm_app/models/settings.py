from dataclasses import dataclass, asdict
from typing import Dict


@dataclass
class PacemakerSettings:
    """Represents full Table-7 programmable parameters for one pacing mode."""

    owner_username: str
    mode: str  # e.g., VVI, VVIR, DDD, AOOR, etc.

    # Basic bradycardia parameters
    lower_rate_limit: int = 60
    upper_rate_limit: int = 120
    maximum_sensor_rate: int = 120

    # Pulse characteristics
    atrial_amplitude: float = 3.5
    atrial_pulse_width: float = 0.4
    ventricular_amplitude: float = 3.5
    ventricular_pulse_width: float = 0.4

    # Sensitivity
    atrial_sensitivity: float = 0.75
    ventricular_sensitivity: float = 2.5

    # Refractory periods
    ventricular_refractory_period: int = 320
    atrial_refractory_period: int = 250
    pvarp: int = 250

    # AV timing
    fixed_av_delay: int = 150
    dynamic_av_delay_on: bool = False
    min_dynamic_av_delay: int = 50
    sensed_av_delay_offset: int = 0  # 0 or negative

    # PVARP extension
    pvarp_extension: int = 0

    # Hysteresis / Rate smoothing
    hysteresis_rate_limit: int = 0  # 0 = Off
    rate_smoothing_percent: int = 0

    # ATR (Atrial Tachycardia Response)
    atr_mode_on: bool = False
    atr_duration: int = 20  # cardiac cycles
    atr_fallback_time: int = 1  # minutes

    # Ventricular blanking
    ventricular_blanking: int = 40

    # Rate response (accelerometer)
    activity_threshold: str = "Med"
    reaction_time: int = 30  # seconds
    response_factor: int = 8
    recovery_time: int = 5  # minutes

    @staticmethod
    def default(owner_username: str, mode: str) -> "PacemakerSettings":
        return PacemakerSettings(owner_username=owner_username, mode=mode)

    def to_dict(self) -> Dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: Dict) -> "PacemakerSettings":
        return PacemakerSettings(**data)
