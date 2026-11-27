# Panel and table reading order

A one-page fictional form deliberately paints its text out of reading order. Each of two separately outlined panels has a heading, condition and deadline. A variant adds a full-width closing box below both. The human reference for this example reads all of the left panel (labels 1, 2, 3), then the right panel (4, 5, 6), then the closing (7) when present. A separate ruled table uses labels 1–6 in row order. These are the intended relations of these fixtures.

| Fixture | Human reference | Extracted text order |
| --- | --- | --- |
| Panels on the same baselines | 1 2 3 4 5 6 | 1 4 2 5 3 6 |
| Same, with closing | 1 2 3 4 5 6 7 | 1 4 2 5 3 6 7 |
| Right panel text 32 pt lower | 1 2 3 4 5 6 | 1 2 3 4 5 6 |
| Same offset, with closing | 1 2 3 4 5 6 7 | 1 2 3 7 4 5 6 |
| Ruled three-row, two-column table | 1 2 3 4 5 6 | 1 3 5 2 4 6 |

The structured table extractor assigned all six labels to the intended cells, in row and column order. The flat text can therefore lose a relationship that the application already knows how to recover from geometry. In this sample, shifting only the right panel text changes how the page-wide column heuristic groups blocks, and a closing line can move ahead of the right panel.

Run this block in PowerShell from a checkout with its prepared project virtual environment. It generates five PDFs in a temporary directory and exercises the source extraction and table mapping code offline.

```powershell
@'
from pathlib import Path
from tempfile import TemporaryDirectory
import sys

import fitz

sys.path.insert(0, str(Path("src").resolve()))
from legalpdf_translate.document_structure import structure_from_ordered
from legalpdf_translate.pdf_text_order import extract_ordered_page_text


def panels(page, offset, closing):
    labels = ["Parte norte", "Condicao norte", "Prazo norte",
              "Parte sul", "Condicao sul", "Prazo sul", "Fim das duas partes"]
    for x in (35, 325):
        page.draw_rect(fitz.Rect(x, 120, x + 230, 415), width=1.5)
    if closing:
        page.draw_rect(fitz.Rect(35, 500, 555, 555), width=1.5)
    xy = [(53, 160), (53, 240), (53, 325),
          (344, 160 + offset), (344, 240 + offset), (344, 325 + offset),
          (53, 534)]
    for i in (6, 5, 2, 4, 1, 3, 0):
        if i != 6 or closing:
            page.insert_text(xy[i], labels[i], fontsize=13)
    return labels if closing else labels[:6]


def table(page):
    labels = ["Norte", "Sul", "Prazo", "Modo", "Locais", "Pessoas"]
    for x in (40, 300, 555):
        page.draw_line((x, 120), (x, 360))
    for y in (120, 200, 280, 360):
        page.draw_line((40, y), (555, y))
    for i in (5, 2, 4, 1, 3, 0):
        page.insert_text((53 if i % 2 == 0 else 324, 155 + 80 * (i // 2)),
                         labels[i], fontsize=13)
    return labels


with TemporaryDirectory() as scratch:
    for name, offset, closing in [("level", 0, False), ("level-close", 0, True),
                                  ("offset", 32, False), ("offset-close", 32, True),
                                  ("table", 0, False)]:
        path = Path(scratch) / (name + ".pdf")
        with fitz.open() as pdf:
            page = pdf.new_page(width=600, height=800)
            labels = table(page) if name == "table" else panels(page, offset, closing)
            pdf.save(path)
        ordered = extract_ordered_page_text(path, 0, preserve_structure=True)
        assert all(ordered.text.count(label) == 1 for label in labels), name
        sequence = sorted(range(1, len(labels) + 1),
                          key=lambda n: ordered.text.index(labels[n - 1]))
        print(name, sequence)
        if name == "table":
            structure = structure_from_ordered(ordered, page_number=1)
            cells = sorted((b.row, b.col, labels.index(b.text) + 1)
                           for b in structure.blocks if b.role == "table_cell")
            print("table cells (row, column, label)", cells)
'@ | .\.venv311\Scripts\python.exe -B -
```

On November 2, 2026, the example produced the table above on local `main` at `3ed81b7` and the W10/V19 working copy based on the same commit. Cell coordinates were `(0,0,1), (0,1,2), (1,0,3), (1,1,4), (2,0,5), (2,1,6)`.

A separate W10 ordinary browser Start on the level panels with a closing sent the interleaved text alongside the source image. With a scripted translation and layout provider it returned an editable DOCX in the scripted correct text order. These measurements localize a source-text ordering problem. Live model behavior, Arabic translation quality and native Word rendering require their own evidence.

## What survives in the source geometry

### November 2 blind follow-up

We froze two arms before scoring eight new fictional Portuguese documents from four families (ten pages). The advisory asserted none of the 26 expected ownership relationships, none of the 26 ordering judgments and none of the six expected cell ownerships. It asserted no wrong link among 21 excluded links and two genuinely ambiguous assignments. The baseline's extracted text ordered 17 pairs correctly, reversed five, and left four unobserved. Falling back to that baseline retained its five reversals. **The advisory failed its usefulness criterion and was stopped.**

The most informative failure was a page on which the app already found all six native table cells. The advisory required every text block on the page to belong to the table. Two ordinary paragraphs outside it caused the advisory to discard the cells. This locates the limitation in the proposed rule. It does not establish a mistranslation by an actual model. A separate check using the retained Arabic source acquisition options produced identical text and images on all eight digital pages. The two image-only pages remain outside that check.

A historical ordinary Portuguese-to-Arabic output also shows why semantic content and structure need separate review. Three distinct source paragraphs became one editable paragraph even though their words and sentence order survived. In a separate Portuguese-to-English example, a paid layout proposal selected centering for six body paragraphs and the writer preserved that explicit choice. Both are historical native evidence. Neither establishes fresh behavior on W10. No new provider charges were incurred for this comparison.

Private evidence lives under `nov02_structure_holdout_01` (input freeze `0c3d755f`, blind score `ae83203a`) and `nov02_structure_experiment_01` (source and protocol freeze `7c917658`, historical trace and results). The documents used for this decision are now known examples.

On both builds, `PageStructure` merges the level panel lines into three row-wise blocks, each containing text from both panels. With actual rendered page pixels, `derive_page_layout` classifies both pages as ordinary flow without a warning. The closing text survives as its own block, but its relationship to both panels is lost. The ruled grid retains all six explicit cell owners. [PDF block construction](../../../src/legalpdf_translate/pdf_text_order.py#L280) · [Table extraction](../../../src/legalpdf_translate/pdf_text_order.py#L438) · [`structure_from_ordered`](../../../src/legalpdf_translate/document_structure.py#L378) · [`derive_page_layout`](../../../src/legalpdf_translate/document_layout.py#L445)

| Synthetic geometry | Observation from original PDF line bounds and vector paths |
| --- | --- |
| Two disjoint outlined panels | Each outline uniquely owns its three text lines. |
| Same panels and full-width closing | The closing outline uniquely owns line 7, below both panels. |
| Ruled 3 × 2 grid | The table detector finds three rows and two columns. |
| Two overlapping outlines | Abstain. A line can have competing owners. |
| Two outlines sharing an edge | Abstain. The divider could describe one table. |
| Aligned text without outlines | Abstain. Line coordinates alone do not decide ownership. |

This shadow comparison used no case text, model calls or Word rendering. It establishes recoverable containment on the generated pages. Intended reading order still comes from the human reference. Scans, missing or concealed rules, rotated pages and unfamiliar forms need separate evidence.

### Independent check with two new fictional pages

A second reviewer fixed the expected relations and hashed two PDFs and the exact diagnostic before executing it. In the first fixture, one tall task panel sat beside two stacked task panels. It recovered all five heading-to-instruction relationships. Ordinary extraction already had the correct reading order on that page, so the result shows no gain in text order.

In the assignment register, the left outlined column listed three tasks and the right outlined column listed their three owners. Its headings made the intended pairing across rows explicit. The diagnostic grouped each column correctly as a physical rectangle, recovered **zero of the three task-to-owner links**, and did not abstain. Rectangle membership is therefore evidence of placement only. Automatic semantic ownership would need independent label/row evidence or abstention.

The [preregistered inputs and expected relationships](READING_ORDER_CONTROLS.json) include each rectangle and the text at each coordinate. The specification SHA-256 starts `88f8360d`, frozen snippet `d963f53c`, task-panel PDF `153b49ec` and assignment-register PDF `34e2b743`. These cases are now known regression examples. They are no longer unseen examples for a later experiment.

To repeat the comparison using the first example, work in a copy of its PowerShell block. Keep the `level`, `level-close` and `table` cases and replace the two offset cases with `("overlap", 0, False)`, `("touch", 0, False)` and `("unruled", 0, False)`. In `panels`, replace the first two drawing lines with this indented block. The outer loop provides `name`.

```python
    boxes = {"overlap": [(35, 385), (325, 555)],
             "touch": [(35, 295), (295, 555)], "unruled": []}
    for left, right in boxes.get(name, [(35, 265), (325, 555)]):
        page.draw_rect(fitz.Rect(left, 120, right, 415), width=1.5)
```

Immediately after the call to `extract_ordered_page_text` insert the following at the same indentation. The diagnostic accepts only disjoint, separately stroked rectangles that each enclose text and uniquely own every line. An identified grid takes precedence.

```python
        from legalpdf_translate.document_layout import derive_page_layout

        structure = structure_from_ordered(ordered, page_number=1)
        with fitz.open(path) as pdf:
            page = pdf[0]
            layout = derive_page_layout(structure, page.get_pixmap().tobytes("png"))
            grid = any(t.row_count >= 2 and t.col_count >= 2
                       for t in page.find_tables().tables)
            boxes = [d["items"][0][1] for d in page.get_drawings()
                     if d["type"] == "s" and len(d["items"]) == 1
                     and d["items"][0][0] == "re"]
            lines = [(fitz.Rect(line["bbox"]), "".join(s["text"] for s in line["spans"]))
                     for block in page.get_text("dict")["blocks"]
                     for line in block.get("lines", [])]
            collide = any(a.intersects(b) or
                          (min(a.y1, b.y1) > max(a.y0, b.y0)
                           and (abs(a.x1 - b.x0) < .01 or abs(a.x0 - b.x1) < .01))
                          for i, a in enumerate(boxes) for b in boxes[i + 1:])
            groups = [[labels.index(text) + 1 for line, text in
                       sorted(lines, key=lambda pair: (pair[0].y0, pair[0].x0))
                       if box.contains(line)]
                      for box in sorted(boxes, key=lambda b: (b.y0, b.x0))]
            unique = all(sum(box.contains(line) for box in boxes) == 1 for line, _ in lines)
            result = "abstain"
            if grid:
                result = "grid"
            elif boxes and not collide and unique and all(groups):
                result = groups
            print(name, layout["status"], result)
```
