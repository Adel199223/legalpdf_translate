function cleanProfileText(value) {
  return String(value ?? "")
    .trim()
    .replace(/\s+/g, " ");
}

function normalizeDistanceNumber(value) {
  const raw = typeof value === "number" ? value : Number.parseFloat(String(value ?? "").trim());
  return Number.isFinite(raw) ? raw : null;
}

function distanceKey(city) {
  return cleanProfileText(city).toLocaleLowerCase();
}

function buildDisplayName(profile = {}) {
  const fullName = cleanProfileText(`${profile.first_name || ""} ${profile.last_name || ""}`);
  return cleanProfileText(profile.document_name)
    || cleanProfileText(profile.document_name_override)
    || fullName
    || cleanProfileText(profile.id)
    || "Profile";
}

function pluralize(count, singular, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export function formatProfileCountStatus(count = 0) {
  const total = Number.parseInt(String(count ?? "").trim(), 10);
  if (!Number.isFinite(total) || total <= 0) {
    return "No main profile is set yet. Add a profile or choose one from the list.";
  }
  return `${total} profile(s) ready.`;
}

export function normalizeDistanceRows(rawValue = {}) {
  const entries = Array.isArray(rawValue)
    ? rawValue.map((row) => [
      row?.city ?? row?.name ?? "",
      row?.distanceKm ?? row?.distance_km ?? row?.km ?? row?.value,
    ])
    : Object.entries(rawValue || {});
  const rows = [];
  const seen = new Set();
  for (const [cityValue, distanceValue] of entries) {
    const city = cleanProfileText(cityValue);
    const cityToken = distanceKey(city);
    if (!city || seen.has(cityToken)) {
      continue;
    }
    const distanceKm = normalizeDistanceNumber(distanceValue);
    if (!Number.isFinite(distanceKm) || distanceKm <= 0) {
      continue;
    }
    seen.add(cityToken);
    rows.push({
      city,
      distanceKm,
      distanceLabel: `${distanceKm} km one way`,
    });
  }
  return rows;
}

export function serializeDistanceRows(rows = []) {
  const serialized = {};
  for (const row of normalizeDistanceRows(rows)) {
    serialized[row.city] = row.distanceKm;
  }
  return serialized;
}

export function parseDistanceRowsFromJson(rawJson = "") {
  const trimmed = String(rawJson ?? "").trim();
  if (!trimmed) {
    return [];
  }
  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch (_error) {
    throw new Error("Advanced distance data must be valid JSON.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Advanced distance data must map city names to one-way km values.");
  }
  return normalizeDistanceRows(parsed);
}

export function upsertDistanceRow(rows = [], cityValue = "", distanceValue = "") {
  const city = cleanProfileText(cityValue);
  if (!city) {
    throw new Error("Enter a city before adding a distance.");
  }
  const distanceKm = normalizeDistanceNumber(distanceValue);
  if (!Number.isFinite(distanceKm) || distanceKm <= 0) {
    throw new Error("Enter a positive one-way distance in km.");
  }
  const normalizedRows = normalizeDistanceRows(rows);
  const existingIndex = normalizedRows.findIndex((row) => distanceKey(row.city) === distanceKey(city));
  const resolvedCity = existingIndex >= 0 ? normalizedRows[existingIndex].city : city;
  const nextRow = {
    city: resolvedCity,
    distanceKm,
    distanceLabel: `${distanceKm} km one way`,
  };
  if (existingIndex >= 0) {
    normalizedRows[existingIndex] = nextRow;
    return normalizedRows;
  }
  return [...normalizedRows, nextRow];
}

export function removeDistanceRow(rows = [], cityValue = "") {
  const cityToken = distanceKey(cityValue);
  if (!cityToken) {
    return normalizeDistanceRows(rows);
  }
  return normalizeDistanceRows(rows).filter((row) => distanceKey(row.city) !== cityToken);
}

export function formatDistanceSummary(value = 0) {
  const count = Array.isArray(value)
    ? normalizeDistanceRows(value).length
    : Number.parseInt(String(value ?? "").trim(), 10);
  if (!Number.isFinite(count) || count <= 0) {
    return "No city distances saved yet.";
  }
  return `${pluralize(count, "saved city distance")}.`;
}

export function deriveProfilePresentation(profile = {}) {
  const distanceRows = normalizeDistanceRows(profile.travel_distances_by_city || {});
  const displayName = buildDisplayName(profile);
  const contactParts = [cleanProfileText(profile.email), cleanProfileText(profile.phone_number)].filter(Boolean);
  const contactSummary = contactParts.length
    ? contactParts.join(" | ")
    : "Add email or phone details to use them in Gmail replies.";
  const travelOrigin = cleanProfileText(profile.travel_origin_label);
  return {
    displayName,
    contactSummary,
    travelOrigin,
    travelOriginSummary: travelOrigin
      ? `Travel origin: ${travelOrigin}`
      : "Travel origin not set yet.",
    distanceSummary: formatDistanceSummary(distanceRows),
    mainChipLabel: "Main profile",
    useAsMainLabel: profile.is_primary ? "Main profile" : "Use as main profile",
    editorStatus: cleanProfileText(profile.id)
      ? `Editing ${displayName}. Update the details, then save.`
      : "New profile draft. Fill the required details, then save.",
    deleteConfirmMessage: "Delete this profile? This cannot be undone.",
  };
}
