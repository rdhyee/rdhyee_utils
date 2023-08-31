import pytest

# add two directories up to sys.path
import sys
from pathlib import Path as P

# add rdhyee_utils to sys.path explicitly
# don't assume that rdhyee_utils is in the PYTHONPATH

p = P(__file__).parents[3]
sys.path.append(str(p))  # noqa: E402

from rdhyee_utils.clipboard.macos import (
    PasteboardTypes,
    PTYPES,
    GeneralPasteboard,
    PasteboardItem,
    ptypes,
)


def test_correct_path():
    assert p == P("/Users/raymondyee/C/src/rdhyee_utils")


def test_divide_by_zero() -> None:
    """
    This test should fail -- it's here to teach Raymond about pytest.raises
    """
    with pytest.raises(ZeroDivisionError):
        1 / 0


class TestPastBoardTypes:
    def test_derived_ptypes(self):
        """
        make sure the derived ptypes are the same as what is hardcoded
        as PTYPES
        """
        assert set(PasteboardTypes().ptypes) == set(PTYPES)

    def test_singleton(self):
        assert PasteboardTypes() == PasteboardTypes()

    def test_abbreviations(self):
        """
        make sure the abbreviations are the same as what is hardcoded
        as ABBR_TYPES
        """
        assert set(PasteboardTypes().ABBR_TYPES) == set(ptypes.ABBR_TYPES)


class TestGeneralPasteboard:
    @pytest.fixture
    def gpb(self):
        pb = GeneralPasteboard()
        return pb

    def test_get_types(self, gpb):
        """
        access the types property and make sure it doesn't throw an exception
        """
        gpb.get_types()
        assert True

    def test_get_string(self, gpb):
        """
        access the types property and make sure it doesn't throw an exception
        """
        gpb.get_string()
        assert True

    def test_get_data(self, gpb):
        """
        access the types property and make sure it doesn't throw an exception
        """
        gpb.get_data()
        assert True

    def test_get_property_list(self, gpb):
        """
        access the types property and make sure it doesn't throw an exception
        """
        gpb.get_property_list()
        assert True

    def test_set_content(self, gpb):
        """
        access the types property and make sure it doesn't throw an exception
        """
        content_list = [
            PasteboardItem(
                [
                    ("public.utf8-plain-text", "Hello, World!"),
                    ("public.html", "<html><body><h1>Hello, World!</h1></body></html>"),
                    (
                        "public.rtf",
                        b"{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Times New Roman;}}\\f0 Hello, World!}",
                    ),
                ]
            )
        ]
        gpb.set_content(content_list)

        assert gpb.get_string(ptypes.ABBR_TYPES["String"]) == "Hello, World!"
        assert (
            gpb.get_string(ptypes.ABBR_TYPES["HTML"])
            == "<html><body><h1>Hello, World!</h1></body></html>"
        )
        assert gpb.get_data(ptypes.ABBR_TYPES["String"]) == b"Hello, World!"
        assert (
            gpb.get_data(ptypes.ABBR_TYPES["RTF"])
            == b"{\\rtf1\\ansi\\deff0 {\\fonttbl {\\f0 Times New Roman;}}\\f0 Hello, World!}"
        )
