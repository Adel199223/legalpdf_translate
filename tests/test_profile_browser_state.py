from __future__ import annotations

from .browser_esm_probe import run_browser_esm_json_probe


def _probe_results() -> dict[str, object]:
    script = """
const profileModule = await import(__PROFILE_MODULE_URL__);

const mainProfile = {
  id: "primary",
  first_name: "Ana",
  last_name: "Silva",
  document_name: "Ana Silva",
  email: "ana@example.com",
  phone_number: "+351 123 456",
  travel_origin_label: "Beja",
  travel_distances_by_city: {
    " Lisboa ": "178",
    "Serpa": 32,
    "serpa": 40,
    "Zero": 0,
    "Broken": "oops",
  },
  is_primary: true,
};

let blankCityError = "";
let invalidDistanceError = "";
try {
  profileModule.upsertDistanceRow([], "   ", "12");
} catch (error) {
  blankCityError = error.message;
}
try {
  profileModule.upsertDistanceRow([], "Lisboa", "0");
} catch (error) {
  invalidDistanceError = error.message;
}

const normalizedRows = profileModule.normalizeDistanceRows({
  " Lisboa ": "178",
  "Serpa": 32,
  "": 10,
  "Zero": 0,
  "Broken": "nope",
});
const updatedRows = profileModule.upsertDistanceRow(
  [{ city: "Lisboa", distanceKm: 178 }, { city: "Serpa", distanceKm: 32 }],
  " lisboa ",
  "180",
);
const removedRows = profileModule.removeDistanceRow(updatedRows, "serpa");
const parsedJsonRows = profileModule.parseDistanceRowsFromJson('{" Beja ": "39", "Cuba": 26}');
const serializedRows = profileModule.serializeDistanceRows(parsedJsonRows);
const mainProfilePresentation = profileModule.deriveProfilePresentation(mainProfile);
const helperText = [
  profileModule.formatProfileCountStatus(0),
  profileModule.formatProfileCountStatus(3),
  profileModule.formatDistanceSummary(parsedJsonRows),
  JSON.stringify(mainProfilePresentation),
  JSON.stringify(parsedJsonRows),
  blankCityError,
  invalidDistanceError,
].join(" ");

console.log(JSON.stringify({
  zeroStatus: profileModule.formatProfileCountStatus(0),
  multiStatus: profileModule.formatProfileCountStatus(3),
  mainProfilePresentation,
  normalizedRows,
  updatedRows,
  removedRows,
  blankCityError,
  invalidDistanceError,
  parsedJsonRows,
  serializedRows,
  helperText,
}));
"""
    return run_browser_esm_json_probe(
        script,
        {"__PROFILE_MODULE_URL__": "profile_presentation.js"},
        timeout_seconds=20,
    )


def test_profile_presentation_helper_uses_beginner_setup_copy() -> None:
    payload = _probe_results()

    assert payload["zeroStatus"] == "No main profile is set yet. Add a profile or choose one from the list."
    assert payload["multiStatus"] == "3 profile(s) ready."

    presentation = payload["mainProfilePresentation"]
    assert presentation["displayName"] == "Ana Silva"
    assert presentation["contactSummary"] == "ana@example.com | +351 123 456"
    assert presentation["travelOriginSummary"] == "Travel origin: Beja"
    assert presentation["distanceSummary"] == "2 saved city distances."
    assert presentation["mainChipLabel"] == "Main profile"
    assert presentation["useAsMainLabel"] == "Main profile"
    assert presentation["editorStatus"] == "Editing Ana Silva. Update the details, then save."
    assert presentation["deleteConfirmMessage"] == "Delete this profile? This cannot be undone."

    assert payload["normalizedRows"] == [
        {"city": "Lisboa", "distanceKm": 178, "distanceLabel": "178 km one way"},
        {"city": "Serpa", "distanceKm": 32, "distanceLabel": "32 km one way"},
    ]
    assert payload["updatedRows"] == [
        {"city": "Lisboa", "distanceKm": 180, "distanceLabel": "180 km one way"},
        {"city": "Serpa", "distanceKm": 32, "distanceLabel": "32 km one way"},
    ]
    assert payload["removedRows"] == [
        {"city": "Lisboa", "distanceKm": 180, "distanceLabel": "180 km one way"},
    ]
    assert payload["blankCityError"] == "Enter a city before adding a distance."
    assert payload["invalidDistanceError"] == "Enter a positive one-way distance in km."
    assert payload["parsedJsonRows"] == [
        {"city": "Beja", "distanceKm": 39, "distanceLabel": "39 km one way"},
        {"city": "Cuba", "distanceKm": 26, "distanceLabel": "26 km one way"},
    ]
    assert payload["serializedRows"] == {"Beja": 39, "Cuba": 26}

    helper_text = payload["helperText"]
    assert "bounded" not in helper_text
    assert "runtime mode" not in helper_text
    assert "Travel Distances JSON" not in helper_text
    assert "Set Primary" not in helper_text
