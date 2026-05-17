from __future__ import annotations

try:
    import google.generativeai as genai
except ImportError:
    genai = None

from app.core.config import settings


def is_gemini_configured() -> bool:
    return bool(settings.gemini_api_key and genai is not None)


def get_pro_coach_analysis(
    board_state: str,
    move_history: list[dict],
    current_move: dict,
    coach_feedback: dict,
    player_nickname: str,
) -> dict | None:
    """Generate comprehensive Pro coach analysis using Gemini API."""
    if not is_gemini_configured():
        return None

    try:
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        move_sequence = ", ".join(
            [
                f"({m['from'][0]},{m['from'][1]})→({m['to'][0]},{m['to'][1]})"
                for m in move_history[-5:]
            ]
        )

        prompt = f"""You are a professional checkers coach. Analyze this game position and provide strategic insights.

Current Move: ({current_move['from'][0]},{current_move['from'][1]})→({current_move['to'][0]},{current_move['to'][1]})
Recent Moves: {move_sequence}
Coach Assessment: {coach_feedback.get('summary', 'Move analyzed')}

Provide a 2-3 sentence strategic explanation as if coaching {player_nickname}. Focus on:
1. Why this move fits the board control strategy
2. What opponent might do next
3. One high-value follow-up idea

Be encouraging but honest. Keep it under 150 words."""

        response = model.generate_content(prompt, stream=False)
        analysis_text = response.text if response and hasattr(response, "text") else None

        if analysis_text:
            return {
                "pro_analysis": analysis_text.strip(),
                "source": "gemini",
            }
    except Exception as e:
        return {"error": f"Gemini analysis unavailable: {str(e)}"}

    return None
