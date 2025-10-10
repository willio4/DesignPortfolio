from flask import Blueprint, jsonify
from openai import OpenAI

client = OpenAI()
test_api = Blueprint('test_api', __name__)

@test_api.route('/test_openai', methods=['GET'])
def api_test():
    try:
        r = client.responses.create(
            model="gpt-4.1-nano",
            input="Tis a test :D"
        )
        return (r.output_text or "FAIL"), 200, {"Content-Type": "text/plain; charset=utf-8"}
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500