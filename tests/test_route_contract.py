from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phd_agents.catalog import agent_spec, provider_spec, workflow_spec
from phd_agents.engine import run_agent, run_workflow, workflow_plan
from phd_agents.route_contract import (
    adapter_capabilities, assess_provider_contract, normalize_requirements,
)
from phd_agents.store import Store


class CapabilityContractTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.store = Store(self.root / "owner.sqlite3")
        self.addCleanup(self.store.close)

    def test_adapter_claims_are_conservative_and_versioned(self) -> None:
        provider = {"id": "local", "kind": "openai_compatible", "max_output_tokens": 1200}
        contract = assess_provider_contract(provider)
        self.assertTrue(contract["compatible"])
        self.assertTrue(contract["adapter"]["native_sse_adapter"])
        self.assertFalse(contract["adapter"]["native_tool_calling"])
        self.assertFalse(contract["adapter"]["json_schema_output"])
        self.assertFalse(contract["adapter"]["vision_input"])
        self.assertEqual(contract["requirements"]["schema_version"], 1)
        self.assertFalse(assess_provider_contract(
            {"**": True, "kind": "anthropic", "max_output_tokens": 1200},
            stream_requested=True,
        )["compatible"])

    def test_invalid_requirements_fail_at_catalog_update(self) -> None:
        basic = {"id": "new_agent", "label": "New", "instructions": "Inspect evidence."}
        for requirements in (
            {"min_output_tokens": True}, {"min_output_tokens": 5},
            {"requires_vision": "yes"}, {"native_tools": True}, {"min_output_tokens": 20000},
        ):
            with self.subTest(requirements=requirements), self.assertRaises(ValueError):
                agent_spec({**basic, "requirements": requirements})
        saved = agent_spec({**basic, "requirements": {"min_output_tokens": 1200}})
        self.assertEqual(saved["requirements"]["min_output_tokens"], 1200)
        self.assertFalse(saved["requirements"]["requires_vision"])

    def test_preflight_rejects_capability_mismatch_before_any_model_call(self) -> None:
        self.store.put_custom("agent", agent_spec({
            "id": "vision_agent", "label": "Vision", "instructions": "Inspect screenshots.",
            "requirements": {"requires_vision": True, "min_output_tokens": 128},
        }))
        self.store.put_custom("workflow", workflow_spec({
            "id": "vision_flow", "agent_id": "vision_agent", "schedule": "manual",
            "steps": ["vision_agent"], "provider_id": "ollama",
        }))
        preview = workflow_plan(self.store, workflow_id="vision_flow")
        self.assertFalse(preview["manual_ready"])
        self.assertFalse(preview["execution_ready"])
        self.assertEqual(preview["compatibility_blockers"],
                         ["stage_1_vision_input_not_implemented"])
        self.assertFalse(preview["stages"][0]["capability_contract"]["compatible"])
        with patch("phd_agents.engine.invoke") as model:
            with self.assertRaisesRegex(ValueError, "capability mismatch"):
                run_workflow(self.store, self.root, workflow_id="vision_flow")
            with self.assertRaisesRegex(ValueError, "Incompatible agent model route"):
                run_agent(self.store, self.root, agent_id="vision_agent",
                          provider_id="ollama", input_text="Inspect")
            model.assert_not_called()
        self.assertEqual(self.store.runs(), [])

    def test_token_constraints_and_native_capabilities_are_not_inferred(self) -> None:
        provider = {"id": "tiny", "kind": "anthropic", "max_output_tokens": 256}
        blocked = assess_provider_contract(provider, {
            "min_output_tokens": 512, "requires_native_tools": True,
            "requires_structured_output": True,
        }, stream_requested=True)
        self.assertEqual(set(blocked["blockers"]), {
            "output_token_limit_below_agent_minimum",
            "native_tool_calling_not_implemented",
            "validated_json_schema_output_not_implemented",
            "native_sse_not_supported_by_adapter",
        })
        self.assertFalse(blocked["compatible"])

    def test_existing_agents_without_requirements_remain_supported(self) -> None:
        provider = provider_spec({
            "id": "localtest", "kind": "openai_compatible",
            "base_url": "http://127.0.0.1:5000/v1", "local": True,
            "model": "test", "max_output_tokens": 512,
        })
        self.assertTrue(assess_provider_contract(provider, None)["compatible"])
        self.assertEqual(normalize_requirements()["min_output_tokens"], 64)


if __name__ == "__main__":
    unittest.main()
