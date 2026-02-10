from legalpdf_translate.validators import parse_code_block_output


def test_single_code_block_with_whitespace_outside_is_ok_shape() -> None:
    raw = "\n  ```\nhello\nworld\n```\n\t"
    parsed = parse_code_block_output(raw)
    assert parsed.block_count == 1
    assert parsed.inner_content == "hello\nworld\n"
    assert parsed.outside_has_non_whitespace is False


def test_single_code_block_with_non_whitespace_outside_is_defect() -> None:
    raw = "prefix\n```text\nhello\n```\nsuffix"
    parsed = parse_code_block_output(raw)
    assert parsed.block_count == 1
    assert parsed.inner_content is not None
    assert parsed.outside_has_non_whitespace is True


def test_zero_code_block_fails_shape() -> None:
    parsed = parse_code_block_output("no fences here")
    assert parsed.block_count == 0
    assert parsed.inner_content is None


def test_multiple_code_blocks_fail_shape() -> None:
    raw = "```a\none\n```\n```b\ntwo\n```"
    parsed = parse_code_block_output(raw)
    assert parsed.block_count == 2
    assert parsed.inner_content is None
