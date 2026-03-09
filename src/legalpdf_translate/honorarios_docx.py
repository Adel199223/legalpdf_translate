"""Deterministic DOCX generator for Requerimento de Honorarios."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Mm, Pt

from .docx_writer import resolve_noncolliding_output_path
from .user_profile import UserProfile

_PT_MONTHS = {
    1: "janeiro",
    2: "fevereiro",
    3: "março",
    4: "abril",
    5: "maio",
    6: "junho",
    7: "julho",
    8: "agosto",
    9: "setembro",
    10: "outubro",
    11: "novembro",
    12: "dezembro",
}
_INVALID_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(slots=True)
class HonorariosDraft:
    case_number: str
    word_count: int
    case_entity: str
    case_city: str
    date_pt: str
    profile: UserProfile


def format_portuguese_date(value: date) -> str:
    return f"{value.day:02d} de {_PT_MONTHS[value.month]} de {value.year:04d}"


def build_honorarios_draft(
    *,
    case_number: str,
    word_count: int,
    case_entity: str,
    case_city: str,
    profile: UserProfile,
    today: date | None = None,
) -> HonorariosDraft:
    current_date = today or date.today()
    return HonorariosDraft(
        case_number=case_number.strip(),
        word_count=int(word_count),
        case_entity=case_entity.strip(),
        case_city=case_city.strip(),
        date_pt=format_portuguese_date(current_date),
        profile=profile,
    )


def sanitize_case_number_for_filename(case_number: str) -> str:
    cleaned = _INVALID_FILENAME_RE.sub("_", case_number.strip())
    cleaned = cleaned.strip("._-")
    return cleaned or "sem_processo"


def default_honorarios_filename(case_number: str, today: date | None = None) -> str:
    current_date = today or date.today()
    slug = sanitize_case_number_for_filename(case_number)
    return f"Requerimento_Honorarios_{slug}_{current_date:%Y%m%d}.docx"


def _irs_sentence_fragment(value: str) -> str:
    cleaned = value.strip().rstrip(".")
    if cleaned.casefold() == "sem retenção":
        return "não tem retenção de IRS"
    return cleaned


def build_honorarios_paragraph_texts(draft: HonorariosDraft) -> list[tuple[str, str]]:
    profile = draft.profile
    return [
        (f"Número de processo: {draft.case_number}", "left"),
        ("", "left"),
        ("Exmo. Sr(a). Procurador(a) da república do " + draft.case_entity, "address"),
        ("", "left"),
        (f"Nome: {profile.document_name}", "left"),
        (f"Morada: {profile.postal_address}", "left"),
        ("", "left"),
        (
            "Venho por este meio requerer o pagamento dos honorários devidos, em virtude de ter sido nomeado "
            "tradutor no âmbito do processo acima identificado.",
            "left",
        ),
        (f"O documento traduzido contém {draft.word_count} palavras.", "left"),
        (
            f"Este serviço inclui a taxa IVA de {profile.iva_text} e {_irs_sentence_fragment(profile.irs_text)}.",
            "left",
        ),
        (f"O Pagamento deverá ser efetuado para o seguinte IBAN: {profile.iban}", "left"),
        ("", "left"),
        ("Melhores cumprimentos,", "left"),
        ("", "left"),
        ("Espera deferimento,", "center"),
        ("", "left"),
        (f"{draft.case_city}, {draft.date_pt}", "center"),
        ("", "left"),
        (profile.document_name, "center"),
    ]


def _set_default_font(document: Document) -> None:
    style = document.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(12)


def _configure_page(document: Document) -> None:
    section = document.sections[0]
    section.start_type = WD_SECTION_START.NEW_PAGE
    section.page_width = Mm(210)
    section.page_height = Mm(297)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)


def generate_honorarios_docx(draft: HonorariosDraft, output_path: Path) -> Path:
    requested_output = output_path.expanduser().resolve()
    requested_output.parent.mkdir(parents=True, exist_ok=True)
    if requested_output.exists():
        fallback_output = requested_output.parent / default_honorarios_filename(draft.case_number)
        output = resolve_noncolliding_output_path(fallback_output)
    else:
        output = requested_output

    document = Document()
    _configure_page(document)
    _set_default_font(document)

    for text, kind in build_honorarios_paragraph_texts(draft):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(0)
        if kind == "center":
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif kind == "address":
            paragraph.paragraph_format.left_indent = Cm(9.0)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        else:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        run = paragraph.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(12)

    document.save(output)
    return output
