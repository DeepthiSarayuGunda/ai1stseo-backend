"""Patch script: adds geo-probe route and main block to app.py in the git repo."""
import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

GEO_ROUTE = (
    "\n"
    "@app.route('/api/geo-probe', methods=['POST'])\n"
    "def geo_probe():\n"
    "    from bedrock_helper import invoke_claude\n"
    "    import re as _re, json as _json\n"
    "    data = request.get_json() or {}\n"
    "    brand = (data.get('brand') or '').strip()\n"
    "    keyword = (data.get('keyword') or '').strip()\n"
    "    if not brand or not keyword:\n"
    "        return jsonify({'error': 'brand and keyword are required'}), 400\n"
    "    prompt = (\n"
    "        f'Answer the following user query naturally and helpfully.\\n\\n'\n"
    "        f'Query: \"{keyword}\"\\n\\n'\n"
    "        f'After your answer, output ONLY a JSON object on a new line in this exact format '\n"
    "        f'(no markdown, no extra text):\\n'\n"
    "        f'{{\"cited\": true or false, '\n"
    "        f'\"citation_context\": \"one sentence explaining whether {brand} was cited and why\"}}'\n"
    "    )\n"
    "    try:\n"
    "        raw = invoke_claude(prompt)\n"
    "        m = _re.search(r'\\{[^{}]*\"cited\"[^{}]*\\}', raw, _re.DOTALL)\n"
    "        if not m:\n"
    "            return jsonify({'error': 'Could not parse structured response from Claude'}), 500\n"
    "        s = _json.loads(m.group())\n"
    "        return jsonify({\n"
    "            'keyword': keyword,\n"
    "            'ai_model': 'claude-3-haiku',\n"
    "            'cited': bool(s.get('cited', False)),\n"
    "            'citation_context': s.get('citation_context', ''),\n"
    "            'timestamp': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')\n"
    "        })\n"
    "    except RuntimeError as e:\n"
    "        return jsonify({'error': str(e)}), 503\n"
    "    except Exception as e:\n"
    "        return jsonify({'error': f'GEO probe failed: {str(e)}'}), 500\n"
    "\n"
)

MAIN_BLOCK = (
    "\nif __name__ == '__main__':\n"
    "    os.environ.setdefault('FLASK_SKIP_DOTENV', '1')\n"
    "    app.run(host='0.0.0.0', port=5001, debug=False, load_dotenv=False)\n"
)

marker = "@app.route('/resources/AI1STSEO-UML-DIAGRAMS.md')"

if 'geo-probe' not in content:
    content = content.replace(marker, GEO_ROUTE + marker)
    print('geo-probe route added')
else:
    print('geo-probe already present')

if '__main__' not in content:
    content = content.rstrip() + '\n' + MAIN_BLOCK
    print('main block added')
else:
    print('main block already present')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Patch complete.')
