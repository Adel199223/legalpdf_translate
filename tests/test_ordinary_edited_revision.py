"""Meaningful-content boundaries for native Word formatting adoption."""
from io import BytesIO
from zipfile import ZipFile

from lxml import etree
import pytest

from legalpdf_translate.ordinary_edited_revision import qualify_edited_docx
from legalpdf_translate.ordinary_layout_contracts import OrdinaryLayoutError

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def element(tag, **attributes):
    return etree.Element(W + tag, {W + k: str(v) for k, v in attributes.items()})


def document(*, reference=None, style=False):
    root = element("document")
    body = etree.SubElement(root, W + "body")
    p = etree.SubElement(body, W + "p")
    if style:
        props = etree.SubElement(p, W + "pPr")
        props.append(element("bidi"))
        props.append(element("jc", val="right"))
    run = etree.SubElement(p, W + "r")
    etree.SubElement(run, W + "t").text = "Unchanged fictional wording."
    if reference:
        run.append(element(reference[0], id=reference[1]))
    return root


def separator(note_kind, *, continuation=False):
    kind = "continuationSeparator" if continuation else "separator"
    note = element(note_kind, type=kind, id=0 if continuation else -1)
    p = etree.SubElement(note, W + "p")
    props = etree.SubElement(p, W + "pPr")
    props.append(element("spacing", after=0, line=240, lineRule="auto"))
    run = etree.SubElement(p, W + "r")
    run.append(element(kind))
    return note


def user_note(note_kind, *, note_id=1, text="Real fictional note."):
    note = element(note_kind, id=note_id)
    p = etree.SubElement(note, W + "p")
    r = etree.SubElement(p, W + "r")
    etree.SubElement(r, W + "t").text = text
    return note


def package(doc=None, **stories):
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", etree.tostring(document() if doc is None else doc))
        for name, root in stories.items():
            archive.writestr("word/" + name + ".xml", etree.tostring(root))
    return output.getvalue()


def story(note_kind, *notes):
    root = element(note_kind + "s")
    root.extend(notes)
    return root


def reject(before, after):
    with pytest.raises(OrdinaryLayoutError, match="edited_layout_rebase_required"):
        qualify_edited_docx(before, after)


def test_word_generated_empty_reserved_note_stories_allow_unchanged_rtl_edit():
    before = package()
    after = package(document(style=True),
        footnotes=story("footnote", separator("footnote"), separator("footnote", continuation=True)),
        endnotes=story("endnote", separator("endnote"), separator("endnote", continuation=True)))
    qualify_edited_docx(before, after)


@pytest.mark.parametrize("kind", ["footnote", "endnote"])
def test_system_separator_insertion_preserves_existing_real_note_ownership(kind):
    before = package(**{kind + "s": story(kind, user_note(kind))})
    after = package(document(style=True), **{kind + "s": story(kind,
        separator(kind), separator(kind, continuation=True), user_note(kind))})
    qualify_edited_docx(before, after)


@pytest.mark.parametrize("kind", ["footnote", "endnote"])
@pytest.mark.parametrize("mutation", ["text", "field", "object", "reference", "wrong_id", "wrong_type", "extra_control"])
def test_nonempty_or_nonstandard_separator_note_cannot_disappear(kind, mutation):
    note = separator(kind)
    run = note.find(".//" + W + "r")
    if mutation == "text":
        etree.SubElement(run, W + "t").text = "Meaningful added note."
    elif mutation == "field":
        etree.SubElement(run, W + "instrText").text = " PAGE "
    elif mutation == "object":
        run.append(element("drawing"))
    elif mutation == "reference":
        run.append(element(kind + "Reference", id=1))
    elif mutation == "wrong_id":
        note.set(W + "id", "4")
    elif mutation == "wrong_type":
        note.set(W + "type", "normal")
    else:
        run.append(element("tab"))
    reject(package(), package(**{kind + "s": story(kind, note)}))


@pytest.mark.parametrize("kind", ["footnote", "endnote"])
@pytest.mark.parametrize("change", ["text", "id", "field", "object", "tab"])
def test_real_note_content_id_and_controls_remain_protected(kind, change):
    before = package(**{kind + "s": story(kind, user_note(kind))})
    note = user_note(kind)
    run = note.find(".//" + W + "r")
    if change == "text":
        run.find(W + "t").text = "Changed fictional note."
    elif change == "id":
        note.set(W + "id", "2")
    elif change == "field":
        run.append(element("fldChar", fldCharType="begin"))
    elif change == "object":
        run.append(element("object"))
    else:
        run.append(element("tab"))
    reject(before, package(**{kind + "s": story(kind, note)}))


@pytest.mark.parametrize("kind", ["footnote", "endnote"])
def test_real_note_reference_addition_or_id_change_is_protected(kind):
    reject(package(), package(document(reference=(kind + "Reference", 1))))
    reject(package(document(reference=(kind + "Reference", 1))),
           package(document(reference=(kind + "Reference", 2))))


@pytest.mark.parametrize("name", ["footnotes", "endnotes", "comments", "header1"])
def test_arbitrary_new_empty_story_is_not_ignored(name):
    reject(package(), package(**{name: element(name)}))


def test_nonstandard_note_controls_remain_exact_even_without_text():
    before_note = separator("footnote")
    before_note.set(W + "id", "4")
    after_note = separator("footnote")
    after_note.set(W + "id", "4")
    after_note.find(".//" + W + "separator").set(W + "val", "changed")
    reject(package(footnotes=story("footnote", before_note)),
           package(footnotes=story("footnote", after_note)))


@pytest.mark.parametrize("mutation", ["nesting", "paragraph_attribute", "run_attribute", "root_attribute"])
def test_unrecognized_system_note_shape_is_not_ignored(mutation):
    note = separator("footnote")
    root = story("footnote", note)
    if mutation == "nesting":
        run = note.find(".//" + W + "r")
        control = run[0]
        run.remove(control)
        note.find(".//" + W + "spacing").append(control)
    elif mutation == "paragraph_attribute":
        note[0].set(W + "unknown", "1")
    elif mutation == "run_attribute":
        note.find(".//" + W + "r").set(W + "unknown", "1")
    else:
        root.set(W + "unknown", "1")
    reject(package(), package(footnotes=root))


def test_word_system_note_metadata_is_neutral():
    note = separator("footnote")
    note[0].set(W + "rsidR", "12345678")
    note[0].set("{http://schemas.microsoft.com/office/word/2010/wordml}paraId", "12345678")
    root = story("footnote", note)
    root.set("{http://schemas.openxmlformats.org/markup-compatibility/2006}Ignorable", "w14")
    qualify_edited_docx(package(), package(footnotes=root))


@pytest.mark.parametrize("kind", ["footnote", "endnote"])
def test_real_note_and_reference_removal_are_protected(kind):
    reject(package(**{kind + "s": story(kind, user_note(kind))}), package())
    reject(package(document(reference=(kind + "Reference", 1))), package())
