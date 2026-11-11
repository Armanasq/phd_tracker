from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from phd_agents.catalog import agent_spec, workflow_spec
from phd_agents.engine import scheduler_once
from phd_agents.connectivity import remember_check
from phd_agents.scheduler_preview import scheduler_preview
from phd_agents.settings import save_settings
from phd_agents.store import Store


class SchedulerPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name)/"state.sqlite3")
        self.addCleanup(self.store.close)
        self.now = datetime(2026,11,9,8,0,tzinfo=timezone.utc)

    def test_disabled_and_enabled_local_workflow(self) -> None:
        self.store.put_custom("workflow",workflow_spec({
            "id":"my_daily","agent_id":"portfolio_planner","provider_id":"ollama",
            "schedule":"daily","enabled":False
        }))
        initial={w["id"]:w for w in scheduler_preview(self.store,self.now)["workflows"]}
        self.assertEqual(initial["my_daily"]["state"],"disabled")
        self.store.put_custom("workflow",workflow_spec({
            "id":"my_daily","agent_id":"portfolio_planner","provider_id":"ollama",
            "schedule":"daily","enabled":True
        }))
        due={w["id"]:w for w in scheduler_preview(self.store,self.now)["workflows"]}["my_daily"]
        self.assertEqual(due["state"],"due")
        self.assertEqual(due["stages"][0]["provider_id"],"ollama")
        self.assertFalse(due["stages"][0]["connection_status"]=="responded")
        self.store.schedule_mark("my_daily",due["period"])
        done={w["id"]:w for w in scheduler_preview(self.store,self.now)["workflows"]}["my_daily"]
        self.assertEqual(done["state"],"already_executed")

    def test_incompatible_agent_is_neither_due_nor_scheduled(self) -> None:
        self.store.put_custom("agent", agent_spec({
            "id": "visual_only", "label": "Visual review",
            "instructions": "Inspect visual evidence.",
            "requirements": {"requires_vision": True},
        }))
        self.store.put_custom("workflow", workflow_spec({
            "id": "visual_daily", "agent_id": "visual_only", "provider_id": "ollama",
            "schedule": "daily", "enabled": True,
        }))
        result = {w["id"]: w for w in scheduler_preview(self.store, self.now)["workflows"]}["visual_daily"]
        self.assertEqual(result["state"], "model_capability_mismatch")
        self.assertFalse(result["would_attempt"])
        self.assertFalse(result["stages"][0]["capability_compatible"])
        self.assertIn("vision_input_not_implemented", result["stages"][0]["capability_blockers"])
        with patch("phd_agents.engine.run_workflow") as model:
            skipped = scheduler_once(self.store, Path(self.folder.name), now=self.now)
        self.assertIn({"workflow_id": "visual_daily", "status": "skipped",
                       "reason": "model_capability_mismatch"}, skipped)
        model.assert_not_called()
        self.assertIsNone(self.store.schedule_last("visual_daily"))
        self.assertIsNone(self.store.db.execute(
            "SELECT period FROM schedule_claims WHERE id='visual_daily'",
        ).fetchone())

    def test_cloud_needs_both_approval_and_budget(self) -> None:
        self.store.put_custom("workflow",workflow_spec({
            "id":"my_cloud","agent_id":"portfolio_planner","provider_id":"openai",
            "schedule":"daily","enabled":True,"cloud_consent":True
        }))
        result={w["id"]:w for w in scheduler_preview(self.store,self.now)["workflows"]}["my_cloud"]
        self.assertEqual(result["state"],"provider_not_approved")
        with patch.dict("os.environ",{"OPENAI_API_KEY":"synthetic-test-key"}):
            remember_check(self.store,"openai",status="responded",model="synthetic-model")
            save_settings(self.store,{"approved_cloud_providers":["openai"]})
            self.assertEqual({w["id"]:w for w in scheduler_preview(self.store,self.now)["workflows"]}["my_cloud"]["state"],"cloud_budget_disabled")
            save_settings(self.store,{"max_cloud_model_calls_per_day":2})
            self.assertEqual({w["id"]:w for w in scheduler_preview(self.store,self.now)["workflows"]}["my_cloud"]["state"],"due")
        with patch.dict("os.environ",{"OPENAI_API_KEY":""}):
            self.assertEqual({w["id"]:w for w in scheduler_preview(self.store,self.now)["workflows"]}["my_cloud"]["state"],"provider_not_approved")


if __name__=="__main__":
    unittest.main()
