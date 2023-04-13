from rdhyee_utils import grouper


def test_grouper():
    assert list(grouper(range(10), 4)) == [[0, 1, 2, 3], [4, 5, 6, 7], [8, 9]]
