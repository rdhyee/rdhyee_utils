import pytest
import applescript
from appscript import app, k, its

# add two directories up to sys.path
import sys
import pathlib
from pathlib import Path as P

# add rdhyee_utils to sys.path explicitly
# don't assume that rdhyee_utils is in the PYTHONPATH

p = P(__file__).parents[2]
sys.path.append(str(p))  # noqa: E402

from rdhyee_utils.bike import Bike


def test_divide_by_zero() -> None:
    """
    This test should fail -- it's here to teach Raymond about pytest.raises
    """
    with pytest.raises(ZeroDivisionError):
        1 / 0


class TestBikeApp:
    @pytest.fixture
    def bike(self):
        bike = Bike()
        return bike

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

    def test_name(self, bike):
        """
        making sure the console client can view an identifier
        """
        assert bike.name == "Bike"

    def test_windows(self, bike):
        """
        making sure the console client can view an identifier
        """
        bike.windows

    def test_documents(self, bike):
        """
        making sure the console client can view an identifier
        """
        bike.documents
