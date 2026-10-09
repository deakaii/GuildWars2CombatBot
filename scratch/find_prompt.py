import json

log_path = r"C:\Users\dakot\.gemini\antigravity-ide\brain\1995e392-98b9-4a69-be2f-e14be90b4d80\.system_generated\logs\transcript_full.jsonl"
with open(log_path, "r", encoding="utf-8") as f:
    for line in f:
        if '"type":"USER_INPUT"' in line and "Shield of Wrath" in line:
            obj = json.loads(line)
            print("USER INPUT FOUND:\n", obj.get("content"))
            break
