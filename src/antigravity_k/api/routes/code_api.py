"""Code Intelligence API — Inline code editing suggestions.

Provides an endpoint for generating inline code suggestions
when the user invokes Ctrl+K (Cursor-style inline edit).
"""

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger("antigravity_k.api.code_api")
router = APIRouter()


@router.post("/api/code/inline-suggest")
async def inline_suggest(request: Request):
    """Generate an inline code suggestion based on user instruction.

    Invoked when user presses Ctrl+K in the editor, types an instruction,
    and presses Enter. The backend returns a suggestion or falls back
    to a simple LLM-based generation.

    Request Body:
        file_path (str): Path to the file being edited
        language (str): Programming language of the file
        original_code (str): The current file content
        instruction (str): User's edit instruction (e.g., "rename to camelCase")
        cursor_line (int): Current cursor line number
        cursor_column (int): Current cursor column number

    Returns:
        dict: { ok: bool, suggested_code: str, start_line: int, end_line: int }
    """
    try:
        body = await request.json()
        language = body.get("language", "python")
        original_code = body.get("original_code", "")
        instruction = body.get("instruction", "")
        cursor_line = body.get("cursor_line", 1)

        if not instruction.strip():
            return {"ok": False, "error": "Instruction is required."}

        if not original_code.strip():
            return {"ok": False, "error": "No code to edit."}

        # Try to use the model manager for LLM-based suggestion
        try:
            from antigravity_k.api.dependencies import get_model_manager

            # Build a focused prompt for the edit task
            lines = original_code.split("\n")
            # Provide context: a few lines before and after the cursor
            context_start = max(0, cursor_line - 10)
            context_end = min(len(lines), cursor_line + 10)
            context_lines = lines[context_start:context_end]

            prompt = (
                f"You are an expert {language} code editor. "
                f"Given the following code context around line {cursor_line}, "
                f"apply this edit instruction: '{instruction}'.\n\n"
                f"```{language}\n" + "\n".join(context_lines) + "\n```\n\n"
                "Return ONLY the modified lines (the complete new version of "
                "the affected code section). Do NOT include any explanation, "
                "markdown formatting, or backticks."
            )

            mm = get_model_manager()
            try:
                result = mm.generate(
                    messages=[{"role": "user", "content": prompt}],
                    model=None,
                    max_tokens=2048,
                    temperature=0.3,
                )
                suggested = result.get("content", "") or result.get("text", "") or ""
            except Exception:
                logger.exception("Model generation failed, using fallback")
                suggested = _fallback_suggestion(original_code, instruction, cursor_line)
        except ImportError:
            logger.warning("Model manager not available, using fallback")
            suggested = _fallback_suggestion(original_code, instruction, cursor_line)

        if not suggested.strip():
            return {"ok": False, "error": "Could not generate suggestion."}

        # Clean up the response
        suggested = suggested.strip()
        # Remove markdown code fences if present
        import re

        suggested = re.sub(r"^```\w*\n?", "", suggested)
        suggested = re.sub(r"\n```$", "", suggested)

        return {
            "ok": True,
            "suggested_code": suggested,
            "start_line": max(1, cursor_line - 1),
            "end_line": min(len(original_code.split("\n")), cursor_line + 1),
            "language": language,
        }

    except Exception as e:
        logger.exception("Inline suggest error")
        return {"ok": False, "error": str(e)}


def _fallback_suggestion(original_code: str, instruction: str, cursor_line: int) -> str:
    """Simple fallback when no LLM is available.

    Provides a basic diff-style suggestion by extracting context
    around the cursor. In production, this would use the model.
    """
    lines = original_code.split("\n")
    if not lines:
        return ""

    # For fallback, just return the context around cursor with a comment
    start = max(0, cursor_line - 3)
    end = min(len(lines), cursor_line + 3)
    context = lines[start:end]

    result = []
    for i, line in enumerate(context):
        result.append(line)

    if result:
        result.insert(0, f"// TODO: {instruction}")
        result.insert(1, "")

    return "\n".join(result)
