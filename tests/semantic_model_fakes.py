"""Fictional HTTP transport around the actual installed OpenAI SDK."""
import json
import httpx
from openai import OpenAI
from legalpdf_translate.openai_client import OpenAIResponsesClient
from tests.semantic_review_fakes import ALL_FORMAT_NAMES, UNIT_REF_VERSIONS, review_response
from tests.test_workflow_semantic_audit_integration import PRIMARY, CORRECTED


class ModelHTTP:
    def __init__(self, mutate=None, primary_retry=False):
        self.requests, self.bodies = [], []
        self.mutate, self.primary_retry = mutate, primary_retry
        self.http = httpx.Client(transport=httpx.MockTransport(self.send))
        self.sdk = OpenAI(api_key="fictional-test-key", http_client=self.http)
        self.client = OpenAIResponsesClient(sdk_client=self.sdk, max_transport_retries=0, pre_call_jitter_seconds=0)

    def send(self, request):
        body = json.loads(request.content)
        self.requests.append(body)
        name = body.get("text", {}).get("format", {}).get("name")
        if name in ALL_FORMAT_NAMES:
            payload = json.loads(body["input"][0]["content"][0]["text"])
            value = review_response(payload,
                corrected_by_page={p["page"]: CORRECTED for p in payload.get("primary_pages", [])},
                unit_references=name in UNIT_REF_VERSIONS.values())
            text = json.dumps(value, ensure_ascii=False)
        else:
            text = "not a fenced response" if self.primary_retry and len(self.requests) == 1 else "```text\n" + PRIMARY + "\n```"
        data = {"id": f"fictional-response-{len(self.requests)}", "object": "response", "created_at": 1,
            "model": body["model"], "status": "completed", "service_tier": "default",
            "output": [{"id": "fictional-message", "type": "message", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": text, "annotations": []}]}],
            "usage": {"input_tokens": 100, "output_tokens": 60, "total_tokens": 160}}
        if body["model"] == "gpt-6-astra":
            data["usage"]["input_tokens_details"] = {"cached_tokens": 10, "cache_write_tokens": 20}
        if self.mutate: data = self.mutate(body, data)
        raw = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False).encode()
        self.bodies.append(raw)
        return httpx.Response(200, content=raw, headers={"content-type": "application/json"})
