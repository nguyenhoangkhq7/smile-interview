from typing import List
import pytest

from src.baselines.base import (
    BaselineInput,
    BaselineMethod,
    BaselineOutputField,
    BaselineSkillResult,
)
from src.baselines.registry import BaselineRegistry


class DummyBaseline(BaselineMethod):
    """Lớp baseline giả lập phục vụ kiểm thử registry."""

    def __init__(self, name: str, output_fields: frozenset[BaselineOutputField]) -> None:
        self._name = name
        self._fields = output_fields

    @property
    def name(self) -> str:
        return self._name

    @property
    def produces(self) -> frozenset[BaselineOutputField]:
        return self._fields

    def run(self, input_data: BaselineInput) -> List[BaselineSkillResult]:
        return []


def test_registry_registration_and_lookup() -> None:
    """Kiểm tra đăng ký và tra cứu baseline thành công."""
    registry = BaselineRegistry()
    b1 = DummyBaseline(name="baseline_a", output_fields=frozenset({BaselineOutputField.ALIGNMENT}))
    b2 = DummyBaseline(name="baseline_b", output_fields=frozenset({BaselineOutputField.GAP_MAGNITUDE}))

    registry.register(b1)
    registry.register(b2)

    assert registry.get("baseline_a") is b1
    assert registry.get("baseline_b") is b2
    assert registry.list_available() == ["baseline_a", "baseline_b"]


def test_registry_duplicate_registration_raises_error() -> None:
    """Kiểm tra việc đăng ký trùng tên baseline sẽ ném ngoại lệ ValueError."""
    registry = BaselineRegistry()
    b1 = DummyBaseline(name="same_name", output_fields=frozenset({BaselineOutputField.ALIGNMENT}))
    b2 = DummyBaseline(name="same_name", output_fields=frozenset({BaselineOutputField.GAP_MAGNITUDE}))

    registry.register(b1)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(b2)


def test_registry_get_nonexistent_raises_error() -> None:
    """Kiểm tra việc tra cứu baseline không tồn tại sẽ ném ngoại lệ KeyError."""
    registry = BaselineRegistry()
    with pytest.raises(KeyError, match="not found"):
        registry.get("non_existent")


def test_registry_invalid_type_raises_type_error() -> None:
    """Kiểm tra việc đăng ký một đối tượng không phải BaselineMethod sẽ ném TypeError."""
    registry = BaselineRegistry()
    with pytest.raises(TypeError, match="Expected BaselineMethod"):
        registry.register("not_a_baseline")  # type: ignore[arg-type]


def test_registry_empty_name_raises_value_error() -> None:
    """Kiểm tra việc đăng ký baseline có tên rỗng sẽ ném ValueError."""
    registry = BaselineRegistry()
    b_empty = DummyBaseline(name="", output_fields=frozenset())
    with pytest.raises(ValueError, match="cannot be empty"):
        registry.register(b_empty)


def test_registry_clear() -> None:
    """Kiểm tra phương thức clear xóa sạch toàn bộ registry."""
    registry = BaselineRegistry()
    b = DummyBaseline(name="temp", output_fields=frozenset())
    registry.register(b)
    assert len(registry.list_available()) == 1

    registry.clear()
    assert len(registry.list_available()) == 0
    assert registry.list_available() == []
