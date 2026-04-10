"""Learning Loop — evaluates experiment outcomes and feeds insights back."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import anthropic
from backend.config import settings
from backend.models.experiment import Experiment
from backend.models.keyword import Keyword
from backend.models.content import ContentPage


REPORT_PROMPT = """You are an SEO performance analyst.

Given the following experiment results from the past 7 days, generate a performance report.

Experiments:
{experiments}

Return JSON:
{{
  "summary": "2-3 sentence executive summary",
  "wins": [{{"experiment_id": ..., "description": "...", "impact": "..."}}],
  "losses": [{{"experiment_id": ..., "description": "...", "reason": "..."}}],
  "neutral": [{{"experiment_id": ..., "description": "..."}}],
  "content_engine_feedback": [
    "Instruction for content engine based on learnings"
  ],
  "next_actions": ["action1", "action2"],
  "overall_health": "improving|stable|declining"
}}

Only valid JSON.
"""


class LearningLoopOptimizer:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    async def run(self, site_id: int) -> dict:
        """Run the weekly learning loop for a site."""
        experiments = await self._evaluate_experiments(site_id)
        report = await self._generate_report(experiments)
        await self._update_experiment_results(experiments)

        return {
            "site_id": site_id,
            "experiments_evaluated": len(experiments),
            "report": report,
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def _evaluate_experiments(self, site_id: int) -> list[dict]:
        """Compare pre/post metrics for recent experiments."""
        cutoff = datetime.utcnow() - timedelta(days=7)
        result = await self.db.execute(
            select(Experiment).where(
                Experiment.site_id == site_id,
                Experiment.started_at >= cutoff,
                Experiment.concluded_at.is_(None),
            )
        )
        experiments = result.scalars().all()

        evaluated = []
        for exp in experiments:
            # Get current keyword positions for target URL
            if exp.target_url:
                kw_result = await self.db.execute(
                    select(Keyword).where(
                        Keyword.site_id == site_id,
                        Keyword.url == exp.target_url,
                    ).order_by(Keyword.created_at.desc()).limit(5)
                )
                current_keywords = kw_result.scalars().all()
                current_avg_position = (
                    sum(k.position for k in current_keywords if k.position) / len(current_keywords)
                    if current_keywords else None
                )
                baseline_position = exp.baseline_metrics.get("avg_position")

                if current_avg_position and baseline_position:
                    position_change = baseline_position - current_avg_position  # positive = improvement
                    if position_change > 2:
                        outcome = "positive"
                        impact_score = min(position_change / 10, 1.0)
                    elif position_change < -2:
                        outcome = "negative"
                        impact_score = max(position_change / 10, -1.0)
                    else:
                        outcome = "neutral"
                        impact_score = 0.0
                else:
                    outcome = "neutral"
                    impact_score = 0.0
                    position_change = 0.0

                evaluated.append({
                    "id": exp.id,
                    "type": exp.type,
                    "hypothesis": exp.hypothesis,
                    "target_url": exp.target_url,
                    "baseline_position": baseline_position,
                    "current_position": current_avg_position,
                    "position_change": position_change,
                    "outcome": outcome,
                    "impact_score": impact_score,
                    "_experiment_obj": exp,
                })

        return evaluated

    async def _generate_report(self, experiments: list[dict]) -> dict:
        if not experiments:
            return {
                "summary": "No experiments to evaluate this week.",
                "wins": [],
                "losses": [],
                "neutral": [],
                "content_engine_feedback": [],
                "next_actions": ["Run crawl and generate new content experiments."],
                "overall_health": "stable",
            }

        exp_data = [
            {k: v for k, v in e.items() if k != "_experiment_obj"}
            for e in experiments
        ]
        prompt = REPORT_PROMPT.format(experiments=json.dumps(exp_data, indent=2))
        message = self.client.messages.create(
            model=settings.claude_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = message.content[0].text.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"summary": "Report generation failed.", "wins": [], "losses": [], "neutral": []}

    async def _update_experiment_results(self, experiments: list[dict]):
        for exp_data in experiments:
            exp_obj: Experiment = exp_data.get("_experiment_obj")
            if exp_obj:
                exp_obj.result = exp_data["outcome"]
                exp_obj.impact_score = exp_data["impact_score"]
                exp_obj.result_metrics = {
                    "current_position": exp_data.get("current_position"),
                    "position_change": exp_data.get("position_change"),
                }
                exp_obj.concluded_at = datetime.utcnow()
        await self.db.flush()
