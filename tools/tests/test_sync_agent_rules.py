import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sync_agent_rules as sync  # noqa: E402

COMPLETE = "\n".join(s + "\n\nbody\n" for s in sync.REQUIRED_SECTIONS)


def test_render_produces_three_targets():
    rendered = sync.render(body=COMPLETE)
    names = {p.name for p in rendered}
    assert names == {"CLAUDE.md", "copilot-instructions.md", "main.mdc"}


def test_render_rejects_missing_section():
    bad = COMPLETE.replace(sync.REQUIRED_SECTIONS[0], "## Something else")
    try:
        sync.render(body=bad)
    except SystemExit as e:
        assert "missing required sections" in str(e)
    else:
        raise AssertionError("expected SystemExit")


def test_every_mirror_carries_the_generated_note():
    for content in sync.render(body=COMPLETE).values():
        assert sync.GENERATED_NOTE in content
