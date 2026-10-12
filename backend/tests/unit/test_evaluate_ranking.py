import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location(
    "evaluate_ranking", Path(__file__).resolve().parents[2] / "scripts" / "evaluate_ranking.py"
)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)  # type: ignore[union-attr]


def src(instrument, text="", section=None):
    return SimpleNamespace(instrument=instrument, text=text, section=section)


def test_hit_rules() -> None:
    assert ev.is_hit(src("Negotiable Instruments Act, 1881", section="138"), {"instrument": "Negotiable Instruments", "section": "138"})
    assert not ev.is_hit(src("Negotiable Instruments Act, 1881", section="142"), {"instrument": "Negotiable", "section": "138"})
    assert ev.is_hit(src("Indian Penal Code (IPC)", "On  THEFT and"), {"instrument": "Indian Penal Code", "contains": ["theft"]})
    assert not ev.is_hit(src("Contract Act", "theft"), {"instrument": "Indian Penal Code", "contains": ["theft"]})
    repealed = {"instrument": "Code of Criminal Procedure", "section": "437",
                "or": [{"instrument": "Bharatiya Nagarik Suraksha Sanhita", "section": "480"}]}
    assert ev.is_hit(src("Bharatiya Nagarik Suraksha Sanhita, 2023", section="480"), repealed)
    assert ev.is_hit(src("Code of Criminal Procedure, 1973", section="437"), repealed)
    assert not ev.is_hit(src("Bharatiya Nagarik Suraksha Sanhita, 2023", section="483"), repealed)


def test_metrics() -> None:
    m = ev.metrics([1, 2, None, 5])
    assert m == {"n": 4, "hit@1": 0.25, "hit@3": 0.5, "hit@5": 0.75, "mrr": round((1 + 0.5 + 0.2) / 4, 3)}


def test_report_groups_by_type_and_flags() -> None:
    questions = [
        {"id": "a", "type": "law", "exact_reference": True},
        {"id": "b", "type": "other", "differently_worded": True, "language": "ta"},
    ]
    rep = ev.report(questions, {"a": 1, "b": None})
    assert rep["metrics"]["exact_reference"]["hit@1"] == 1.0
    assert rep["metrics"]["differently_worded"]["hit@5"] == 0.0
    assert set(rep["metrics"]) >= {"all", "type:law", "type:other", "language:en", "language:ta"}
