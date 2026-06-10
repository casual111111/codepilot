import pytest

from codepilot.tools.shell import run_tests


def test_run_tests_rejects_non_allowlisted_command():
    with pytest.raises(ValueError):
        run_tests("echo unsafe")
