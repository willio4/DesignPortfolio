# ------------------------ Tess -------------------------------
# AI/callModel.py
import json
import logging
import datetime
from openai import OpenAI
client = OpenAI()

SYSTEM = (
    "You are a recipe generator. Respond with ONLY valid JSON; no prose, no comments, no trailing commas."
)

def call_model(prompt: str, max_tokens: int = 900) -> dict:

    prompt += f"\n\n# Request timestamp: {datetime.utcnow().isoformat()}"
    logging.debug(f"Final prompt sent to model: {prompt}")

    r = client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,          # stricter
        top_p=1.0,
        max_output_tokens=max_tokens,
    )
    text = r.output_text or ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logging.error("Failed to parse JSON from model response.")
        # one repair pass
        return {"meals": []} # ensure no hard coded meals are returned 

        















"""recipesFromModel= #call model here pass to the parse function below
    modelResults=parseModelResults(recipesFromModel)
    return modelResults"""
