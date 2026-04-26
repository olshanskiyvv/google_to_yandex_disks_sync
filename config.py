import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_ENV_VAR_RE = re.compile(r"\$\{([^}]+)\}")


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${ENV_VAR} placeholders in config values."""
    if isinstance(value, str):
        for var_name in _ENV_VAR_RE.findall(value):
            env_value = os.getenv(var_name, "")
            value = value.replace(f"${{{var_name}}}", env_value)
        return value
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


@dataclass
class FolderDef:
    """A folder definition pointing to a backend and path."""

    backend: str
    path: str


@dataclass
class SyncPair:
    """A sync pair defining source and target folders."""

    source: str
    target: str


@dataclass
class AppConfig:
    """
    Application configuration loaded from YAML files.

    Priority order:
    1. config.yaml - base configuration
    2. Environment variables - used for ${ENV_VAR} resolution
    """

    backends: dict[str, dict] = field(default_factory=dict)
    folders: dict[str, FolderDef] = field(default_factory=dict)
    sync_pairs: list[SyncPair] = field(default_factory=list)
    logging: dict = field(default_factory=dict)

    @classmethod
    def load(cls, config_path: str = "config.yaml", sync_path: str = "sync.yaml") -> "AppConfig":
        """
        Load configuration from YAML files.

        Args:
            config_path: Path to config.yaml (backends + logging)
            sync_path: Path to sync.yaml (folders + sync pairs)

        Returns:
            AppConfig instance
        """
        load_dotenv()

        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        sync_file = Path(sync_path)
        if not sync_file.exists():
            raise FileNotFoundError(f"Sync file not found: {sync_path}")

        with open(config_file) as f:
            base_config = yaml.safe_load(f) or {}

        with open(sync_file) as f:
            sync_config = yaml.safe_load(f) or {}

        backends = base_config.get("backends", {})

        config = cls()
        
        # Resolve environment variables
        config.backends = _resolve_env_vars(backends)
        config.logging = _resolve_env_vars(base_config.get("logging", {}))

        # Parse folders and sync pairs from sync.yaml
        folders_raw = sync_config.get("folders", {})
        config.folders = {
            name: FolderDef(
                backend=folder_data["backend"],
                path=folder_data["path"],
            )
            for name, folder_data in folders_raw.items()
        }

        sync_pairs_raw = sync_config.get("sync_pairs", [])
        config.sync_pairs = [
            SyncPair(source=pair["source"], target=pair["target"])
            for pair in sync_pairs_raw
        ]

        return config

    def validate(self) -> list[str]:
        """
        Validate configuration.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate backends have required fields
        for name, backend_config in self.backends.items():
            if name == "google":
                if "credentials_file" not in backend_config:
                    errors.append("Backend 'google' missing 'credentials_file'")
            elif name == "yandex":
                if "token" not in backend_config or not backend_config["token"]:
                    errors.append("Backend 'yandex' missing valid 'token'")
            elif name == "local":
                if "root" not in backend_config:
                    errors.append("Backend 'local' missing 'root'")

        # Validate folders reference existing backends
        for name, folder in self.folders.items():
            if folder.backend not in self.backends:
                errors.append(f"Folder '{name}' references unknown backend '{folder.backend}'")

        # Validate sync pairs reference existing folders
        folder_names = set(self.folders.keys())
        for i, pair in enumerate(self.sync_pairs):
            if pair.source not in folder_names:
                errors.append(f"Sync pair {i}: source '{pair.source}' not found in folders")
            if pair.target not in folder_names:
                errors.append(f"Sync pair {i}: target '{pair.target}' not found in folders")

        return errors


# Global config instance
_config: AppConfig | None = None


def load_config(config_path: str = "config.yaml", sync_path: str = "sync.yaml") -> AppConfig:
    """Load and validate configuration."""
    global _config
    _config = AppConfig.load(config_path, sync_path)

    errors = _config.validate()
    if errors:
        raise ValueError("Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    return _config


def get_config() -> AppConfig:
    """Get the loaded configuration."""
    if _config is None:
        return load_config()
    return _config
