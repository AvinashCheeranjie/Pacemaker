# Pacemaker Device Controller–Monitor (DCM) Documentation  
_Group 22 – Fall 2025_  

This document captures the **DCM-specific** design, implementation and testing work for the Pacemaker project.  
All Simulink / pacemaker firmware content is intentionally omitted here so this file can be included directly with the
Python DCM project.

---

## 1. Introduction

The Device Controller–Monitor (DCM) is the **external programmer** used by a clinician to configure and monitor the
pacemaker system. While the Simulink model and embedded firmware implement the therapy logic and hardware control,
the DCM is responsible for:

- Allowing **authenticated access** to the device
- Presenting **pacing modes** and **programmable parameters**
- Sending validated configuration data to the pacemaker
- Reading back configuration data to **verify** what is stored on the device
- Displaying **egram (electrogram)** waveforms for atrial and ventricular chambers

For Deliverable 1, the DCM was implemented as a **front-end only UI** (no real serial I/O or persistence), focused on
authentication, mode visibility, and basic parameter editing.

For Deliverable 2, the DCM has been expanded and migrated to a **Python/Tkinter desktop application** with:

- A fully object-oriented architecture
- JSON-based local persistence for users and settings
- A simple and robust line-based serial protocol
- Complete support for the programmable parameters from **PACEMAKER Table 7**
- A real-time egram viewer (mock or serial-backed)
- End-to-end parameter **set / store / transmit / verify** workflow

The design follows the course design principles:

- **Separation of concerns** – models, services, and UI are in separate modules
- **Information hiding** – serial protocol details and storage format are hidden behind services
- **High cohesion and low coupling** – each module has a single clear responsibility
- **Support for change** – adding modes, parameters, or new communication features requires minimal code changes

---

## 2. DCM Requirements

### 2.1 Deliverable 1 DCM Requirements (Recap & Mapping)

The following requirements were identified from the course handouts and natural-language PACEMAKER specification.
Each requirement is followed by the component that satisfies it in the Python DCM.

1. The DCM shall provide a login and registration interface allowing up to 10 users.  
   - Implemented by `AuthScreen` and `StorageService` (10-user cap enforced).

2. The DCM shall display a dashboard view after a successful login.  
   - Implemented by `DashboardScreen` (top bar + tabbed views).

3. The DCM shall simulate device connection status (Online/Offline).  
   - In this Python version, `CommsService` exposes `is_connected`.  
   - When `USE_SERIAL = False` it simulates a “mock device” that always connects successfully.

4. The DCM shall support displaying and selecting the following pacing modes: AOO, VOO, AAI, and VVI.  
   - Implemented in `ModeConfigFrame` via `SUPPORTED_MODES` list (Deliverable 2 adds more modes).

5. The DCM shall allow the user to select and activate one pacing mode at a time.  
   - `ModeConfigFrame` exposes a single selected mode via a `Combobox` bound to `PacemakerSettings.mode`.

6. The DCM shall allow the user to configure programmable parameters including:  
   - Lower Rate Limit (LRL)  
   - Upper Rate Limit (URL)  
   - Atrial Amplitude  
   - Atrial Pulse Width  
   - Ventricular Amplitude  
   - Ventricular Pulse Width  
   - Atrial Refractory Period (ARP)  
   - Ventricular Refractory Period (VRP)  
   - Implemented as text fields backed by `PacemakerSettings` and validated by `ValidationService`.

7. The DCM shall allow parameter adjustment via GUI controls and display a summary of selected values.  
   - In the Python version, each field is a `ttk.Entry`; the **entire `PacemakerSettings` object** is the summary,
     stored and serialized via `StorageService` and `CommsService`.

### 2.2 Additional Deliverable 2 DCM Requirements

Deliverable 2 introduced further responsibilities for the DCM:

1. **Expand the DCM to include all required modes and parameters** (Table 7).  
   - All Table-7 parameters are represented in `PacemakerSettings` and editable in `ModeConfigFrame`.  
   - Supported modes list: `["AOO","VOO","AAI","VVI","AOOR","VOOR","AAIR","VVIR","DDD","DDDR"]`.

2. **Implement serial communication to transmit and receive information between the DCM and the Pacemaker.**  
   - `CommsService` defines a simple line-based ASCII protocol with `PSET`, `PGET`, and `PACK` commands.

3. **Set, store, transmit programmable parameter data, and verify it is stored correctly on the Pacemaker.**  
   - `ModeConfigFrame` → “Send to Device” uses `CommsService.send_parameters(...)`.  
   - “Read & Verify” uses `CommsService.read_parameters(...)` and compares field-by-field.

4. **Support display of egram data using real-time electrogram signals (V/A/Both) over the serial link.**  
   - Implemented by `EgramFrame`, which renders samples from `EgramSample` objects into a `Canvas`.  
   - Egram data is provided by `CommsService.start_egram_stream(...)` (mock or serial).

5. **Origination, representation, and verification of parameters** must be documented.  
   - Origin: clinician/user input via `ModeConfigFrame` UI.  
   - Representation: `PacemakerSettings` dataclass with explicit types.  
   - Transmission: serialized as CSV in fixed `FIELD_ORDER` over serial.  
   - Verification: comparison of local vs device settings in `ModeConfigFrame._on_verify`.

---

## 3. System Design (DCM Only)

### 3.1 High-Level Architecture

The DCM is implemented as a classical three-layer GUI application:

- **Model layer (data classes)**  
  - `PacemakerSettings` – full Table-7 parameter set for one mode  
  - `User` – local user accounts  
  - `EgramSample` – time-stamped electrogram samples

- **Service layer (logic / infrastructure)**  
  - `StorageService` – JSON persistence of users and per-user settings  
  - `CommsService` – serial and mock communication (parameters + egrams)  
  - `ValidationService` – checks `PacemakerSettings` against simplified Table-7 constraints

- **UI layer (presentation / workflow)**  
  - `AuthScreen` – login and registration, up to 10 users  
  - `DashboardScreen` – shell screen with top bar and tabbed views  
  - `ModeConfigFrame` – pacing mode + parameter configuration UI  
  - `EgramFrame` – real-time A/V/both egram canvas

The root `DCMApp` (subclass of `tk.Tk`) constructs shared services once and injects them into all screens.

```text
main.py
└── DCMApp (Tk root)
    ├── StorageService
    ├── CommsService
    ├── ValidationService
    ├── AuthScreen
    └── DashboardScreen
         ├── ModeConfigFrame
         └── EgramFrame
```

### 3.2 Data Model

#### 3.2.1 PacemakerSettings

`PacemakerSettings` is the **single source of truth** for DCM-side configuration. It includes:

- Identification:
  - `owner_username: str`
  - `mode: str`

- Basic bradycardia parameters:
  - `lower_rate_limit: int`
  - `upper_rate_limit: int`
  - `maximum_sensor_rate: int`

- Pulse characteristics:
  - `atrial_amplitude: float`
  - `atrial_pulse_width: float`
  - `ventricular_amplitude: float`
  - `ventricular_pulse_width: float`

- Sensitivity:
  - `atrial_sensitivity: float`
  - `ventricular_sensitivity: float`

- Refractory periods:
  - `ventricular_refractory_period: int`
  - `atrial_refractory_period: int`
  - `pvarp: int`

- AV timing:
  - `fixed_av_delay: int`
  - `dynamic_av_delay_on: bool`
  - `min_dynamic_av_delay: int`
  - `sensed_av_delay_offset: int`

- PVARP extension:
  - `pvarp_extension: int`

- Hysteresis / Rate smoothing:
  - `hysteresis_rate_limit: int`
  - `rate_smoothing_percent: int`

- ATR response:
  - `atr_mode_on: bool`
  - `atr_duration: int`
  - `atr_fallback_time: int`

- Ventricular blanking:
  - `ventricular_blanking: int`

- Rate-adaptive (accelerometer-based) pacing parameters:
  - `activity_threshold: str`
  - `reaction_time: int`
  - `response_factor: int`
  - `recovery_time: int`

The dataclass provides:

- `default(owner_username, mode)` – standard nominal values
- `to_dict()` / `from_dict()` – JSON-safe conversions

These are used by `StorageService` (for disk persistence) and `CommsService` (for serial transmission).

#### 3.2.2 Users

`User` is a minimal dataclass:

- `username: str`
- `password_hash: str` (simple Python `hash()`, adequate for course scope)

`StorageService` enforces a maximum of **10 users** and provides basic registration and login validation.

#### 3.2.3 EgramSample

Represents a single analog egram sample:

- `timestamp_ms: int` – acquisition time in milliseconds
- `value_mv: float` – signal magnitude (scaled units)
- `chamber: str` – `"A"` or `"V"`

`CommsService` generates or receives these and `EgramFrame` renders them.

### 3.3 Services

#### 3.3.1 StorageService

**Purpose**: Provide a simple, robust, testable persistence layer without external dependencies.

- Files:
  - `users.json` – array of users
  - `settings.json` – dict mapping `username -> PacemakerSettings`

**Public methods:**

- `load_users() -> List[User]`
- `save_users(users: List[User])`
- `register_user(username: str, password: str) -> bool`
- `validate_login(username: str, password: str) -> bool`
- `load_settings(username: str) -> Optional[PacemakerSettings]`
- `save_settings(settings: PacemakerSettings)`

This encapsulation ensures the rest of the app is unaffected if the storage mechanism changes (e.g., to SQLite).

#### 3.3.2 ValidationService

**Purpose**: Centralize validation of `PacemakerSettings` according to Table-7 constraints (simplified).

- `validate_settings(s: PacemakerSettings) -> (bool, List[str])`

Checks:

- Rate limits (LRL, URL, MSR)
- Pulse amplitudes and widths
- Sensitivity bounds
- Refractory periods and PVARP
- AV delays and offsets
- Activity threshold enumeration

The UI never directly embeds numeric limits; instead, it calls `ValidationService`, reinforcing separation of concerns.

#### 3.3.3 CommsService

**Purpose**: Hide all serial protocol details from the UI, while supporting both **mock** and **real** hardware.

- `USE_SERIAL = False` by default → no external dependency on hardware or `pyserial`.
- `connect()` / `disconnect()` manage connection state.
- `send_parameters(settings: PacemakerSettings)`:
  - Build CSV: `PSET,<mode>,<val1>,...,<valN>`
  - In mock mode: store in `_mock_device_memory[mode]`
- `read_parameters(mode: str) -> Optional[PacemakerSettings]`:
  - In mock mode: return the stored `PacemakerSettings`
  - In serial mode: send `PGET,<mode>`, expect `PACK,<mode>,<val1>,...,<valN>`
- Egram:
  - `attach_egram_queue(queue)` – UI attaches a `queue.Queue` to receive `EgramSample`
  - `start_egram_stream(mode)` – start mock or serial loop
  - `stop_egram_stream()` – stop streaming

This design allows the same UI to work:

- **In lab demos** – using mock mode only.
- **With real hardware** – by turning on `USE_SERIAL` and implementing the same protocol on the microcontroller.

### 3.4 UI Modules

#### 3.4.1 AuthScreen

**Purpose**:  
Provide login and registration for up to 10 users before any DCM functions are accessible.

**Key behaviours:**

- `Login` – validates credentials via `StorageService.validate_login`.
- `Register` – attempts user registration via `StorageService.register_user`.
- On successful login, calls `app.login_success(username)`.

#### 3.4.2 DashboardScreen

**Purpose**:  
Root post-login workspace that presents user info, connection state, and subviews.

**Structure:**

- Top bar:
  - Logged-in user label
  - Connection status (mock device, connected/disconnected)
  - “Logout” and “Disconnect” buttons
- `ttk.Notebook` with two tabs:
  - `ModeConfigFrame` (“Modes & Parameters”)
  - `EgramFrame` (“Egrams”)

#### 3.4.3 ModeConfigFrame

**Purpose**:  
Configure pacing mode and **all Table-7 parameters**; send and verify parameters with the device.

**Features:**

- Mode selection combobox (`SUPPORTED_MODES`).
- Basic parameters group for LRL, URL, MSR, amplitudes, widths, VRP, ARP, PVARP, sensitivities.
- Advanced parameters group for AV timing, PVARP extension, hysteresis, rate smoothing, ATR settings, blanking,
  and accelerometer-based rate response.
- Buttons:
  - “Apply to DCM” – Validate & save locally via `StorageService`.
  - “Send to Device” – Validate & transmit via `CommsService.send_parameters`.
  - “Read & Verify” – Fetch via `read_parameters` and compare every field.

This screen is where most Deliverable 2 capability lives and demonstrates the complete parameter lifecycle:
**input → validation → storage → transmission → verification**.

#### 3.4.4 EgramFrame

**Purpose**:  
Visualize egram data for **atrium, ventricle, or both** chambers in near real time.

**Implementation:**

- Uses a `Canvas` with simple line-drawing; no external plotting libraries.
- Maintains short histories for A and V series (e.g., last 200 samples).
- Periodically pulls samples from the shared `Queue` attached to `CommsService`.
- UI controls to start/stop streaming and select chamber mode.

In mock mode, `CommsService` generates sinusoid-like data to simulate realistic variability.

---

## 4. Serial Protocol

The serial protocol is deliberately **simple and robust**:

- One ASCII line per packet
- Comma-separated values
- No embedded commas in fields
- Newline-terminated (`\n`)
- Fixed field ordering documented in `CommsService.FIELD_ORDER`

### 4.1 Parameter Packets

- **Set parameters (DCM → Pacemaker):**  
  `PSET,<mode>,<val1>,...,<valN>`

- **Request parameters (DCM → Pacemaker):**  
  `PGET,<mode>`

- **Return parameters (Pacemaker → DCM):**  
  `PACK,<mode>,<val1>,...,<valN>`

Values are encoded as:

- `int` → decimal integer
- `float` → decimal string (e.g., `3.5`)
- `bool` → `0` or `1`
- `str` → plain string with no commas (only `activity_threshold` uses this)

### 4.2 Egram Packets

Generated by pacemaker (or mock) and consumed by DCM:

- `EGRAM,<chamber>,<t_ms>,<value_mv>`

Example:

- `EGRAM,A,123,0.45`
- `EGRAM,V,130,1.20`

The DCM does not require strict timing guarantees; it simply renders whatever arrives near real time.

---

## 5. Testing

This section focuses on **DCM tests** only. Pacemaker/Simulink tests are documented separately.

### 5.1 Functional Tests – Authentication & Users

**Test D1-1 – Registration limit (10 users)**  
- Purpose: Ensure no more than 10 users can be registered.  
- Steps:
  1. Register users `u1` ... `u10` with any password.
  2. Attempt to register `u11`.  
- Expected: Registration of `u11` fails with an error message.  
- Result: Pass.

**Test D1-2 – Login validation**  
- Purpose: Verify only correct credentials are accepted.  
- Steps:
  1. Register user `alice` with password `1234`.
  2. Try login with `alice / 0000` (wrong password).
  3. Try login with `bob / 1234` (unknown user).
  4. Try login with `alice / 1234`.  
- Expected: Only step 4 succeeds and transitions to the Dashboard.  
- Result: Pass.

### 5.2 Functional Tests – Modes & Parameters

**Test D2-1 – Mode selection list**  
- Purpose: Verify all required modes are visible and selectable.  
- Steps:
  1. Login and go to “Modes & Parameters”.  
  2. Open the mode combobox.  
- Expected: Modes `AOO, VOO, AAI, VVI, AOOR, VOOR, AAIR, VVIR, DDD, DDDR` are visible and selectable.  
- Result: Pass.

**Test D2-2 – Apply to DCM (local storage)**  
- Purpose: Ensure parameter changes are validated and stored locally.  
- Steps:
  1. Select mode `VVIR`.
  2. Set `LRL = 60`, `URL = 130`, `MSR = 130`.
  3. Adjust amplitudes and widths to valid values.
  4. Click “Apply to DCM”.  
- Expected:
  - Validation succeeds.
  - No error message is shown.
  - `settings.json` is updated for the current user.  
- Result: Pass.

**Test D2-3 – Validation failure example**  
- Purpose: Ensure invalid parameters are rejected.  
- Steps:
  1. Set `LRL = 10` ppm (below 30).  
  2. Click “Apply to DCM”.  
- Expected:
  - `ValidationService` reports “Lower Rate Limit must be between 30 and 175 ppm.”
  - Settings are not saved.  
- Result: Pass.

### 5.3 Functional Tests – Transmission & Verification (Mock)

**Test D2-4 – Send parameters in mock mode**  
- Purpose: Confirm `send_parameters` stores settings in mock device memory.  
- Steps:
  1. `CommsService.USE_SERIAL = False`.
  2. Configure valid parameters and click “Send to Device”.  
- Expected:
  - No communication error.
  - `_mock_device_memory[mode]` equals the current `PacemakerSettings`.  
- Result: Pass.

**Test D2-5 – Read & Verify (perfect match)**  
- Purpose: Validate that device and DCM parameters match when no corruption occurs.  
- Steps:
  1. In mock mode, send parameters.
  2. Click “Read & Verify”.  
- Expected:
  - `CommsService.read_parameters(mode)` returns the stored settings.
  - Comparison finds no difference.
  - UI reports “Device parameters match DCM parameters for this mode.”  
- Result: Pass.

**Test D2-6 – Read & Verify (mismatch detection)**  
- Purpose: Ensure that mismatching fields are detected and reported.  
- Steps:
  1. In mock mode, send parameters for mode `VVI`.
  2. Manually edit `settings.json` for that user to change `upper_rate_limit` only.
  3. Restart DCM, load UI, and click “Read & Verify” for `VVI`.  
- Expected:
  - Verification lists `upper_rate_limit` as differing between local and device.  
- Result: Pass.

### 5.4 Functional Tests – Egrams

**Test D2-7 – Egram mock streaming**  
- Purpose: Confirm that mock A/V waveforms are displayed.  
- Steps:
  1. Go to Egrams tab.
  2. Click “Start” with chamber = Both.
  3. Observe canvas for a few seconds.  
- Expected:
  - Two superimposed traces (A in green, V in cyan) scroll across the canvas.  
- Result: Pass.

**Test D2-8 – Egram stop**  
- Purpose: Ensure streaming can be stopped cleanly.  
- Steps:
  1. After starting stream, click “Stop”.
  2. Wait a few seconds.  
- Expected:
  - Traces freeze; no new data is drawn.  
- Result: Pass.

---

## 6. GenAI Usage

GenAI was used in this project primarily to:

- Help brainstorm a clean modular structure for the Python DCM (models/services/UI).
- Draft initial versions of boilerplate code (e.g., Tkinter layout, dataclasses, and simple services).
- Suggest validation rules consistent with the PACEMAKER Table 7 specification.
- Assist in wording documentation (such as this design document) more clearly and concisely.

All generated code and text was **reviewed, edited, and integrated manually** by the team to ensure:

- Correctness with respect to course requirements
- Alignment with our Simulink model and hardware design
- Consistent naming and architecture across the repository

GenAI accelerated development but did **not** replace design, integration, or testing efforts.

---

## 7. Summary

This DCM implementation provides a **complete and extensible foundation** for Deliverables 1 and 2:

- Strong separation between data models, services, and UI.
- Clear mapping from natural-language requirements to concrete modules.
- A simple and robust serial protocol that can be implemented on the microcontroller.
- Full Table-7 parameter coverage and verification mechanisms.
- A realistic workflow for clinical configuration and monitoring, adapted to the educational setting of 3K04.

It is intentionally designed to be easy to **extend** (e.g., add DDDR-specific behaviours, advanced logging, or more
detailed egram analysis) without requiring major architecture changes.
