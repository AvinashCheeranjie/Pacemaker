# Pacemaker DCM (Device Controller–Monitor)

This project implements a **Python/Tkinter Device Controller–Monitor (DCM)** for the 3K04 Pacemaker project, covering
Deliverable 1 and Deliverable 2 requirements for the DCM:

- User login and registration (max 10 users)
- Mode selection and programmable parameter editing
- Full Table-7 parameter model (`PacemakerSettings`)
- Simple, robust serial protocol for parameter transmission and verification
- Real-time egram display from A/V chambers (mock or serial)
- JSON-backed local storage for users and last-used settings
- Clear separation of concerns via models, services, and UI modules

See `docs/DCM_Deliverable_Documentation.md` for full design, requirements, and testing documentation.
