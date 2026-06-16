"""Tests for career workflow module."""

from config.settings import BotConfig
from core.career_workflow import (
    WORKFLOW_STEPS,
    get_manual_prompts,
    load_workflow_state,
    mark_step_complete,
)


class TestCareerWorkflow:
    def test_manual_prompts_pt(self):
        prompts = get_manual_prompts("pt")
        assert "LinkedIn" in prompts["jobs"]
        assert "recrutadores" in prompts["recruiters"].lower()

    def test_workflow_steps(self):
        assert WORKFLOW_STEPS == 6

    def test_mark_step_complete(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "core.career_workflow.get_data_dir",
            lambda: tmp_path,
        )
        state = mark_step_complete(1)
        assert 1 in state["completed_steps"]
        assert state["current_step"] == 2

    def test_bot_defaults_review(self):
        bot = BotConfig()
        assert bot.apply_mode == "review"
        assert bot.max_applications_per_day == 15
