# dcm_app/services/comms_service.py

from __future__ import annotations

import os
import time
import threading
import queue
from typing import Optional, List, Tuple, Dict

import serial
import serial.tools.list_ports

from dcm_app.models.settings import PacemakerSettings


class CommsService:
    """
    Serial communication + parameter protocol + UART logging for the Pacemaker DCM.

    Responsibilities:
    - Enumerate available COM ports
    - Connect / disconnect to a selected port
    - Test connection (lightweight I/O probe)
    - Send / receive compact parameter frames for PacemakerSettings
    - Stream egram bytes into a queue for plotting
    - Log all TX / RX frames to uart_log.txt for debugging and validation
    """

    # ----------------------------------------------------------------------
    # Extended compact parameter frame (16 bytes total)
    #
    # 1-based indexing (Simulink side: i_rx_serial(1..16)):
    #   Byte 1: SYNC             = 0xAA
    #   Byte 2: INSTRUCTION      (e.g., 0x01 = SET_PARAMS, 0x02 = READ_PARAMS)
    #   Byte 3: mode_code
    #   Byte 4: Lower Rate Limit (LRL), ppm
    #   Byte 5: Upper Rate Limit (URL), ppm
    #   Byte 6: Atrial Amplitude * 10 (V -> 0.1 V steps)
    #   Byte 7: Atrial Pulse Width (ms)
    #   Byte 8: Ventricular Amplitude * 10 (V -> 0.1 V steps)
    #   Byte 9: Ventricular Pulse Width (ms)
    #   Byte10: ARP (Atrial Refractory Period) (ms)
    #   Byte11: VRP (Ventricular Refractory Period) (ms)
    #   Byte12: Recovery Time (min)
    #   Byte13: Reaction Time (s)
    #   Byte14: Response Factor
    #   Byte15: Activity Threshold code (0..6)
    #   Byte16: MSR (Maximum Sensor Rate), ppm
    #
    # Zero-based indexing (Python bytes[0..15]):
    #   0: SYNC
    #   1: INSTRUCTION
    #   2: mode_code
    #   3: LRL
    #   4: URL
    #   5: AA_x10
    #   6: APW
    #   7: VA_x10
    #   8: VPW
    #   9: ARP
    #   10: VRP
    #   11: recovery_time
    #   12: reaction_time
    #   13: response_factor
    #   14: activity_threshold_code
    #   15: maximum_sensor_rate
    # ----------------------------------------------------------------------
    PACKET_LEN = 15
    SYNC_BYTE = 0x9

    # Instruction byte values
    # INSTR_SET_PARAMS = 0x01
    # INSTR_READ_PARAMS = 0x02  # reserved for future "read-back" command

    # Mapping of activity threshold string <-> small code
    ACTIVITY_THRESH_MAP: Dict[str, int] = {
        "V-Low": 0,
        "Low": 1,
        "Med-Low": 2,
        "Med": 3,
        "Med-High": 4,
        "High": 5,
        "V-High": 6,
    }
    ACTIVITY_THRESH_MAP_INV: Dict[int, str] = {v: k for k, v in ACTIVITY_THRESH_MAP.items()}

    # Fields checked in ModeConfigFrame._on_verify
    FIELD_ORDER = [
        "mode",
        "lower_rate_limit",
        "upper_rate_limit",
        "atrial_amplitude",
        "atrial_pulse_width",
        "ventricular_amplitude",
        "ventricular_pulse_width",
        "atrial_refractory_period",
        "ventricular_refractory_period",
        "recovery_time",
        "reaction_time",
        "response_factor",
        "activity_threshold",
        "maximum_sensor_rate",
    ]

    # Mode string <-> small code mapping
    MODE_MAP: Dict[str, int] = {
        "AOO": 1,
        "VOO": 2,
        "AAI": 3,
        "VVI": 4,
        "AOOR": 5,
        "VOOR": 6,
        "AAIR": 7,
        "VVIR": 8,
        "DDD": 9,
        "DDDR": 10,
    }
    MODE_MAP_INV: Dict[int, str] = {v: k for k, v in MODE_MAP.items()}

    def __init__(self, baudrate: int = 115200):
        self._baudrate = baudrate
        self._ser: Optional[serial.Serial] = None
        self._port: Optional[str] = None
        self._is_connected: bool = False

        # Egram streaming
        self._egram_queue: Optional[queue.Queue] = None
        self._egram_thread: Optional[threading.Thread] = None
        self._egram_running: bool = False

        # Last settings we attempted to send
        self._last_sent_settings: Optional[PacemakerSettings] = None

        # UART log file path (in current working directory)
        self._log_path = os.path.join(os.getcwd(), "uart_log.txt")

    # ======================================================================
    # Logging helpers
    # ======================================================================
    def _log_frame(self, direction: str, data: bytes) -> None:
        """
        Log raw bytes to uart_log.txt as hex.

        direction:
            'TX'     - actual transmit
            'RX'     - actual receive
            'TX-NC'  - would transmit, but no connection
            'TX-ERR' - transmit attempt raised an exception
            'PARAM-TX' - parameter frame being sent (plus human-readable fields)
            'RT-TX'  - loopback test transmit
            etc.
        """
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        hex_str = " ".join(f"{b:02X}" for b in data)
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {direction} ({len(data)} bytes): {hex_str}\n")
        except Exception:
            # Logging should never break the application
            pass

    def _log_text(self, line: str) -> None:
        """Log a free-form text line (used for field dumps, errors, etc.)."""
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {line}\n")
        except Exception:
            pass

    # ======================================================================
    # Properties
    # ======================================================================
    @property
    def is_connected(self) -> bool:
        return self._is_connected and self._ser is not None and self._ser.is_open

    @property
    def current_port(self) -> Optional[str]:
        return self._port

    # ======================================================================
    # Port enumeration
    # ======================================================================
    def list_ports(self) -> List[str]:
        """
        Return a list of available serial ports, e.g. ["COM3", "COM4"] on Windows,
        ["/dev/ttyACM0", ...] on Linux.
        """
        ports = serial.tools.list_ports.comports()
        return [p.device for p in ports]

    # ======================================================================
    # Connection control
    # ======================================================================
    def connect(self, port: str, baudrate: Optional[int] = None) -> Tuple[bool, Optional[str]]:
        """
        Try to open the given serial port.

        Returns:
            (success: bool, error_message: Optional[str])
        """
        self.disconnect()

        br = baudrate or self._baudrate
        try:
            self._ser = serial.Serial(
                port=port,
                baudrate=br,
                timeout=0.2,
            )
        except Exception as e:
            self._ser = None
            self._port = None
            self._is_connected = False
            err = f"Failed to open {port}: {e}"
            self._log_text(err)
            return False, err

        self._port = port
        self._baudrate = br
        self._is_connected = True
        self._log_text(f"Connected to {port} at {br} baud.")
        return True, None

    def disconnect(self) -> None:
        """Close any active serial connection and stop egram streaming."""
        self.stop_egram_stream()

        if self._ser is not None:
            try:
                if self._ser.is_open:
                    self._ser.close()
                    self._log_text(f"Closed serial port {self._port}.")
            except Exception as e:
                self._log_text(f"Error while closing serial port {self._port}: {e}")

        self._ser = None
        self._port = None
        self._is_connected = False

    # ======================================================================
    # Connection test
    # ======================================================================
    def test_connection(self) -> Tuple[bool, str]:
        """
        Lightweight test that the currently open port is alive and usable.

        We *do not* assume any pacemaker protocol yet:
        - Just checks the port is open
        - Tries a tiny non-invasive I/O (flush + in_waiting)
        If any serial exception is raised, we treat it as a failed test.
        """
        if not self.is_connected or self._ser is None:
            msg = "No open serial connection. Please connect first."
            self._log_text(f"[TEST] {msg}")
            return False, msg

        try:
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            _ = self._ser.in_waiting  # exercise driver
            msg = f"Port {self._port} is open and responsive."
            self._log_text(f"[TEST] {msg}")
            return True, msg
        except Exception as e:
            msg = f"Serial I/O error on {self._port}: {e}"
            self._log_text(f"[TEST] {msg}")
            return False, msg

    # ======================================================================
    # Egram queue attachment + streaming
    # ======================================================================
    def attach_egram_queue(self, eg_queue: queue.Queue) -> None:
        """Attach a queue where egram samples will be pushed."""
        self._egram_queue = eg_queue

    def start_egram_stream(self) -> None:
        """
        Start a background thread that continuously reads from serial and pushes
        data into the egram queue.
        """
        if not self.is_connected:
            self._log_text("[EGRAM] Not starting stream: not connected.")
            return
        if self._egram_running:
            return

        self._egram_running = True
        self._egram_thread = threading.Thread(
            target=self._egram_loop,
            name="EgramReader",
            daemon=True,
        )
        self._egram_thread.start()
        self._log_text("[EGRAM] Egram stream started.")

    def stop_egram_stream(self) -> None:
        """Request the egram thread to stop."""
        self._egram_running = False
        if self._egram_thread and self._egram_thread.is_alive():
            self._egram_thread.join(timeout=0.5)
        self._egram_thread = None
        if self.is_connected:
            self._log_text("[EGRAM] Egram stream stopped.")

    def _egram_loop(self) -> None:
        """Background loop: read raw samples and push to queue."""
        while self._egram_running and self._ser is not None and self._ser.is_open:
            try:
                # reuse read_bytes so RX logging happens here too
                data = self.read_bytes(64)
                if not data:
                    time.sleep(0.01)
                    continue

                if self._egram_queue is not None:
                    samples = list(data)
                    self._egram_queue.put(samples)
            except Exception as e:
                self._log_text(f"[EGRAM] Error in egram loop: {e}")
                break

        self._egram_running = False

    # ======================================================================
    # Raw send/receive primitives (with logging)
    # ======================================================================
    def write_bytes(self, payload: bytes) -> bool:
        """
        Low-level write to the serial port with logging.
        """
        if not self.is_connected or self._ser is None:
            # Log what *would* have been sent
            self._log_frame("TX-NC", payload)
            return False
        try:
            self._ser.write(payload)
            self._log_frame("TX", payload)
            return True
        except Exception as e:
            self._log_frame("TX-ERR", payload)
            self._log_text(f"[WRITE] Error writing to {self._port}: {e}")
            return False

    def read_bytes(self, size: int) -> bytes:
        """
        Low-level read from the serial port with logging.
        """
        if not self.is_connected or self._ser is None:
            return b""
        try:
            data = self._ser.read(size)
            if data:
                self._log_frame("RX", data)
            return data
        except Exception as e:
            self._log_text(f"[READ] Error reading from {self._port}: {e}")
            return b""

    # ======================================================================
    # Compact parameter protocol
    # ======================================================================
    # ======================================================================
    # Compact parameter protocol
    # ======================================================================
    def send_parameters(self, settings: PacemakerSettings) -> None:
        """
        Encode PacemakerSettings into our compact 16-byte frame and send over UART.

        Frame layout (bytes, zero-based indexing):
          [0] SYNC                    = 0xAA
          [1] INSTRUCTION             = 0x01 (SET_PARAMS)
          [2] mode_code
          [3] Lower Rate Limit (ppm)
          [4] Upper Rate Limit (ppm)
          [5] Atrial Amplitude * 10   (0.1 V steps)
          [6] Atrial Pulse Width (ms)
          [7] Ventricular Amplitude * 10
          [8] Ventricular Pulse Width (ms)
          [9] ARP  (ms)
          [10] VRP (ms)
          [11] Recovery Time   (min)
          [12] Reaction Time   (s)
          [13] Response Factor
          [14] Activity Threshold code (0..6)
          [15] Maximum Sensor Rate (ppm)
        """
        import struct

        self._last_sent_settings = settings

        frame = self._encode_settings_to_frame(settings)

        # Log readable field summary
        debug_fields = {
            "mode": settings.mode,
            "LRL": settings.lower_rate_limit,
            "URL": settings.upper_rate_limit,
            "AA": settings.atrial_amplitude,
            "APW": settings.atrial_pulse_width,
            "VA": settings.ventricular_amplitude,
            "VPW": settings.ventricular_pulse_width,
            "ARP": settings.atrial_refractory_period,
            "VRP": settings.ventricular_refractory_period,
            "Recovery": settings.recovery_time,
            "Reaction": settings.reaction_time,
            "RespFactor": settings.response_factor,
            "ActivityThresh": settings.activity_threshold,
            "MSR": settings.maximum_sensor_rate,
        }
        
        field_line = " | ".join(f"{k}={v}" for k, v in debug_fields.items())
        self._log_frame("PARAM-TX", frame)
        self._log_text("    Fields: " + field_line)

        if not self.is_connected or self._ser is None:
            # Mock mode: just log and return
            self._log_text("[PARAM] send_parameters called with no active serial connection (mock send only).")
            return

        try:
            print(f"Writing data {frame}")
            ok = self.write_bytes(frame)
            if not ok:
                raise RuntimeError("write_bytes returned False.")
            if self._ser is not None:
                self._ser.flush()
        except Exception as e:
            msg = f"Error writing parameters to serial port: {e}"
            self._log_text("[PARAM] " + msg)
            raise RuntimeError(msg)

    def read_parameters(self, mode: str) -> Optional[PacemakerSettings]:
        """
        Read one 16-byte parameter frame from the device and decode it into a PacemakerSettings.

        For now we assume the pacemaker will send exactly one frame in response
        to some command (or on demand) and that it uses the same encoding format.
        """
        if not self.is_connected or self._ser is None:
            raise RuntimeError("Not connected to device.")

        raw = self.read_bytes(self.PACKET_LEN)
        if len(raw) != self.PACKET_LEN:
            self._log_text(f"[PARAM] read_parameters: expected {self.PACKET_LEN} bytes, got {len(raw)}.")
            return None

        settings = self._decode_frame_to_settings(mode, raw)
        # Log decoded fields
        debug_fields = {
            "mode": settings.mode,
            "LRL": settings.lower_rate_limit,
            "URL": settings.upper_rate_limit,
            "AA": settings.atrial_amplitude,
            "APW": settings.atrial_pulse_width,
            "VA": settings.ventricular_amplitude,
            "VPW": settings.ventricular_pulse_width,
            "ARP": settings.atrial_refractory_period,
            "VRP": settings.ventricular_refractory_period,
            "Recovery": settings.recovery_time,
            "Reaction": settings.reaction_time,
            "RespFactor": settings.response_factor,
            "ActivityThresh": settings.activity_threshold,
            "MSR": settings.maximum_sensor_rate,
        }
        field_line = " | ".join(f"{k}={v}" for k, v in debug_fields.items())
        self._log_text("[PARAM] Decoded from RX: " + field_line)
        return settings

    # ------------------------------------------------------------------
    # Encode/decode helpers
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Encode/decode helpers
    # ------------------------------------------------------------------
    def _encode_settings_to_frame(self, s: PacemakerSettings) -> bytes:
        """
        Map PacemakerSettings -> 15-byte frame.

        Frame layout (zero-based):
          [0] SYNC                    = 0xAA
          [1] mode_code
          [2] Lower Rate Limit (ppm)
          [3] Upper Rate Limit (ppm)
          [4] Atrial Amplitude * 10   (0.1 V steps)
          [5] Atrial Pulse Width (ms)
          [6] Ventricular Amplitude * 10
          [7] Ventricular Pulse Width (ms)
          [8] ARP  (ms)
          [9] VRP (ms)
          [10] Recovery Time   (min)
          [11] Reaction Time   (s)
          [12] Response Factor
          [13] Activity Threshold code (0..6)
          [14] Maximum Sensor Rate (ppm)
        """
        import struct

        mode_code = self.MODE_MAP.get(s.mode, 0)

        lrl = max(0, min(255, int(s.lower_rate_limit)))
        url = max(0, min(255, int(s.upper_rate_limit)))
        msr = max(0, min(255, int(s.maximum_sensor_rate)))

        # store amplitudes in 0.1 V increments
        aa = max(0, min(255, int(round(s.atrial_amplitude * 10.0))))
        va = max(0, min(255, int(round(s.ventricular_amplitude * 10.0))))

        apw = max(0, min(255, int(round(s.atrial_pulse_width))))
        vpw = max(0, min(255, int(round(s.ventricular_pulse_width))))

        arp = max(0, min(255, int(round(s.atrial_refractory_period))))
        vrp = max(0, min(255, int(round(s.ventricular_refractory_period))))

        recovery = max(0, min(255, int(round(s.recovery_time))))
        reaction = max(0, min(255, int(round(s.reaction_time))))
        resp_factor = max(0, min(255, int(round(s.response_factor))))

        # Activity threshold string -> code
        act_code = self.ACTIVITY_THRESH_MAP.get(s.activity_threshold, 3)  # default "Med"
        act_code = max(0, min(255, int(act_code)))
        
        format_specifier = self.PACKET_LEN * ['B']
        packet = b""
        
        values = [
            self.SYNC_BYTE & 0xFF,
            mode_code & 0xFF,        # 1
            lrl & 0xFF,              # 2
            url & 0xFF,              # 3
            aa & 0xFF,               # 4
            apw & 0xFF,              # 5
            va & 0xFF,               # 6
            vpw & 0xFF,              # 7
            arp & 0xFF,              # 8
            vrp & 0xFF,              # 9
            recovery & 0xFF,         # 10
            reaction & 0xFF,         # 11
            resp_factor & 0xFF,      # 12
            act_code & 0xFF,         # 13
            msr & 0xFF,              # 14
        ]
            
        for format_spec, value in zip(format_specifier, values):
            packet += struct.pack(format_spec, value)
            
        return packet

        # 15 bytes total => 15 'B's
        frame = struct.pack(
            "<BBBBBBBBBBBBBBB",
            self.SYNC_BYTE,          # [0]
            mode_code & 0xFF,        # [1]
            lrl & 0xFF,              # [2]
            url & 0xFF,              # [3]
            aa & 0xFF,               # [4]
            apw & 0xFF,              # [5]
            va & 0xFF,               # [6]
            vpw & 0xFF,              # [7]
            arp & 0xFF,              # [8]
            vrp & 0xFF,              # [9]
            recovery & 0xFF,         # [10]
            reaction & 0xFF,         # [11]
            resp_factor & 0xFF,      # [12]
            act_code & 0xFF,         # [13]
            msr & 0xFF,              # [14]
        )
        return frame

    def _decode_frame_to_settings(self, mode: str, frame: bytes) -> PacemakerSettings:
        """
        Map 15-byte frame -> PacemakerSettings.
        """
        if len(frame) != self.PACKET_LEN:
            raise ValueError(f"Frame must be {self.PACKET_LEN} bytes.")

        (b0, b1, b2, b3, b4,
         b5, b6, b7, b8, b9,
         b10, b11, b12, b13, b14) = frame

        if b0 != self.SYNC_BYTE:
            self._log_text(
                f"[PARAM] Warning: unexpected sync byte {b0:#02x}, "
                f"expected {self.SYNC_BYTE:#02x}."
            )

        decoded_mode = self.MODE_MAP_INV.get(b1, mode)

        lrl = int(b2)
        url = int(b3)

        aa = b4 / 10.0
        apw = float(b5)

        va = b6 / 10.0
        vpw = float(b7)

        arp = int(b8)
        vrp = int(b9)

        recovery = int(b10)
        reaction = int(b11)
        resp_factor = int(b12)

        act_code = int(b13)
        activity_threshold = self.ACTIVITY_THRESH_MAP_INV.get(act_code, "Med")

        msr = int(b14)

        # Build PacemakerSettings instance
        s = PacemakerSettings.default(
            owner_username="device",
            mode=decoded_mode,
        )

        s.lower_rate_limit = lrl
        s.upper_rate_limit = url
        s.maximum_sensor_rate = msr

        s.atrial_amplitude = aa
        s.atrial_pulse_width = apw
        s.ventricular_amplitude = va
        s.ventricular_pulse_width = vpw

        s.atrial_refractory_period = arp
        s.ventricular_refractory_period = vrp

        s.recovery_time = recovery
        s.reaction_time = reaction
        s.response_factor = resp_factor
        s.activity_threshold = activity_threshold

        return s


    # ======================================================================
    # Loopback helpers
    # ======================================================================
    def roundtrip_from_settings(
        self,
        settings: PacemakerSettings,
        timeout: float = 1.0,
        poll_interval: float = 0.02,
    ) -> Tuple[bool, str]:
        """
        Convenience wrapper: build a frame from PacemakerSettings and run a
        UART loopback test against the currently-connected device.
        """
        frame = self._encode_settings_to_frame(settings)
        return self.debug_roundtrip_test(frame, timeout=timeout, poll_interval=poll_interval)

    def debug_roundtrip_test(
        self,
        test_frame: bytes,
        timeout: float = 1.0,
        poll_interval: float = 0.02,
    ) -> Tuple[bool, str]:
        """
        Send a test frame and repeatedly check for a response for up to `timeout`.

        Assumes the K64 model echoes the data (Serial Receive -> Serial Transmit)
        or at least returns a single 16-byte frame in response.
        """
        if not self.is_connected or self._ser is None:
            msg = "Not connected to any serial port."
            self._log_text("[RT] " + msg)
            return False, msg

        if len(test_frame) != self.PACKET_LEN:
            msg = f"Test frame must be {self.PACKET_LEN} bytes, got {len(test_frame)}."
            self._log_text("[RT] " + msg)
            return False, msg

        # Flush buffers so we don't read stale data
        try:
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
        except Exception as e:
            msg = f"Error resetting buffers on {self._port}: {e}"
            self._log_text("[RT] " + msg)
            return False, msg

        # Send test frame
        self._log_frame("RT-TX", test_frame)
        try:
            self._ser.write(test_frame)
            self._ser.flush()
        except Exception as e:
            msg = f"Error writing test frame to {self._port}: {e}"
            self._log_text("[RT] " + msg)
            return False, msg

        # Poll for response until timeout
        end_time = time.time() + timeout
        last_rx: Optional[bytes] = None

        while time.time() < end_time:
            data = self.read_bytes(self.PACKET_LEN)
            if len(data) == 0:
                time.sleep(poll_interval)
                continue

            last_rx = data

            if data == test_frame:
                msg = f"Roundtrip OK. Got back: {data.hex(' ')}"
                self._log_text("[RT] " + msg)
                return True, msg
            else:
                self._log_text(f"[RT] Non-matching RX frame: {data.hex(' ')}")
                time.sleep(poll_interval)

        # Timeout
        if last_rx is None:
            msg = "No response received during loopback test."
        else:
            msg = f"Loopback timeout. Last RX: {last_rx.hex(' ')}"
        self._log_text("[RT] " + msg)
        return False, msg
