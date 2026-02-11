import pytest

from legalpdf_translate.page_selection import resolve_page_selection


def test_resolve_page_selection_full_range() -> None:
    assert resolve_page_selection(5, 1, None, None) == [1, 2, 3, 4, 5]


def test_resolve_page_selection_with_end_and_max_pages() -> None:
    assert resolve_page_selection(10, 3, 8, 3) == [3, 4, 5]


def test_resolve_page_selection_validates_start_end_bounds() -> None:
    with pytest.raises(ValueError):
        resolve_page_selection(10, 5, 4, None)
    with pytest.raises(ValueError):
        resolve_page_selection(10, 1, 11, None)
    with pytest.raises(ValueError):
        resolve_page_selection(10, 0, None, None)


def test_resolve_page_selection_validates_max_pages() -> None:
    with pytest.raises(ValueError):
        resolve_page_selection(10, 1, 3, 0)
