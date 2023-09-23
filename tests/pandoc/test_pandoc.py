import pytest

# add two directories up to sys.path
import sys
from pathlib import Path as P

from rdhyee_utils.pandoc.utils import run_cmd, pandoc_formats, PFormatExtensionCombo


# add rdhyee_utils to sys.path explicitly
# don't assume that rdhyee_utils is in the PYTHONPATH

p = P(__file__).parents[2]
sys.path.append(str(p))  # noqa: E402


def test_divide_by_zero() -> None:
    """
    This test should fail -- it's here to teach Raymond about pytest.raises
    """
    with pytest.raises(ZeroDivisionError):
        1 / 0


def test_run_cmd():
    result = run_cmd("echo Hello")
    assert result.stdout.decode("utf-8").strip() == "Hello"


def test_pandoc_formats():
    input_formats, output_formats = pandoc_formats()

    # Assuming markdown and html are always supported formats
    pf = pandoc_formats()
    assert "markdown" in pf["input"]
    assert "html" in pf["output"]


def test_PFormatExtensionCombo_init():
    # Test initialization using 'fmt'
    combo1 = PFormatExtensionCombo(fmt="markdown", enabled={"ext1"}, disabled={"ext2"})
    assert combo1.fmt == "markdown"
    assert combo1.enabled == {"ext1"}
    assert combo1.disabled == {"ext2"}

    # Test initialization using 'by_str'
    combo2 = PFormatExtensionCombo(by_str="markdown+ext1-ext2")
    assert combo2.fmt == "markdown"
    assert combo2.enabled == {"ext1"}
    assert combo2.disabled == {"ext2"}

    # Test error when neither 'fmt' nor 'by_str' is provided
    with pytest.raises(ValueError):
        PFormatExtensionCombo()


class TestPandoc:
    @pytest.fixture
    def pandoc(self):
        return True

    def test_true(self):
        assert True

    @pytest.mark.xfail()
    def test_false(self):
        assert False

    def test_sys_path_ok(self):
        """
        making sure the console client can view an identifier
        """
        print(sys.path)
