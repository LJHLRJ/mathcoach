"""先修关系：存在性、无环、不允许自指。"""
import pytest

from mathcoach.content.validator import ValidationError, validate_prerequisites


def test_happy_path():
    prereq = {"hs-002": ["hs-001"], "hs-003": ["hs-002"]}
    cards = ["hs-001", "hs-002", "hs-003"]
    validate_prerequisites(prereq, cards)  # 不抛异常


def test_unknown_ancestor_rejected():
    prereq = {"hs-002": ["hs-999"]}
    with pytest.raises(ValidationError):
        validate_prerequisites(prereq, ["hs-002"])


def test_cycle_rejected():
    prereq = {"hs-001": ["hs-002"], "hs-002": ["hs-001"]}
    with pytest.raises(ValidationError):
        validate_prerequisites(prereq, ["hs-001", "hs-002"])


def test_self_reference_rejected():
    prereq = {"hs-001": ["hs-001"]}
    with pytest.raises(ValidationError):
        validate_prerequisites(prereq, ["hs-001"])
