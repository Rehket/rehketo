import ast as _ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import agent_guards as g  # noqa: E402


def test_check_runs_clean_on_real_tree():
    # The whole point: the real source must pass all file checks.
    assert g.main(["check"]) == 0


def test_violation_render_is_path_line_message():
    v = g.Violation(g.API_SRC / "x.py", 7, "boom")
    assert v.render() == "rehketo-api/rehketo/x.py:7: boom"
