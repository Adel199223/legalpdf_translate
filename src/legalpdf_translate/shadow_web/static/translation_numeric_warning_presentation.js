export const NUMERIC_MISMATCH_WARNING_MESSAGE = "Review recommended: some numbers from the source may not appear exactly in the translation.";

export function blankTranslationNumericMismatchWarning({ checked = false } = {}) {
  return {
    visible: false,
    checked,
    message: NUMERIC_MISMATCH_WARNING_MESSAGE,
    lines: [],
    pages: [],
  };
}

function coercePositiveInt(value) {
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function cleanNumericSample(value) {
  return String(value ?? "")
    .trim()
    .replace(/^['"`]+|['"`]+$/g, "")
    .trim();
}

function normalizeNumericSamples(value) {
  if (Array.isArray(value)) {
    return value.map(cleanNumericSample).filter(Boolean).slice(0, 6);
  }
  const text = String(value ?? "").trim();
  if (!text) {
    return [];
  }
  const trimmed = text.replace(/^\[/, "").replace(/\]$/, "");
  const quoted = Array.from(trimmed.matchAll(/["']([^"']+)["']/g))
    .map((match) => cleanNumericSample(match[1]))
    .filter(Boolean);
  if (quoted.length) {
    return quoted.slice(0, 6);
  }
  const separator = trimmed.includes(";") ? /\s*;\s*/ : /,\s+/;
  const parts = (trimmed.includes(";") || /,\s+/.test(trimmed))
    ? trimmed.split(separator)
    : [trimmed];
  return parts
    .map(cleanNumericSample)
    .filter(Boolean)
    .slice(0, 6);
}

function normalizeNumericWarningRows(rows = []) {
  const normalizedRows = [];
  for (const row of rows) {
    if (!row || typeof row !== "object") {
      continue;
    }
    const samples = normalizeNumericSamples(row.samples ?? row.numeric_missing_sample ?? row.missing);
    const count = coercePositiveInt(row.count ?? row.numeric_mismatches_count) ?? samples.length;
    if (count <= 0 && samples.length === 0) {
      continue;
    }
    const page = coercePositiveInt(row.page ?? row.page_index ?? row.page_number);
    normalizedRows.push({
      page,
      count,
      samples,
    });
  }
  const lines = normalizedRows.map((row) => {
    const prefix = row.page ? `Page ${row.page}: ` : "";
    if (row.samples.length) {
      return `${prefix}${row.samples.join("; ")}`;
    }
    const countText = row.count === 1 ? "1 number needs review" : `${row.count} numbers need review`;
    return `${prefix}${countText}`;
  });
  return {
    visible: lines.length > 0,
    checked: true,
    message: NUMERIC_MISMATCH_WARNING_MESSAGE,
    lines,
    pages: normalizedRows,
  };
}

function collectNumericWarningRows(value, rows = [], seen = new Set(), depth = 0) {
  if (!value || typeof value !== "object" || seen.has(value) || depth > 7) {
    return rows;
  }
  seen.add(value);
  if (Array.isArray(value)) {
    value.forEach((item) => collectNumericWarningRows(item, rows, seen, depth + 1));
    return rows;
  }
  const samples = normalizeNumericSamples(value.samples ?? value.numeric_missing_sample ?? value.missing);
  const count = coercePositiveInt(value.count ?? value.numeric_mismatches_count) ?? 0;
  if (count > 0 || samples.length > 0) {
    rows.push({
      page: value.page_index ?? value.page ?? value.page_number,
      count,
      samples,
    });
  }
  for (const [key, nested] of Object.entries(value)) {
    if (
      key === "save_seed"
      || key === "logs"
      || key.endsWith("_path")
      || key.endsWith("_dir")
    ) {
      continue;
    }
    collectNumericWarningRows(nested, rows, seen, depth + 1);
  }
  return rows;
}

function extractNumericMismatchWarningFromText(text) {
  const source = String(text || "");
  if (!source) {
    return blankTranslationNumericMismatchWarning();
  }
  const rows = [];
  const lines = source.split(/\r?\n/);
  let inSamples = false;
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (/^#{1,6}\s+Numeric Mismatch Samples/i.test(line)) {
      inSamples = true;
      continue;
    }
    if (inSamples && /^#{1,6}\s+/.test(line)) {
      break;
    }
    const match = line.match(/^-?\s*Page\s+(?<page>\d+)\s*:\s*(?:missing\s*)?(?<samples>\[[^\]]*\]|.+)$/i);
    if (!match?.groups) {
      continue;
    }
    rows.push({
      page: match.groups.page,
      samples: normalizeNumericSamples(match.groups.samples),
    });
  }
  return normalizeNumericWarningRows(rows);
}

export function deriveTranslationNumericMismatchWarning({
  job = null,
  extra = null,
  cachedWarning = null,
} = {}) {
  const rows = collectNumericWarningRows(extra || job || []);
  const structured = normalizeNumericWarningRows(rows);
  if (structured.visible) {
    return structured;
  }
  const previewText = String(
    extra?.preview || extra?.normalized_payload?.preview || job?.result?.run_report_preview || "",
  ).trim();
  const previewWarning = extractNumericMismatchWarningFromText(previewText);
  if (previewWarning.visible) {
    return previewWarning;
  }
  if (cachedWarning) {
    return cachedWarning;
  }
  return blankTranslationNumericMismatchWarning();
}
