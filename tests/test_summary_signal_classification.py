from legalpdf_translate.workflow_components.contracts import SummarySignalInputs
from legalpdf_translate.workflow_components.summary import classify_suspected_cause


def test_transport_instability_is_not_labeled_rate_limiting() -> None:
    cause, evidence = classify_suspected_cause(
        SummarySignalInputs(
            selected_pages_count=7,
            pages_with_images=0,
            avg_image_bytes=0.0,
            total_reasoning_tokens=100,
            total_tokens=1000,
            effort_policy="fixed_high",
            pages_with_retries=0,
            rate_limit_hits=0,
            transport_retries_total=4,
        )
    )

    assert cause == "transport_instability"
    assert any("rate_limit_hits=0" in item or "transport_retries_total=4" in item for item in evidence)
