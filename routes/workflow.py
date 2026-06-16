"""Career workflow API — step-by-step job search guide."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from config.settings import load_config
from core.career_workflow import (
    WORKFLOW_STEPS,
    analyze_jobs,
    analyze_recruiters,
    analyze_references,
    apply_search_suggestions,
    check_readiness,
    get_manual_prompts,
    load_workflow_state,
    mark_step_complete,
    set_current_step,
    store_analysis,
)
from core.i18n import get_locale

logger = logging.getLogger(__name__)

workflow_bp = Blueprint("workflow", __name__)


@workflow_bp.route("/api/workflow/status", methods=["GET"])
def workflow_status():
    state = load_workflow_state()
    config = load_config()
    readiness = check_readiness(config)
    completed = state.get("completed_steps", [])
    return jsonify({
        "steps_total": WORKFLOW_STEPS,
        "current_step": state.get("current_step", 1),
        "completed_steps": completed,
        "workflow_complete": len(completed) >= WORKFLOW_STEPS,
        "readiness": readiness,
        "analyses": state.get("analyses", {}),
    })


@workflow_bp.route("/api/workflow/step", methods=["PUT"])
def workflow_set_step():
    data = request.get_json(force=True) or {}
    step = int(data.get("step", 1))
    if data.get("complete"):
        state = mark_step_complete(step)
    else:
        state = set_current_step(step)
    return jsonify({"success": True, **state})


@workflow_bp.route("/api/workflow/prompts", methods=["GET"])
def workflow_prompts():
    locale = request.args.get("locale") or get_locale()
    return jsonify(get_manual_prompts(locale))


@workflow_bp.route("/api/workflow/analyze/jobs", methods=["POST"])
def workflow_analyze_jobs():
    config = load_config()
    if not config:
        return jsonify({"error": "complete_setup_first"}), 400

    readiness = check_readiness(config)
    if not readiness["ready_for_analysis"]:
        return jsonify({"error": "profile_incomplete", "readiness": readiness}), 400

    locale = request.args.get("locale") or get_locale()

    if not readiness["ai_available"]:
        prompts = get_manual_prompts(locale)
        result = {
            "mode": "manual",
            "prompt": prompts["jobs"],
            "message": "use_claude_extension",
        }
        store_analysis("jobs", result)
        return jsonify(result)

    try:
        result = analyze_jobs(config, locale)
        store_analysis("jobs", result)
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Job analysis failed")
        return jsonify({"error": "analysis_failed", "detail": str(e)}), 500


@workflow_bp.route("/api/workflow/analyze/recruiters", methods=["POST"])
def workflow_analyze_recruiters():
    config = load_config()
    if not config:
        return jsonify({"error": "complete_setup_first"}), 400

    locale = request.args.get("locale") or get_locale()
    readiness = check_readiness(config)

    if not readiness["ai_available"]:
        prompts = get_manual_prompts(locale)
        result = {"mode": "manual", "prompt": prompts["recruiters"], "message": "use_claude_extension"}
        store_analysis("recruiters", result)
        return jsonify(result)

    try:
        result = analyze_recruiters(config, locale)
        store_analysis("recruiters", result)
        return jsonify(result)
    except Exception as e:
        logger.exception("Recruiter analysis failed")
        return jsonify({"error": "analysis_failed", "detail": str(e)}), 500


@workflow_bp.route("/api/workflow/analyze/references", methods=["POST"])
def workflow_analyze_references():
    config = load_config()
    if not config:
        return jsonify({"error": "complete_setup_first"}), 400

    locale = request.args.get("locale") or get_locale()
    readiness = check_readiness(config)

    if not readiness["ai_available"]:
        prompts = get_manual_prompts(locale)
        result = {"mode": "manual", "prompt": prompts["references"], "message": "use_claude_extension"}
        store_analysis("references", result)
        return jsonify(result)

    try:
        result = analyze_references(config, locale)
        store_analysis("references", result)
        return jsonify(result)
    except Exception as e:
        logger.exception("Reference analysis failed")
        return jsonify({"error": "analysis_failed", "detail": str(e)}), 500


@workflow_bp.route("/api/workflow/apply-search", methods=["POST"])
def workflow_apply_search():
    config = load_config()
    if not config:
        return jsonify({"error": "complete_setup_first"}), 400

    data = request.get_json(force=True) or {}
    config = apply_search_suggestions(
        config,
        titles=data.get("titles"),
        keywords=data.get("keywords"),
        locations=data.get("locations"),
    )
    mark_step_complete(3)
    return jsonify({
        "success": True,
        "search_criteria": config.search_criteria.model_dump(),
    })
