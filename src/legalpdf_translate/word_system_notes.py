"""Strict reserved Word separator furniture; no meaningful note content."""
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def system_separator_note(note, note_tag):
    """Only Word's empty reserved separator entries are serialization furniture."""
    controls = {("separator", "-1"): "separator", ("continuationSeparator", "0"): "continuationSeparator"}
    control = controls.get((note.get(_W + "type"), note.get(_W + "id")))
    if (note.tag != note_tag or control is None
            or set(note.attrib) != {_W + "type", _W + "id"}):
        return False
    if len(note) != 1 or note[0].tag != _W + "p":
        return False
    paragraph = note[0]
    metadata = {_W + key for key in ("rsidR", "rsidRDefault", "rsidP", "rsidRPr", "rsidDel")}
    metadata.update("{http://schemas.microsoft.com/office/word/2010/wordml}" + key
                    for key in ("paraId", "textId"))
    children = list(paragraph)
    if children and children[0].tag == _W + "pPr":
        properties = children.pop(0)
        if (properties.attrib or len(properties) > 1
                or any(child.tag != _W + "spacing" or len(child)
                       or set(child.attrib) - {_W + key for key in (
                           "before", "after", "line", "lineRule", "beforeAutospacing",
                           "afterAutospacing", "beforeLines", "afterLines")}
                       for child in properties)):
            return False
    if (set(paragraph.attrib) - metadata or len(children) != 1
            or children[0].tag != _W + "r" or children[0].attrib
            or len(children[0]) != 1 or children[0][0].tag != _W + control
            or children[0][0].attrib or len(children[0][0])):
        return False
    return all(not (node.text or "").strip() and not (node.tail or "").strip()
               for node in note.iter())

