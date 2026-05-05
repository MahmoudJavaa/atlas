"""Atlas Master Orchestration Agent — uses Ollama function-calling to plan and execute SEO tasks."""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from backend.llm import get_llm

SYSTEM_PROMPT = """You are Atlas, an expert autonomous SEO and GEO agent.

Given a high-level goal, you will:
1. Break it into an ordered task plan using available tools
2. Execute each tool sequentially (or flag parallel-safe tasks)
3. Build a full report of actions taken and results

Always think strategically. Prioritize high-impact actions first.
When generating content, always ensure it passes quality checks before publishing.
Never publish without explicit dry_run=False confirmation.

Be precise with tool arguments. Return structured JSON in tool calls.
"""

# Tool declarations in OpenAI / Ollama format
TOOL_DECLARATIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "crawl_site",
            "description": "Crawl a website and run a full technical SEO audit. Returns issues by severity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer", "description": "Database site ID"},
                    "start_url": {"type": "string", "description": "URL to start crawling from"},
                    "max_pages": {"type": "integer", "description": "Max pages to crawl (default 100)"},
                },
                "required": ["site_id", "start_url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "classify_keywords",
            "description": "Classify keyword intent and build topic clusters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                    "seed_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["site_id", "seed_keywords"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_geo_answerability",
            "description": "Score content for AI answerability (GEO) and get recommendations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to analyze"},
                    "url": {"type": "string"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_content",
            "description": "Generate SEO-optimized content for a target keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                    "keyword": {"type": "string"},
                    "intent": {"type": "string"},
                    "funnel_stage": {"type": "string"},
                    "page_type": {"type": "string"},
                    "location": {"type": "string"},
                },
                "required": ["site_id", "keyword", "intent", "funnel_stage", "page_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_competitors",
            "description": "Analyze competitor domains and produce a content gap report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                    "competitor_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "our_domain": {"type": "string"},
                },
                "required": ["site_id", "competitor_domains"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "build_silo",
            "description": "Build topic silo structure and internal linking plan from crawl data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                },
                "required": ["site_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_local_page",
            "description": "Generate a local SEO service page with schema and doorway check.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                    "service": {"type": "string"},
                    "location": {"type": "string"},
                    "business_name": {"type": "string"},
                },
                "required": ["service", "location", "business_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_backlink_opportunities",
            "description": "Find backlink opportunities and generate outreach emails.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                    "target_domain": {"type": "string"},
                    "topic": {"type": "string"},
                },
                "required": ["site_id", "target_domain", "topic"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pull_analytics",
            "description": "Pull Google Search Console data and return performance summary.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                    "days": {"type": "integer", "description": "Number of days to look back (default 28)"},
                },
                "required": ["site_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "publish_to_cms",
            "description": "Publish a generated content page to WordPress or Shopify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                    "content_page_id": {"type": "integer"},
                    "dry_run": {"type": "boolean", "description": "true=preview only, false=actually publish"},
                },
                "required": ["site_id", "content_page_id", "dry_run"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_learning_loop",
            "description": "Evaluate past experiments and generate a performance report.",
            "parameters": {
                "type": "object",
                "properties": {
                    "site_id": {"type": "integer"},
                },
                "required": ["site_id"],
            },
        },
    },
]


class AtlasAgent:
    def __init__(self, db=None, redis_client=None):
        self.db = db
        self.redis = redis_client
        self.llm = get_llm()
        self.session_id = str(uuid.uuid4())
        self.audit_trail: list[dict] = []

    async def run(self, goal: str, site_id: int) -> dict:
        """Execute a high-level SEO goal autonomously using Ollama function calling."""
        # Conversation history — grows with each tool round-trip
        messages: list[dict] = [
            {"role": "user", "content": f"Goal: {goal}\nSite ID: {site_id}"},
        ]

        max_iterations = 20

        for iteration in range(1, max_iterations + 1):
            result = self.llm.generate_with_tools(
                messages=messages,
                tools=TOOL_DECLARATIONS,
                system=SYSTEM_PROMPT,
            )

            fn_calls = result.get("function_calls")
            text = result.get("text")

            # Build the assistant turn for history
            assistant_msg: dict[str, Any] = {"role": "assistant", "content": text or ""}
            if fn_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": fc["id"],
                        "type": "function",
                        "function": {
                            "name": fc["name"],
                            "arguments": json.dumps(fc["args"]),
                        },
                    }
                    for fc in fn_calls
                ]
            messages.append(assistant_msg)

            if not fn_calls:
                # Agent decided it's done — return final text
                return {
                    "session_id": self.session_id,
                    "goal": goal,
                    "site_id": site_id,
                    "final_report": text or "Task complete.",
                    "audit_trail": self.audit_trail,
                    "iterations": iteration,
                }

            # Execute each tool call and feed results back into the conversation
            for fc in fn_calls:
                tool_name = fc["name"]
                tool_input = fc["args"]

                tool_result = await self._execute_tool(tool_name, tool_input, site_id)

                self.audit_trail.append({
                    "tool": tool_name,
                    "input": tool_input,
                    "result": tool_result,
                    "timestamp": datetime.now().isoformat(),
                })

                # Persist to DB audit log if DB session available
                if self.db:
                    from backend.models.audit import AuditLog
                    log = AuditLog(
                        site_id=site_id,
                        module="atlas_agent",
                        action=tool_name,
                        payload={"input": tool_input, "result": tool_result},
                    )
                    self.db.add(log)
                    await self.db.flush()

                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": fc["id"],
                    "content": json.dumps(tool_result, default=str),
                })

            # Save session state to Redis if available
            if self.redis:
                await self.redis.set(
                    f"atlas:session:{self.session_id}",
                    json.dumps({
                        "audit_trail_len": len(self.audit_trail),
                        "iteration": iteration,
                    }),
                    ex=3600,
                )

        return {
            "session_id": self.session_id,
            "goal": goal,
            "site_id": site_id,
            "error": "Max iterations reached",
            "audit_trail": self.audit_trail,
        }

    async def _execute_tool(self, tool_name: str, tool_input: dict, site_id: int) -> Any:
        """Dispatch tool calls to the appropriate Atlas module."""
        try:
            if tool_name == "crawl_site":
                from backend.modules.technical_seo.crawler import TechnicalSEOCrawler
                crawler = TechnicalSEOCrawler(db=self.db)
                return await crawler.run(
                    site_id=tool_input.get("site_id", site_id),
                    start_url=tool_input["start_url"],
                    max_pages=tool_input.get("max_pages", 100),
                )

            elif tool_name == "classify_keywords":
                from backend.modules.keyword_intel.classifier import KeywordClassifier
                classifier = KeywordClassifier(db=self.db)
                return await classifier.run(
                    site_id=tool_input.get("site_id", site_id),
                    seed_keywords=tool_input["seed_keywords"],
                )

            elif tool_name == "score_geo_answerability":
                from backend.modules.geo_engine.optimizer import GEOOptimizer
                optimizer = GEOOptimizer()
                return await optimizer.run(
                    content=tool_input["content"],
                    url=tool_input.get("url", ""),
                )

            elif tool_name == "generate_content":
                from backend.modules.content_engine.generator import ContentGenerator
                generator = ContentGenerator(db=self.db)
                return await generator.run(
                    site_id=tool_input.get("site_id", site_id),
                    keyword=tool_input["keyword"],
                    intent=tool_input["intent"],
                    funnel_stage=tool_input["funnel_stage"],
                    page_type=tool_input["page_type"],
                    location=tool_input.get("location"),
                )

            elif tool_name == "analyze_competitors":
                from backend.modules.competitor_intel.analyzer import CompetitorAnalyzer
                analyzer = CompetitorAnalyzer(db=self.db)
                return await analyzer.run(
                    site_id=tool_input.get("site_id", site_id),
                    competitor_domains=tool_input["competitor_domains"],
                    our_domain=tool_input.get("our_domain", ""),
                )

            elif tool_name == "build_silo":
                from backend.modules.internal_linking.silo import SiloBuilder
                builder = SiloBuilder(db=self.db)
                return await builder.run(site_id=tool_input.get("site_id", site_id))

            elif tool_name == "generate_local_page":
                from backend.modules.local_seo.page_generator import LocalSEOPageGenerator
                generator = LocalSEOPageGenerator(db=self.db)
                return await generator.run(
                    service=tool_input["service"],
                    location=tool_input["location"],
                    business_name=tool_input["business_name"],
                    site_id=tool_input.get("site_id", site_id),
                )

            elif tool_name == "find_backlink_opportunities":
                from backend.modules.backlink_ai.finder import BacklinkFinder
                finder = BacklinkFinder(db=self.db)
                return await finder.run(
                    site_id=tool_input.get("site_id", site_id),
                    target_domain=tool_input["target_domain"],
                    topic=tool_input["topic"],
                )

            elif tool_name == "pull_analytics":
                from backend.modules.analytics.connector import AnalyticsConnector
                connector = AnalyticsConnector(db=self.db)
                return await connector.get_performance_summary(
                    site_id=tool_input.get("site_id", site_id),
                    days=tool_input.get("days", 28),
                )

            elif tool_name == "publish_to_cms":
                from backend.modules.execution.publisher import CMSPublisher
                publisher = CMSPublisher(db=self.db)
                return await publisher.publish_page(
                    content_page_id=tool_input["content_page_id"],
                    dry_run=tool_input.get("dry_run", True),
                )

            elif tool_name == "run_learning_loop":
                from backend.modules.learning_loop.optimizer import LearningLoopOptimizer
                optimizer = LearningLoopOptimizer(db=self.db)
                return await optimizer.run(site_id=tool_input.get("site_id", site_id))

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            return {"error": str(e), "tool": tool_name}
