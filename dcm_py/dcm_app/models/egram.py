from dataclasses import dataclass

@dataclass
class EgramSample:
    timestamp_ms: int
    value_mv: float
    chamber: str  # "A" or "V"
