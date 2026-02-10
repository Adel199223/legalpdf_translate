import fitz

from legalpdf_translate.pdf_text_order import (
    TextBlock,
    build_text_blocks_from_page_dict,
    get_page_count,
    order_text_blocks,
)


def test_build_text_blocks_sorts_internal_lines() -> None:
    page_dict = {
        "blocks": [
            {
                "type": 0,
                "bbox": [0, 0, 100, 100],
                "lines": [
                    {"bbox": [0, 20, 0, 0], "spans": [{"text": "line2"}]},
                    {"bbox": [0, 10, 0, 0], "spans": [{"text": "line1"}]},
                ],
            }
        ]
    }
    blocks = build_text_blocks_from_page_dict(page_dict)
    assert len(blocks) == 1
    assert blocks[0].text == "line1\nline2"


def test_order_text_blocks_groups_header_barcode_body_footer() -> None:
    blocks = [
        TextBlock(x0=10, y0=10, x1=300, y1=40, text="Tribunal Judicial da Comarca"),
        TextBlock(x0=15, y0=45, x1=350, y1=70, text="%*RE12345*%"),
        TextBlock(x0=20, y0=200, x1=380, y1=260, text="Corpo do documento"),
        TextBlock(x0=25, y0=940, x1=400, y1=980, text="Indicar na resposta..."),
    ]
    ordered = order_text_blocks(blocks, page_width=500, page_height=1000)
    assert ordered.split("\n") == [
        "Tribunal Judicial da Comarca",
        "%*RE12345*%",
        "Corpo do documento",
        "Indicar na resposta...",
    ]


def test_two_column_body_orders_left_then_right() -> None:
    blocks = [
        TextBlock(x0=40, y0=100, x1=250, y1=140, text="L1"),
        TextBlock(x0=45, y0=200, x1=255, y1=240, text="L2"),
        TextBlock(x0=360, y0=110, x1=560, y1=150, text="R1"),
        TextBlock(x0=365, y0=210, x1=565, y1=250, text="R2"),
    ]
    ordered = order_text_blocks(blocks, page_width=600, page_height=1000)
    assert ordered.split("\n") == ["L1", "L2", "R1", "R2"]


def test_get_page_count_reads_pdf_pages(tmp_path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.new_page()
    doc.new_page()
    doc.save(pdf_path)
    doc.close()

    assert get_page_count(pdf_path) == 3
