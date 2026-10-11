# LLM Rotation Prompt Template

Paste the prompt below into any AI model, followed by the rotation guide text (e.g. a Snow Crows
opener and rotation), and the spec's skill bar. Save the YAML it returns as
`config/rotations/{profession}_{spec}.yaml`. See `config/rotations/thief_deadeye.yaml` for a full example.

---

```text
Convert the Guild Wars 2 rotation below into a YAML rotation file for a screen-reading bot.
Return only the YAML.

SKILLS are named by skill-bar position, never by keybind:
  1-5 weapon skills, 6 heal, 7 8 9 utilities, 0 elite, f1-f5 profession skills, swap = weapon swap.
  A skill whose icon changes in place (stealth attack on 1, a flip skill) keeps its slot number.

FORMAT
name: <build name>

# Builds without a fixed order: the first ready skill in this list is pressed.
priority: [2, 3, 4, 5, 7, 0]

# Builds with an opener / rotation:
opener: [<steps>]                 # runs once per fight, in order
loop:                             # after the opener: the first block whose "when" skills
  - name: <block name>            # are all ready runs start to finish, then pick again
    when: [<skills>]              # e.g. "when Shadow Flare is available" -> [7]
    steps: [<steps>]

A step is one of:
  3                                       press skill 3
  {skill: f2, wait: {malice: 5}}          wait until the resource reaches the amount
  {skill: f2, after: {1: 3}}              wait until 3 s after skill 1 last went off
  {auto: 5}                               press nothing for 5 auto-attacks
  {skill: f2, wait: {malice: 5}, fill: 3} while waiting, cast 3 to build the resource
  {skill: 1, only_if: {malice: 3}}        skip the step unless the condition holds
  {skill: 1, confirm: false}              press once; don't wait to see it go off

instant: [f1, f2, 8]              # instant-cast skills (cantrips, virtues, F-skills that don't cast);
                                  # "X during these casts" = list X as a step right after the cast
costs:                            # skills that spend a resource, e.g. thief initiative
  3: {initiative: 4}
double_tap: {7: 0.25}             # ground-targeted skills: pressed twice, N seconds apart
no_interrupt: {2: 0.75}           # channels that must not be cast over: hold N seconds
auto_attack_seconds: 0.8          # length of one auto-attack, for {auto: N}

RULES
- "Skill A x2" is two steps. "A -> B" is A then B.
- Resource names must be the spec's: e.g. initiative, malice, clones, blades, life_force, heat.
- Waiting never builds a resource that only skills generate (e.g. malice): give such waits a "fill".
- Things the bot can't see (boons, Revealed, target state) become waits: use "after" for
  "until Revealed wears off" and an auto step for "auto-attack N times".
- Comment each step with the skill name from the guide.

ROTATION GUIDE AND SKILL BAR:
[PASTE HERE]
```
