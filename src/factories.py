from typing import Protocol

from src.protocols import StorageBackend


class BackendFactory(Protocol):
    """Creates a StorageBackend from config namespace."""

    @classmethod
    def from_namespace(cls, namespace: dict) -> StorageBackend:
        """
        Build a complete StorageBackend from a config namespace.

        Args:
            namespace: Backend-specific configuration dict

        Returns:
            Configured StorageBackend instance
        """
        ...

    @classmethod
    def required_fields(cls) -> list[str]:
        """Fields that must be present in the config namespace."""
        ...


class BackendRegistry:
    """
    Singleton registry for storage backends.

    Usage:
        registry = BackendRegistry()
        registry.register("yandex", yandex_backend)
        registry.get("yandex")  # returns StorageBackend
    """

    _instance = None
    _factories: dict[str, type[BackendFactory]] = {}
    _backends: dict[str, StorageBackend] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(self, name: str, backend: StorageBackend) -> None:
        """Register a pre-built StorageBackend."""
        self._backends[name] = backend

    def register_factory(self, name: str, factory: type[BackendFactory]) -> None:
        """Register a backend factory class."""
        self._factories[name] = factory

    def get(self, name: str) -> StorageBackend | None:
        """Get a registered backend by name."""
        return self._backends.get(name)

    def get_factory(self, name: str) -> type[BackendFactory] | None:
        """Get a registered factory class by name."""
        return self._factories.get(name)

    def list_registered(self) -> list[str]:
        """List all registered backend names."""
        return list(self._factories.keys()) + list(self._backends.keys())

    def clear(self) -> None:
        """Clear all registrations. Useful for testing."""
        self._factories.clear()
        self._backends.clear()


def register_backend(name: str):
    """
    Decorator to register a backend factory.

    Usage:
        @register_backend("yandex")
        class YandexFactory:
            ...
    """
    def decorator(cls: type[BackendFactory]) -> type[BackendFactory]:
        BackendRegistry().register_factory(name, cls)
        return cls
    return decorator


def get_registry() -> BackendRegistry:
    """Get the global BackendRegistry instance."""
    return BackendRegistry()
