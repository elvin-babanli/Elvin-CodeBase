"""
AI analysis service. Uses OpenAI to analyze visitor/user behavior from footprint data.
Returns structured analysis with risk score and recommendations.
"""
import logging
import json
import re
from django.conf import settings

logger = logging.getLogger(__name__)

STRUCTURED_PROMPT = """You are a security and behavior analyst for a web application. Analyze the following visitor/user footprint data (collected in-app only, no external data).

TASK: Produce a structured JSON analysis. Return ONLY valid JSON, no markdown or extra text.

FOOTPRINT DATA:
{footprint_json}

Return a JSON object with exactly these keys (use empty string for missing):
- behavior_summary: Brief summary of user behavior (2-3 sentences)
- engagement_assessment: low/medium/high based on activity
- suspicious_activity_assessment: Description of any suspicious patterns or "None detected"
- bot_or_spam_probability: low/medium/high and brief reason
- risk_score_0_to_100: Integer 0-100 (0=safe, 100=high risk)
- risk_reasoning: Why this risk score
- session_pattern_analysis: Notable session patterns
- device_pattern_analysis: Device/browser usage patterns
- geo_pattern_analysis: Geographic/regional patterns
- auth_pattern_analysis: Login/auth behavior summary
- recommended_admin_action: Concrete admin recommendation
- concise_final_verdict: One-line verdict

Be objective. Use only the provided data. No speculation beyond evidence."""


def analyze_footprint(footprint: dict) -> dict:
    """
    Send footprint to OpenAI and return structured analysis.
    footprint: from footprint_service.get_full_footprint()
    """
    api_key = getattr(settings, "OPENAI_API_KEY", "") or ""
    if not api_key:
        return {"error": "OpenAI API key not configured"}

    if not footprint or not footprint.get("identity"):
        return {"error": "No footprint data to analyze"}

    prompt = STRUCTURED_PROMPT.format(footprint_json=json.dumps(footprint, indent=2))

    try:
        import openai

        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You return only valid JSON. No markdown, no code blocks, no extra text.",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.3,
        )
        text = response.choices[0].message.content.strip()
        parsed = _parse_json_response(text)
        if parsed:
            return parsed
        return {"error": "Could not parse AI response", "raw": text[:500]}
    except Exception as e:
        logger.exception("AI analysis failed: %s", e)
        return {"error": str(e)}


def _parse_json_response(text: str) -> dict | None:
    """Extract JSON from response, handling code blocks."""
    text = text.strip()
    # Remove markdown code block if present
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to find JSON object
    start = text.find("{")
    if start >= 0:
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None
