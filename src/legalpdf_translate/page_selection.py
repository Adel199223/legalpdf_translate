"""Page selection resolution utilities."""

from __future__ import annotations


def resolve_page_selection(
    total_pages: int,
    start_page: int,
    end_page: int | None,
    max_pages: int | None,
) -> list[int]:
    if total_pages <= 0:
        raise ValueError("total_pages must be a positive integer.")
    if start_page <= 0:
        raise ValueError("start_page must be >= 1.")
    if max_pages is not None and max_pages <= 0:
        raise ValueError("max_pages must be > 0 when provided.")

    resolved_end = total_pages if end_page is None else end_page
    if resolved_end <= 0:
        raise ValueError("end_page must be >= 1 when provided.")
    if start_page > resolved_end:
        raise ValueError("start_page must be <= end_page.")
    if resolved_end > total_pages:
        raise ValueError("end_page must be <= total_pages.")
    if start_page > total_pages:
        raise ValueError("start_page must be <= total_pages.")

    selected_pages = list(range(start_page, resolved_end + 1))
    if max_pages is not None:
        selected_pages = selected_pages[:max_pages]
    return selected_pages
