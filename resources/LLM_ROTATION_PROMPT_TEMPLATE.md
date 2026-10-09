# LLM Rotation Serialization Prompt Template

Copy and paste the system prompt below into any AI model (ChatGPT, Claude, Gemini, DeepSeek) alongside your rotation web page text or guide to generate a ready-to-import JSON payload for the bot engine.

---

```text
You are a Guild Wars 2 Combat Rotation Serializer for an automated rotation engine.
Convert the provided combat rotation guide/text into a valid JSON object matching the exact schema below.

CRITICAL RULES:
1. Return ONLY the valid JSON object. Do not include markdown headers, prose explanations, or commentary outside the JSON.
2. Skill keybinds must map to standard keyboard keys: "1", "2", "3", "4", "5", "q", "e", "r", "t", "f1", "f2", "f3", "f4", "`".
3. Ground-targeted skills (e.g. Jump Shot, Throw Mine, Symbol of Punishment, Sword of Justice) MUST have "double_tap": true.
4. Off-GCD skills (e.g. Virtues, Mech commands F1-F3, Instant Buffs) MUST have "is_instant": true.
5. Passive filler auto-attacks (e.g. Rifle Burst 1) MUST have "is_auto_attack": true.
6. Rotation Type: Set "priority_list" for priority-driven builds, "rigid_loop" for fixed weapon-swap loops, or "hybrid" for builds with both an opener and priority/loop.

JSON SCHEMA:
{
  "name": "Build Name (e.g. Power Mechanist)",
  "description": "Short description of the build",
  "rotation_type": "priority_list",
  "opener": [
    {
      "name": "Skill Name (Weapon/Slot)",
      "key": "keyboard_key",
      "cast_delay": 0.4,
      "cooldown": 8.0,
      "double_tap": false,
      "cancellable": true
    }
  ],
  "loop": [
    {
      "name": "Skill Name (Weapon/Slot)",
      "key": "keyboard_key",
      "cast_delay": 0.5,
      "cooldown": 8.0,
      "double_tap": false,
      "is_auto_attack": false
    }
  ],
  "priority_list": [
    {
      "name": "Skill Name (Weapon/Slot)",
      "key": "keyboard_key",
      "priority": 90,
      "cooldown": 8.0,
      "cast_delay": 0.5,
      "double_tap": false,
      "is_auto_attack": false
    }
  ],
  "mechanic_skills": [
    {
      "name": "Mechanic Skill Name (F1-F5)",
      "key": "f1",
      "priority": 95,
      "cooldown": 15.0,
      "is_instant": true
    }
  ]
}

Here is the rotation guide text to process:
[PASTE YOUR ROTATION TEXT / WEBSITE GUIDE HERE]
```

---

### Example JSON Payload Output

```json
{
  "name": "Power Mechanist",
  "description": "High sustained power DPS with Jade Mech command synchronization",
  "rotation_type": "priority_list",
  "opener": [
    {
      "name": "Skill 3 (Net Shot)",
      "key": "3",
      "cast_delay": 0.4,
      "cooldown": 8.0,
      "cancellable": true
    },
    {
      "name": "Skill 2 (Blunderbuss)",
      "key": "2",
      "cast_delay": 0.5,
      "cooldown": 8.0,
      "cancellable": true
    },
    {
      "name": "Skill 4 (Overcharged Shot)",
      "key": "4",
      "cast_delay": 0.65,
      "cooldown": 12.0,
      "cancellable": true
    },
    {
      "name": "Skill 5 (Jump Shot)",
      "key": "5",
      "cast_delay": 0.85,
      "cooldown": 18.0,
      "double_tap": true,
      "cancellable": false
    }
  ],
  "loop": [],
  "priority_list": [
    {
      "name": "Skill 2 (Blunderbuss)",
      "key": "2",
      "priority": 90,
      "cast_delay": 0.5,
      "cooldown": 8.0,
      "cancellable": true
    },
    {
      "name": "Skill 3 (Net Shot)",
      "key": "3",
      "priority": 80,
      "cast_delay": 0.4,
      "cooldown": 8.0,
      "cancellable": true
    },
    {
      "name": "Skill 4 (Overcharged Shot)",
      "key": "4",
      "priority": 70,
      "cast_delay": 0.65,
      "cooldown": 12.0,
      "cancellable": true
    },
    {
      "name": "Skill 5 (Jump Shot)",
      "key": "5",
      "priority": 60,
      "cast_delay": 0.85,
      "cooldown": 18.0,
      "double_tap": true,
      "cancellable": false
    },
    {
      "name": "Throw Mine (Utility E)",
      "key": "e",
      "priority": 50,
      "cast_delay": 0.35,
      "cooldown": 15.0,
      "double_tap": true,
      "cancellable": true
    },
    {
      "name": "Skill 1 (Rifle Burst Filler)",
      "key": "1",
      "priority": 20,
      "cast_delay": 0.4,
      "cooldown": 1.2,
      "is_auto_attack": true
    }
  ],
  "mechanic_skills": [
    {
      "name": "Core Reactor Shot (F2)",
      "key": "f2",
      "priority": 95,
      "cooldown": 15.0,
      "is_instant": true
    },
    {
      "name": "Jade Mortar (F3)",
      "key": "f3",
      "priority": 90,
      "cooldown": 20.0,
      "is_instant": true
    },
    {
      "name": "Spark Revolver (F1)",
      "key": "f1",
      "priority": 85,
      "cooldown": 8.0,
      "is_instant": true
    }
  ]
}
```
