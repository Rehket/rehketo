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


def test_escape_hatches_flags_blanket_but_allows_coded():
    src = (
        "x = 1  # type: ignore\n"             # blanket -> flag
        "y = 2  # type: ignore[arg-type]\n"   # coded -> ok
        "import z  # noqa\n"                   # blanket -> flag
        "import w  # noqa: F401\n"            # coded -> ok
        "a = 3  # pragma: no cover\n"         # no reason -> flag
        "b = 4  # pragma: no cover  # cli\n"  # reason -> ok
    )
    v = g._check_escape_hatches_text(g.API_SRC / "x.py", src)
    assert [x.line for x in v] == [1, 3, 5]


def test_logger_names():
    bad = "import logging\nlogging.getLogger('x')\nget_logger('lit')\n"
    v = g._check_logger_names_tree(g.API_SRC / "api" / "foo.py", _ast.parse(bad))
    assert [x.line for x in v] == [2, 3]
    ok = g._check_logger_names_tree(
        g.LOGGING_PY, _ast.parse("import logging\nlogging.getLogger('uvicorn')\n")
    )
    assert ok == []
    fine = g._check_logger_names_tree(
        g.API_SRC / "api" / "foo.py", _ast.parse("get_logger(__name__)\n")
    )
    assert fine == []


def test_getenv_outside_config():
    bad = "import os\nx = os.getenv('A')\ny = os.environ['B']\n"
    v = g._check_getenv_tree(g.API_SRC / "api" / "foo.py", _ast.parse(bad))
    assert [x.line for x in v] == [2, 3]
    assert g._check_getenv_tree(g.CONFIG_PY, _ast.parse(bad)) == []


def test_single_permission_gate():
    bad = (
        "check_permission(roles, 'a', resource_type=None, resource_id=None)\n"
        "x = ROLE_PERMISSIONS\n"
    )
    v = g._check_permission_gate_tree(g.API_SRC / "api" / "foo.py", _ast.parse(bad))
    assert [x.line for x in v] == [1, 2]
    assert g._check_permission_gate_tree(g.PERMISSIONS_DIR / "check.py", _ast.parse(bad)) == []


def test_permission_resource_id():
    bad = "perms.require('a', resource_type='conversation')\n"
    v = g._check_resource_id_tree(g.API_SRC / "api" / "foo.py", _ast.parse(bad))
    assert [x.line for x in v] == [1]
    ok = "perms.require('a', resource_type='conversation', resource_id=None)\n"
    assert g._check_resource_id_tree(g.API_SRC / "api" / "foo.py", _ast.parse(ok)) == []


def test_no_ai_attribution(tmp_path):
    good = tmp_path / "good.txt"
    good.write_text("feat: do a thing\n\nReal body.\n")
    assert g.check_no_ai_attribution(good) == []

    bad = tmp_path / "bad.txt"
    bad.write_text("feat: x\n\nCo-Authored-By: Claude <noreply@anthropic.com>\n")
    assert len(g.check_no_ai_attribution(bad)) == 1

    gen = tmp_path / "gen.txt"
    gen.write_text("fix: y\n\n\U0001f916 Generated with Claude Code\n")
    assert len(g.check_no_ai_attribution(gen)) == 1
