# ------------------------ Tess -------------------------------
# AI/callModel.py
import json
from openai import OpenAI
client = OpenAI()

SYSTEM = (
    "You are a recipe generator. Respond with ONLY valid JSON; no prose, no comments, no trailing commas."
)

def call_model(prompt: str, max_tokens: int = 900) -> dict:
    r = client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0,          # stricter
        top_p=0,
        max_output_tokens=max_tokens,
    )
    text = r.output_text or ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # one repair pass
        fix = client.responses.create(
            model="gpt-4.1-nano",
            input=f"Fix to strictly valid JSON only (no commentary):\n{text}",
            temperature=0,
            top_p=0,
            max_output_tokens=max_tokens,
        )
        return json.loads(fix.output_text or "{}")

        















"""recipesFromModel= #call model here pass to the parse function below
    modelResults=parseModelResults(recipesFromModel)
    return modelResults"""
