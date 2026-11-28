"""KC 前置图：加载、反向查询、未知 KC 与环检测。"""
import yaml

from mathcoach.tutor.kc_graph import KC_GRAPH, load_kc_graph


def test_builtin_graph_loads_expected_edges() -> None:
    """内置前置图无错误，并能查到跨 unit 的先修边。"""
    assert KC_GRAPH.errors == ()
    edges = KC_GRAPH.prerequisites_of("kc-hs-trig-003-f1")

    assert [edge.from_kc for edge in edges] == ["kc-hs-trig-002-f1"]
    assert edges[0].strength == "required"
    assert KC_GRAPH.prerequisites_of("kc-hs-trig-002-f1")[0].from_kc == (
        "kc-hs-trig-001-f1"
    )


def _write(path, edges) -> None:
    """写入一份前置图 YAML。"""
    path.write_text(
        yaml.safe_dump(
            {"version": 1, "edges": edges}, allow_unicode=True
        ),
        encoding="utf-8",
    )


def test_unknown_kc_is_skipped(tmp_path) -> None:
    """引用未知 KC 的边会被跳过并记录错误。"""
    _write(
        tmp_path / "graph.yaml",
        [
            {
                "from": "kc-unknown",
                "to": "kc-hs-trig-003-f1",
                "strength": "required",
                "source": "manual",
                "confidence": 1.0,
            }
        ],
    )

    graph = load_kc_graph(tmp_path / "graph.yaml")

    assert graph.prerequisites == {}
    assert any("未知 KC" in error for error in graph.errors)


def test_cycle_returns_empty_graph(tmp_path) -> None:
    """前置边成环时返回空图并记录错误。"""
    _write(
        tmp_path / "graph.yaml",
        [
            {
                "from": "kc-hs-trig-003-f1",
                "to": "kc-hs-trig-003-p1",
                "strength": "required",
                "source": "manual",
                "confidence": 1.0,
            },
            {
                "from": "kc-hs-trig-003-p1",
                "to": "kc-hs-trig-003-f1",
                "strength": "required",
                "source": "manual",
                "confidence": 1.0,
            },
        ],
    )

    graph = load_kc_graph(tmp_path / "graph.yaml")

    assert graph.prerequisites == {}
    assert any("环" in error for error in graph.errors)
