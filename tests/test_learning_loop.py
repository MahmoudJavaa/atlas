"""Tests for LearningLoopOptimizer — mocked experiments + LLM."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta


MOCK_REPORT = {
    "summary": "2 experiments evaluated. 1 positive, 1 neutral.",
    "wins": [{"experiment_id": 1, "description": "Title tag change improved position", "impact": "+3.2 positions"}],
    "losses": [],
    "neutral": [{"experiment_id": 2, "description": "Schema addition had no measurable effect"}],
    "content_engine_feedback": ["Headlines with numbers perform better in this niche"],
    "next_actions": ["Test CTA placement on locksmith pages"],
    "overall_health": "improving",
}


def make_mock_experiment(id, type, target_url, baseline_position):
    exp = MagicMock()
    exp.id = id
    exp.type = type
    exp.hypothesis = f"Test {type}"
    exp.target_url = target_url
    exp.baseline_metrics = {"avg_position": baseline_position}
    exp.result_metrics = {}
    exp.result = None
    exp.impact_score = 0.0
    exp.started_at = datetime.now(tz=None) - timedelta(days=3)
    exp.concluded_at = None
    return exp


@pytest.mark.asyncio
async def test_evaluate_experiments_positive():
    from backend.modules.learning_loop.optimizer import LearningLoopOptimizer

    exp = make_mock_experiment(1, "title_change", "https://fastlock.co.uk/locksmith/", 15.0)

    # Mock DB: return experiment and current keyword data
    mock_exp_result = MagicMock()
    mock_exp_result.scalars.return_value.all.return_value = [exp]

    kw = MagicMock()
    kw.position = 10.0  # Improved from 15 to 10

    mock_kw_result = MagicMock()
    mock_kw_result.scalars.return_value.all.return_value = [kw]

    call_count = 0
    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        return mock_exp_result if call_count == 1 else mock_kw_result

    db = AsyncMock()
    db.execute = mock_execute
    db.flush = AsyncMock()

    optimizer = LearningLoopOptimizer(db=db)

    evaluated = await optimizer._evaluate_experiments(site_id=1)

    assert len(evaluated) == 1
    assert evaluated[0]["outcome"] == "positive"
    assert evaluated[0]["position_change"] == 5.0  # 15 - 10


@pytest.mark.asyncio
async def test_generate_report():
    from backend.modules.learning_loop.optimizer import LearningLoopOptimizer

    db = AsyncMock()
    optimizer = LearningLoopOptimizer(db=db)
    optimizer.llm = MagicMock()
    optimizer.llm.generate_json.return_value = MOCK_REPORT

    experiments = [
        {"id": 1, "type": "title_change", "outcome": "positive", "position_change": 5.0, "impact_score": 0.5},
    ]

    report = await optimizer._generate_report(experiments)

    assert report["overall_health"] == "improving"
    assert len(report["wins"]) == 1
    assert len(report["content_engine_feedback"]) >= 1


@pytest.mark.asyncio
async def test_empty_experiments_report():
    from backend.modules.learning_loop.optimizer import LearningLoopOptimizer

    db = AsyncMock()
    optimizer = LearningLoopOptimizer(db=db)

    report = await optimizer._generate_report([])

    assert "no experiments" in report["summary"].lower()
    assert report["overall_health"] == "stable"
