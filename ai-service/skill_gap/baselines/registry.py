from typing import Any, Callable, Dict, List, NamedTuple, Optional
from skill_gap.baselines.base import BaselineMethod


class BaselineFactoryEntry(NamedTuple):
    factory: Callable[..., BaselineMethod]
    requires_llm: bool
    estimated_llm_calls_per_pair: int


class BaselineRegistry:
    """
    Registry for managing and discovering baseline methods.
    Supports both pre-instantiated baseline instances and lazy factories with runtime injection.
    Prevents duplicate registration and avoids large if/elif dispatch blocks (Open/Closed Principle).
    """

    def __init__(self) -> None:
        self._registry: Dict[str, BaselineMethod] = {}
        self._factories: Dict[str, BaselineFactoryEntry] = {}

    def register(self, baseline: BaselineMethod) -> None:
        """
        Register a baseline instance.
        Raises ValueError if a baseline with the same name is already registered.
        Raises TypeError if baseline is not an instance of BaselineMethod.
        """
        if not isinstance(baseline, BaselineMethod):
            raise TypeError(f"Expected BaselineMethod instance, got {type(baseline).__name__}")
        name = baseline.name
        if not name or not name.strip():
            raise ValueError("Baseline name cannot be empty.")
        if name in self._registry or name in self._factories:
            raise ValueError(f"Baseline '{name}' is already registered in registry.")
        self._registry[name] = baseline

    def register_factory(
        self,
        name: str,
        factory: Callable[..., BaselineMethod],
        requires_llm: bool = False,
        estimated_llm_calls_per_pair: int = 0,
    ) -> None:
        """
        Register a baseline factory callable.
        Allows lazy instantiation with injected runtime dependencies (e.g., llm_client, config).
        """
        if not callable(factory):
            raise TypeError("Factory must be a callable.")
        if not name or not name.strip():
            raise ValueError("Baseline name cannot be empty.")
        if name in self._registry or name in self._factories:
            raise ValueError(f"Baseline '{name}' is already registered in registry.")
        self._factories[name] = BaselineFactoryEntry(
            factory=factory,
            requires_llm=requires_llm,
            estimated_llm_calls_per_pair=estimated_llm_calls_per_pair,
        )

    def get(self, name: str, **kwargs: Any) -> BaselineMethod:
        """
        Retrieve a baseline by its registered name.
        If registered as a factory, calls the factory with provided kwargs.
        Raises KeyError if the name is not registered.
        """
        if name in self._registry:
            return self._registry[name]
        if name in self._factories:
            return self._factories[name].factory(**kwargs)
        available = ", ".join(sorted(self.list_available())) or "none"
        raise KeyError(f"Baseline '{name}' not found. Available baselines: {available}")

    def is_llm_required(self, name: str) -> bool:
        """Query whether a baseline requires LLM execution without instantiating it."""
        if name in self._registry:
            return self._registry[name].requires_llm
        if name in self._factories:
            return self._factories[name].requires_llm
        available = ", ".join(sorted(self.list_available())) or "none"
        raise KeyError(f"Baseline '{name}' not found. Available baselines: {available}")

    def get_estimated_llm_calls(self, name: str) -> int:
        """Query estimated LLM calls per pair without instantiating."""
        if name in self._registry:
            return self._registry[name].estimated_llm_calls_per_pair
        if name in self._factories:
            return self._factories[name].estimated_llm_calls_per_pair
        available = ", ".join(sorted(self.list_available())) or "none"
        raise KeyError(f"Baseline '{name}' not found. Available baselines: {available}")

    def list_available(self) -> List[str]:
        """Return a sorted list of all registered baseline names."""
        return sorted(set(self._registry.keys()) | set(self._factories.keys()))

    def clear(self) -> None:
        """Clear all registered baselines and factories. Useful for isolated unit testing."""
        self._registry.clear()
        self._factories.clear()


# Global registry instance for application-wide registration
baseline_registry = BaselineRegistry()
