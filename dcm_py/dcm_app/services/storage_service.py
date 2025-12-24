import json
import os
import hashlib
from pathlib import Path
from typing import List, Optional

from dcm_app.models.user import User
from dcm_app.models.settings import PacemakerSettings


class StorageService:
    """Simple JSON-based local storage for users and per-user settings."""

    MAX_USERS = 50

    def __init__(self):
        base_dir = Path(os.getenv("PACEMAKER_DCM_HOME", "."))
        self._users_file = base_dir / "users.json"
        self._settings_file = base_dir / "settings.json"
        self._session_file = base_dir / "session.json"
        self._ensure_files()

    def _ensure_files(self):
        try:
            if not self._users_file.exists():
                self._users_file.write_text("[]", encoding="utf-8")
        except (IOError, OSError):
            pass
        try:
            if not self._settings_file.exists():
                self._settings_file.write_text("{}", encoding="utf-8")
        except (IOError, OSError):
            pass
        try:
            if not self._session_file.exists():
                self._session_file.write_text("{}", encoding="utf-8")
        except (IOError, OSError):
            pass

    # --- Users ---------------------------------------------------------
    def load_users(self) -> List[User]:
        try:
            content = self._users_file.read_text(encoding="utf-8").strip()
            if not content:
                return []
            data = json.loads(content)
            return [User(**u) for u in data]
        except (json.JSONDecodeError, ValueError, IOError, OSError):
            # File is corrupted or inaccessible, reinitialize it
            try:
                self._users_file.write_text("[]", encoding="utf-8")
            except (IOError, OSError):
                pass
            return []

    def save_users(self, users: List[User]) -> None:
        try:
            data = [u.__dict__ for u in users]
            self._users_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except (IOError, OSError, TypeError):
            pass

    def register_user(self, username: str, password: str) -> bool:
        try:
            users = self.load_users()
            if len(users) >= self.MAX_USERS:
                return False
            if any(u.username == username for u in users):
                return False
            # Simple hash substitute (NOT secure, but fine for project)
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            users.append(User(username=username, password_hash=pwd_hash))
            self.save_users(users)
            return True
        except Exception:
            return False

    def validate_login(self, username: str, password: str) -> bool:
        try:
            users = self.load_users()
            pwd_hash = hashlib.sha256(password.encode()).hexdigest()
            return any(u.username == username and u.password_hash == pwd_hash for u in users)
        except Exception:
            return False

    # --- Session (current user) -------------------------------------
    def get_current_user(self) -> Optional[str]:
        try:
            content = self._session_file.read_text(encoding="utf-8").strip()
            if not content:
                return None
            data = json.loads(content)
            cu = data.get("current_user")
            if isinstance(cu, str) and cu:
                return cu
            return None
        except (json.JSONDecodeError, ValueError, IOError, OSError):
            try:
                self._session_file.write_text("{}", encoding="utf-8")
            except (IOError, OSError):
                pass
            return None

    def set_current_user(self, username: Optional[str]) -> None:
        try:
            if not username:
                self._session_file.write_text("{}", encoding="utf-8")
                return
            data = {"current_user": username}
            self._session_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except (IOError, OSError, TypeError):
            pass

    # --- Settings ------------------------------------------------------
    def load_settings(self, username: str) -> Optional[PacemakerSettings]:
        try:
            content = self._settings_file.read_text(encoding="utf-8").strip()
            if not content:
                return None
            data = json.loads(content)
            if username not in data:
                return None
            return PacemakerSettings.from_dict(data[username])
        except (json.JSONDecodeError, ValueError, IOError, OSError):
            # File is corrupted or inaccessible, reinitialize it
            try:
                self._settings_file.write_text("{}", encoding="utf-8")
            except (IOError, OSError):
                pass
            return None

    def save_settings(self, settings: PacemakerSettings) -> None:
        try:
            content = self._settings_file.read_text(encoding="utf-8").strip()
            if not content:
                data = {}
            else:
                data = json.loads(content)
            data[settings.owner_username] = settings.to_dict()
            self._settings_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except (json.JSONDecodeError, ValueError, IOError, OSError):
            pass