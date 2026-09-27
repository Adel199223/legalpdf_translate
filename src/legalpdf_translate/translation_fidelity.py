"""Shared source-faithful guidance for ordinary and structured translation.

This is prompt guidance, not a semantic validator or a text-replacement rule.
It does not change the source, output protocol, or protected literal contract.
"""

FIDELITY_GUIDANCE_VERSION = "legal_effect_and_visual_text_v1"

FIDELITY_GUIDANCE = (
    "SOURCE MEANING AND VISUAL TEXT FIDELITY\n"
    "Preserve each clause's speaker, actor, tense, evidential certainty, conditions and legal effect. "
    "Distinguish facts from allegations, inferences, uncertainty, requests and future acts. "
    "Portuguese future or conditional forms can express an inference about the present: "
    "retain that uncertainty when the context supports it, rather than asserting a certain fact. "
    "Do not weaken a condition that must actually occur into a mere possibility, or state that "
    "a requested act has already been completed. Keep conditional deadlines attached to their trigger.\n"
    "Translate procedural expressions in their source context. In a direction to the registry, "
    "'abrir conclusão' or submitting the 'autos conclusos' means placing the case file before "
    "the responsible judicial authority for consideration or a ruling; it does not by itself "
    "mean closing, dismissing or archiving the case. Preserve an actual direction to archive "
    "when that is what the source says. Do not invent expansions of an uncertain acronym.\n"
    "For page images, preserve human-readable source content and meaningful reading order. "
    "Do not manufacture barcode-font scaffolding around a readable tracking identifier. "
    "Barcode bars and font-control glyphs are graphics, not words. Preserve punctuation that "
    "is actually part of the readable identifier. Use the standard Unicode bullet for a visible "
    "round list bullet, not a font-dependent private-use glyph; preserve numbered list labels. "
    "Keep a personal name or postal address as a coherent verbatim span under the selected "
    "language's literal rules, without splitting its internal words merely for line wrapping.\n"
    "Before returning the translation, compare these distinctions with the original assigned "
    "source, including the image when supplied. Correct meaning against that source, never "
    "against an assumed outcome. These instructions do not authorize adding translator notes, "
    "new headings, signatures or source text that is not present."
)
