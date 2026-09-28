import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def generator():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_powerbi_project.py"
    spec = importlib.util.spec_from_file_location("dashboard_generator", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_existing_project_is_not_overwritten(generator, tmp_path):
    report = tmp_path / "user-report.pbip"
    report.write_bytes(b"existing user work")
    with pytest.raises(SystemExit):
        generator.main(["--output", str(tmp_path)])
    assert report.read_bytes() == b"existing user work"
    assert list(tmp_path.iterdir()) == [report]


def test_rejects_measure_column_collision_case_insensitively(generator):
    columns = [("Evaluated Users", "users", "int64", "#,0", None, False)]
    with pytest.raises(ValueError, match="Duplicate"):
        generator.table_tmdl(
            "Protocol", "protocol", columns, [("evaluated users", "1", "#,0")]
        )


def test_review_generation_does_not_touch_sibling_report(generator, tmp_path):
    original = tmp_path / "powerbi" / "model" / ".pbi" / "cache.abf"
    original.parent.mkdir(parents=True)
    original.write_bytes(b"saved user cache")
    review = tmp_path / "review"
    assert generator.main(["--output", str(review)]) == 0
    assert original.read_bytes() == b"saved user cache"
    assert len(list(review.rglob("visual.json"))) == 35
    assert len(list(review.rglob("tables/*.tmdl"))) == 8
