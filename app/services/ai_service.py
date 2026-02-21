import os
import json
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"),
    base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL"),
)

MODEL = "gpt-4o-mini"


def _chat(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> str:
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            temperature=0.4,
        )
        return resp.choices[0].message.content or ""
    except Exception as e:
        return f"AI analysis unavailable: {str(e)}"


def generate_project_insights(kpis: dict, conflicts: dict, route_stats: dict, budget: dict) -> dict:
    system = """You are an expert FTTH (Fiber-To-The-Home) construction project analyst. 
Provide concise, actionable insights for project managers. Be direct and specific.
Return valid JSON with these keys:
- "summary": 1-2 sentence project health overview
- "risks": array of 2-4 risk items (short strings)
- "recommendations": array of 2-4 action items (short strings)  
- "highlights": array of 1-3 positive highlights (short strings)
Keep each item under 80 characters. No markdown."""

    user = f"""Analyze this FTTH project:

KPIs: {json.dumps(kpis)}
Spatial Conflicts: {json.dumps({k: v for k, v in conflicts.items() if k != 'conflicts'})}
Route Stats: {json.dumps(route_stats)}
Budget: {json.dumps(budget)}"""

    raw = _chat(system, user, 600)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(cleaned)
    except:
        return {
            "summary": raw[:200] if raw else "Analysis unavailable",
            "risks": [], "recommendations": [], "highlights": []
        }


def generate_task_recommendations(tasks: list, kpis: dict) -> list:
    system = """You are an FTTH construction scheduling expert.
Given a list of tasks with their status, priority, and progress, recommend the optimal next actions.
Return a JSON array of objects, each with:
- "task_name": name of the task
- "action": what to do (under 60 chars)
- "reason": why (under 80 chars)
- "urgency": "high", "medium", or "low"
Return 3-5 recommendations max. No markdown."""

    task_summary = [
        {
            "name": t.get("name", ""),
            "status": t.get("status", ""),
            "priority": t.get("priority", "medium"),
            "type": t.get("task_type_name", ""),
            "progress_pct": round(t.get("actual_qty", 0) / max(t.get("planned_qty", 1), 1) * 100, 1),
            "cost": t.get("total_cost", 0),
        }
        for t in tasks[:20]
    ]

    user = f"""Tasks: {json.dumps(task_summary)}
Project KPIs: completion={kpis.get('completion_pct',0)}%, health={kpis.get('health_status','unknown')}, SPI={kpis.get('spi',0)}, CPI={kpis.get('cpi',0)}"""

    raw = _chat(system, user, 500)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(cleaned)
    except:
        return []


def generate_report_summary(report_data: dict, report_type: str) -> str:
    system = """You are an FTTH construction reporting analyst.
Summarize the report data in 2-3 concise sentences for a project manager.
Focus on key takeaways, trends, and anything that needs attention.
Be direct and professional. No bullet points or markdown."""

    user = f"""Report type: {report_type}
Data: {json.dumps(report_data)}"""

    return _chat(system, user, 200)


def detect_field_anomalies(entries: list, task_info: dict) -> list:
    if not entries:
        return []

    system = """You are a construction QA analyst reviewing field data entries.
Identify anomalies such as unusual quantity jumps, potential data entry errors, or productivity concerns.
Return a JSON array of objects with:
- "entry_index": which entry (0-based)
- "issue": description (under 60 chars)
- "severity": "info", "warning", or "critical"
Return empty array [] if no anomalies. Max 5 items. No markdown."""

    entry_data = [
        {
            "qty": e.get("qty_installed", 0),
            "date": e.get("created_at", ""),
            "user": e.get("user_name", ""),
        }
        for e in entries[:15]
    ]

    user = f"""Task: {task_info.get('name', '')} (planned: {task_info.get('planned_qty', 0)}, actual: {task_info.get('actual_qty', 0)})
Field entries (recent first): {json.dumps(entry_data)}"""

    raw = _chat(system, user, 300)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(cleaned)
    except:
        return []


def smart_import_validation(features: list, file_format: str) -> dict:
    if not features:
        return {"quality_score": 100, "issues": [], "suggestion": "No data to validate"}

    system = """You are a GIS data quality analyst reviewing imported FTTH design data.
Assess the data quality and flag potential issues.
Return JSON with:
- "quality_score": 0-100 integer
- "issues": array of strings (max 5, each under 80 chars)
- "suggestion": single overall recommendation (under 100 chars)
No markdown."""

    sample = features[:5]
    user = f"""Import format: {file_format}
Sample features ({len(features)} total): {json.dumps(sample, default=str)}"""

    raw = _chat(system, user, 300)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(cleaned)
    except:
        return {"quality_score": 0, "issues": ["Could not analyze data"], "suggestion": raw[:100] if raw else "Manual review recommended"}


def generate_daily_briefing(kpis: dict, activities: list, low_stock: list) -> str:
    system = """You are a construction project assistant creating a brief daily update.
Write 3-4 concise sentences covering: project status, yesterday's activity, and any items needing attention.
Professional tone. No bullet points or headers."""

    recent = [{"action": a.get("action",""), "entity": a.get("entity_name",""), "user": a.get("user_name","")} for a in activities[:10]]

    user = f"""KPIs: completion={kpis.get('completion_pct',0)}%, health={kpis.get('health_status','')}, tasks_in_progress={kpis.get('in_progress_tasks',0)}, rework={kpis.get('rework_tasks',0)}
Recent activity: {json.dumps(recent)}
Low stock materials: {json.dumps([m.get('name','') for m in low_stock[:5]])}"""

    return _chat(system, user, 200)


def generate_asset_insights(asset_summary: dict) -> dict:
    system = """You are an expert asset management analyst for FTTH construction companies.
Analyze the asset portfolio and provide actionable insights on utilization, depreciation, maintenance, and risk.
Return valid JSON with:
- "summary": 1-2 sentence overview of asset health
- "risks": array of 2-4 risk items (short strings, under 80 chars)
- "recommendations": array of 2-4 action items (short strings, under 80 chars)
- "highlights": array of 1-3 positive highlights (short strings, under 80 chars)
- "depreciation_analysis": 1 sentence on depreciation trends
- "utilization_score": integer 0-100 estimating fleet utilization
No markdown."""

    user = f"""Asset portfolio data:
{json.dumps(asset_summary, default=str)}"""

    raw = _chat(system, user, 700)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(cleaned)
    except:
        return {
            "summary": raw[:200] if raw else "Analysis unavailable",
            "risks": [], "recommendations": [], "highlights": [],
            "depreciation_analysis": "", "utilization_score": 0
        }


def generate_fleet_insights(fleet_summary: dict) -> dict:
    system = """You are a fleet management analyst for a fiber construction company.
Analyze the fleet data and provide insights on vehicle utilization, maintenance needs, fuel efficiency, and driver allocation.
Return valid JSON with:
- "summary": 1-2 sentence overview of fleet health
- "risks": array of 2-4 risk items (short strings, under 80 chars)
- "recommendations": array of 2-4 action items (short strings, under 80 chars)
- "highlights": array of 1-3 positive highlights (short strings, under 80 chars)
- "efficiency_score": integer 0-100 estimating fleet efficiency
No markdown."""

    user = f"""Fleet data:
{json.dumps(fleet_summary, default=str)}"""

    raw = _chat(system, user, 700)
    try:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(cleaned)
    except:
        return {
            "summary": raw[:200] if raw else "Analysis unavailable",
            "risks": [], "recommendations": [], "highlights": [],
            "efficiency_score": 0
        }
