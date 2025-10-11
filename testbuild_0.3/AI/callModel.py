# ------------------------ Tess -------------------------------
import json
from openai import OpenAI

client = OpenAI()

SYSTEM= "You are a recipe generator that focuses on healthy meal creation. Respond with ONLY " \
"a valid JSON. No prose."

def call_model(prompt: str) -> dict:
    # send the prompt to the model and return with a python dict (parsed JSON)
    r = client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt}
        ],
            temperature=0.3,
            max_output_tokens=700
        )
    
    # parse text as JSON

    text_response = r.output_text or ""
    try:
        return json.loads(text_response)
    except json.JSONDecodeError:

        fix = client.responses.create(
            model="gpt-4.1-nano",
            input=f"Convert to valid JSON only (no comentary):\n{text_response}",
            temperature=0,
            max_output_tokens=700
        )
        return json.loads(fix.output_text or "{}")















"""recipesFromModel= #call model here pass to the parse function below
    modelResults=parseModelResults(recipesFromModel)
    return modelResults"""
