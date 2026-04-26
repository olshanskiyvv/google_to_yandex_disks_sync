import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _resolve_env_vars(value: Any) -> Any:
    """Recursively resolve ${ENV_VAR} placeholders in config values."""
    if isinstance(value, str):
        pattern = re.compile(r"\$\{([^}]+)\}")
        matches = pattern.findall(value)
        for var_name in matches:
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
    1. auth.yaml (if exists) - secrets, have highest priority
    2. config.yaml - base configuration
    3. Environment variables - used for ${ENV_VAR} resolution
    """

    backends: dict[str, dict] = field(default_factory=dict)
    folders: dict[str, FolderDef] = field(default_factory=dict)
    sync_pairs: list[SyncPair] = field(default_factory=list)
    logging: dict = field(default_factory=dict)
    _auth_loaded: bool = False

    @classmethod
    def load(cls, config_path: str = "config.yaml") -> "AppConfig":
        """
        Load configuration from YAML files.

        Args:
            config_path: Path to main config.yaml

        Returns:
            AppConfig instance
        """
        config_file = Path(config_path)

        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_file) as f:
            base_config = yaml.safe_load(f) or {}

        backends = base_config.get("backends", {})

        # Load auth.yaml if exists (higher priority)
        auth_path = Path("auth.yaml")
        if auth_path.exists():
            with open(auth_path) as f:
                auth_config = yaml.safe_load(f) or {}
            for backend_name, auth_data in auth_config.items():
                if backend_name in backends:
                    backends[backend_name].update(auth_data)
                else:
                    backends[backend_name] = auth_data
            config = cls(_auth_loaded=True)
        else:
            config = cls(_auth_loaded=False)

        # Resolve environment variables
        config.backends = _resolve_env_vars(backends)
        config.logging = _resolve_env_vars(base_config.get("logging", {}))

        # Parse folders
        folders_raw = base_config.get("folders", {})
        config.folders = {
            name: FolderDef(
                backend=folder_data["backend"],
                path=folder_data["path"],
            )
            for name, folder_data in folders_raw.items()
        }

        # Parse sync pairs
        sync_pairs_raw = base_config.get("sync_pairs", [])
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
                    errors.append(f"Backend 'google' missing 'credentials_file'")
            elif name == "yandex":
                if "token" not in backend_config or not backend_config["token"]:
                    errors.append(f"Backend 'yandex' missing valid 'token'")
            elif name == "local":
                if "root" not in backend_config:
                    errors.append(f"Backend 'local' missing 'root'")

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


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """Load and validate configuration."""
    global _config
    _config = AppConfig.load(config_path)

    errors = _config.validate()
    if errors:
        raise ValueError(f"Config validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    return _config


def get_config() -> AppConfig:
    """Get the loaded configuration."""
    if _config is None:
        return load_config()
    return _config
