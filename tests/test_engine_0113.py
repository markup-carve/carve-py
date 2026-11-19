"""Task states exposed by the 0.1.13 engine."""

import carve
import pytest

pytestmark = pytest.mark.skip(reason="0.1 engine readings; 0.2 examples run in test_v2_conformance")


def test_task_states_render_and_preserve_markers():
    for marker in ("/", "!", "_"):
        source = f"- [{marker}] task\n"
        assert f'data-task-state="{marker}"' in carve.to_html(source)
        assert carve.to_carve(source) == source
