"""情境目录：图形、参数集合与数值范围校验。"""
from pathlib import Path

from mathcoach.scenario import (
    CATALOG,
    SCENARIOS,
    load_scenario_catalog,
    scenario_for,
)


def _write(tmp_path: Path, name: str, body: list[str]) -> Path:
    directory = tmp_path / "scenario"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text("\n".join(body), encoding="utf-8")
    return directory


def _yaml(
    card_id: str,
    figure: str,
    params: list[str],
    extra: list[str] | None = None,
) -> list[str]:
    lines = [
        "version: 1",
        f"card_id: {card_id}",
        "title: 测试情境",
        f"figure: {figure}",
        "params:",
    ]
    lines.extend(params)
    lines.extend(extra or [])
    return lines


def test_default_catalog_has_two_scenarios():
    """仓库自带斜率与向量两个情境，且没有结构错误。"""
    assert CATALOG.errors == ()
    assert set(SCENARIOS) == {"hs-func-004", "hs-vector-002"}
    tangent = scenario_for(CATALOG, "hs-func-004")
    vector = scenario_for(CATALOG, "hs-vector-002")
    assert tangent is not None and tangent.figure == "tangent_slope"
    assert vector is not None and vector.figure == "vector_sum"


def test_unknown_figure_is_skipped(tmp_path):
    """未知图形不进入目录。"""
    directory = _write(
        tmp_path,
        "bad.yaml",
        _yaml(
            "hs-func-004",
            "unknown",
            ["  - {name: x0, min: -1, max: 1, default: 0}"],
        ),
    )
    catalog = load_scenario_catalog(directory)

    assert catalog.scenarios == {}
    assert any("未知图形" in error for error in catalog.errors)


def test_missing_or_extra_params_are_rejected(tmp_path):
    """参数集合必须与图形匹配。"""
    missing = _write(
        tmp_path / "missing",
        "bad.yaml",
        _yaml(
            "hs-func-004",
            "vector_sum",
            ["  - {name: x0, min: -1, max: 1, default: 0}"],
        ),
    )
    extra = _write(
        tmp_path / "extra",
        "bad.yaml",
        _yaml(
            "hs-func-004",
            "tangent_slope",
            [
                "  - {name: x0, min: -1, max: 1, default: 0}",
                "  - {name: ax, min: -1, max: 1, default: 0}",
            ],
        ),
    )

    missing_catalog = load_scenario_catalog(missing)
    extra_catalog = load_scenario_catalog(extra)
    assert missing_catalog.scenarios == {}
    assert any("需要参数" in error for error in missing_catalog.errors)
    assert extra_catalog.scenarios == {}
    assert any("需要参数" in error for error in extra_catalog.errors)


def test_invalid_range_is_rejected(tmp_path):
    """最小值不小于最大值时跳过。"""
    directory = _write(
        tmp_path,
        "bad.yaml",
        _yaml(
            "hs-func-004",
            "tangent_slope",
            ["  - {name: x0, min: 2, max: 1, default: 1}"],
        ),
    )
    catalog = load_scenario_catalog(directory)

    assert catalog.scenarios == {}
    assert any("最小值必须小于最大值" in error for error in catalog.errors)


def test_valid_scenario_loads(tmp_path):
    """结构正确的情境可以加载。"""
    directory = _write(
        tmp_path,
        "ok.yaml",
        _yaml(
            "hs-func-004",
            "tangent_slope",
            ["  - {name: x0, min: -2, max: 2, step: 0.5, default: 1}"],
            ["prompts: [观察斜率]", "bridge: 去做题"],
        ),
    )
    catalog = load_scenario_catalog(directory)

    assert catalog.errors == ()
    spec = catalog.scenarios["hs-func-004"]
    assert spec.params[0].step == 0.5
    assert spec.prompts == ("观察斜率",)
    assert spec.bridge == "去做题"
