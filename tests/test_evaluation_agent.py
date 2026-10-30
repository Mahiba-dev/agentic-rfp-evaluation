"""Tests for proposal evaluation requests and output validation."""

from __future__ import annotations

import json
import os
import sys
import types
import unittest
from unittest.mock import Mock, patch

from src.database import EvaluationCriterion
from src.evaluation_agent import (
    EvaluationError,
    create_llm_client,
    evaluate_supplier,
)


class FakeClient:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.request: dict[str, object] | None = None
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self.create)
        )

    def create(self, **request: object) -> object:
        self.request = request
        if self.error is not None:
            raise self.error
        message = types.SimpleNamespace(content=self.content)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=message)]
        )


class EvaluationAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.criteria = [
            EvaluationCriterion(
                id=14,
                name="Delivery approach",
                weight=100.0,
                max_score=7,
                active=True,
            )
        ]
        self.result = {
            "supplier_name": "Northstar Ltd",
            "criteria": [
                {
                    "criterion_id": 14,
                    "score": 6,
                    "max_score": 7,
                    "justification": "A delivery schedule is included.",
                    "evidence": ["The rollout is planned across 12 weeks."],
                }
            ],
            "risks": ["The proposal does not identify a backup deployment window."],
            "overall_summary": "The proposal provides a credible delivery schedule.",
            "warnings": [],
        }

    def test_requests_json_and_returns_validated_dynamic_criteria(self) -> None:
        model_result = dict(self.result)
        model_result.pop("warnings")
        client = FakeClient(json.dumps(model_result))

        evaluation = evaluate_supplier(
            "Northstar Ltd",
            "The rollout is planned across 12 weeks.",
            self.criteria,
            client,
            model="test-model",
        )

        self.assertEqual(evaluation, self.result)
        self.assertEqual(client.request["model"], "test-model")
        self.assertEqual(client.request["response_format"], {"type": "json_object"})
        messages = client.request["messages"]
        prompt = messages[1]["content"]
        self.assertIn("Delivery approach", prompt)
        self.assertIn("The rollout is planned across 12 weeks.", prompt)
        self.assertIn("Do not calculate weighted totals", messages[0]["content"])

    def test_fills_missing_active_criterion_and_returns_warning(self) -> None:
        active_criteria = self.criteria + [
            EvaluationCriterion(
                id=15,
                name="Security review",
                weight=0.0,
                max_score=5,
                active=True,
            )
        ]
        result = dict(self.result)
        result.pop("warnings")

        evaluation = evaluate_supplier(
            "Northstar Ltd",
            "Proposal text",
            active_criteria,
            FakeClient(json.dumps(result)),
        )

        self.assertEqual(evaluation["criteria"][1]["score"], 0)
        self.assertTrue(any("Missing active criterion 15" in warning for warning in evaluation["warnings"]))

    def test_clips_score_above_criterion_maximum(self) -> None:
        result = json.loads(json.dumps(self.result))
        result.pop("warnings")
        result["criteria"][0]["score"] = 8

        evaluation = evaluate_supplier(
            "Northstar Ltd",
            "Proposal text",
            self.criteria,
            FakeClient(json.dumps(result)),
        )

        self.assertEqual(evaluation["criteria"][0]["score"], 7)
        self.assertTrue(any("clipped to 7" in warning for warning in evaluation["warnings"]))

    def test_rejects_ranking_fields(self) -> None:
        result = dict(self.result, rank=1)
        with self.assertRaisesRegex(EvaluationError, "rank: Extra inputs are not permitted"):
            evaluate_supplier("Northstar Ltd", "Proposal text", self.criteria, FakeClient(json.dumps(result)))

    def test_rejects_malformed_json(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "malformed JSON"):
            evaluate_supplier("Northstar Ltd", "Proposal text", self.criteria, FakeClient("not json"))

    def test_wraps_provider_api_failure(self) -> None:
        with self.assertRaisesRegex(EvaluationError, "LLM request failed"):
            evaluate_supplier(
                "Northstar Ltd",
                "Proposal text",
                self.criteria,
                FakeClient(error=RuntimeError("provider unavailable")),
            )

    def test_client_factory_reads_credentials_and_endpoint_from_environment(self) -> None:
        mock_client = Mock()
        openai_module = types.ModuleType("openai")
        openai_module.OpenAI = Mock(return_value=mock_client)
        environment = {
            "LLM_PROVIDER": "openai-compatible",
            "LLM_API_KEY": "test-secret",
            "LLM_BASE_URL": "https://llm.example.test/v1",
        }
        with patch.dict(os.environ, environment, clear=True):
            with patch.dict(sys.modules, {"openai": openai_module}):
                client = create_llm_client()

        self.assertIs(client, mock_client)
        openai_module.OpenAI.assert_called_once_with(
            api_key="test-secret",
            base_url="https://llm.example.test/v1",
        )

    def test_client_factory_accepts_explicit_credentials_and_endpoint(self) -> None:
        mock_client = Mock()
        openai_module = types.ModuleType("openai")
        openai_module.OpenAI = Mock(return_value=mock_client)
        with patch.dict(os.environ, {}, clear=True):
            with patch.dict(sys.modules, {"openai": openai_module}):
                client = create_llm_client(
                    provider="openai-compatible",
                    api_key="user-secret",
                    base_url="https://custom.example/v1",
                )

        self.assertIs(client, mock_client)
        openai_module.OpenAI.assert_called_once_with(
            api_key="user-secret",
            base_url="https://custom.example/v1",
        )

    def test_client_factory_requires_environment_credential(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(EvaluationError, "Provide an API key"):
                create_llm_client()


if __name__ == "__main__":
    unittest.main()