"""One-off AST extractor: legacy voice command table -> reflex rule data.

Reads src/jarvis/voice/interface.py, extracts the 156-entry
``self.commands`` table, and writes src/jarvis/legacy/rule_commands.py
as pure data (patterns + ToolSpec mapping + reply templates).

Mapping policy (Task 2.6: reflex calls go through the policy gate via
ToolSpec — the legacy direct-pyautogui/webbrowser paths are UPGRADED to
gated tool calls):
  _open_url(url, msg)      -> open_website {url_or_name: url}
  _press_key(key, msg)     -> keyboard_mouse_action {action: press_key, value: key}
  _hotkey(keys, msg)       -> keyboard_mouse_action {action: press_hotkey, value: "+".join(keys)}
  _launch_app(cmd, msg)    -> open_application {app_name: normalized}
  _change_volume(up, ...)  -> system_control {action: volume_up/volume_down}
  _gated(tool, args, msg)  -> tool + args (already gated)
  random.choice([...])     -> reply-only (random pick)
  constant lambda          -> reply-only
  _action_get_time/date/day, _action_tell_joke/_action_flip_coin/_action_roll_dice,
  _action_calculate        -> compute rules (no tool call)
  match-group actions      -> hand-written entries with {groupN} templates
Excluded (fall through to the LLM): find_file (no ToolSpec), ai_summarize,
ai_code (clipboard+LLM flows), repeat_last (needs conversational state).
"""

import ast
import os
import re

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "src", "jarvis", "voice", "interface.py")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "src", "jarvis", "legacy", "rule_commands.py")

# A-04/A-10 normalization from VoiceCommandProcessor._launch_app.
LAUNCH_NORMALIZE = {
    "start ms-settings:": "settings",
    "start chrome": "chrome",
    "start msedge": "edge",
    "start winword": "word",
    "start excel": "excel",
    "start powerpnt": "powerpoint",
}

JOKES = [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "There are 10 types of people in the world: those who understand binary, and those who don't.",
    "Why did the computer go to the doctor? Because it had a virus!",
    "What is a programmer's favorite hangout spot? The Foo Bar.",
    "A SQL statement walks into a bar, approaches two tables, and asks: May I join you?",
    "Why was the JavaScript developer sad? Because they didn't Node how to Express themselves!",
    "What did one computer say to the other? Between 0 and 1, you're my favorite.",
]

# Hand-written entries for match-group actions: id -> rule (patterns kept
# from the legacy table unless simplified; see notes).
HANDWRITTEN = {
    "play_youtube": {
        "tool": "open_website",
        "args": {"url_or_name": "https://www.youtube.com/results?search_query={group1|urlencode}"},
        "reply": "Searching YouTube for {group1}",
    },
    "download_youtube_video": {
        # Legacy picked the last non-keyword group and fell back to the
        # clipboard, then "trending song". Reflex: single clean group with
        # the same last-resort default (clipboard fallback dropped).
        "patterns": [r"^download (?:this|current|the)? ?(?:video|song|youtube video)(?: (.+))?$",
                     r"^download (.+) (?:from|on) youtube$"],
        "tool": "download_media",
        "args": {"url_or_query": "{group1|default:trending song}", "media_type": "video"},
        "reply": "Starting video download to your Downloads folder in the background.",
    },
    "download_youtube_audio": {
        "patterns": [r"^download (?:this|current|the)? ?(?:mp3|audio)(?: (.+))?$",
                     r"^download audio of (.+)$"],
        "tool": "download_media",
        "args": {"url_or_query": "{group1|default:trending song}", "media_type": "audio"},
        "reply": "Starting audio download to your Downloads folder in the background.",
    },
    "ask_chatgpt": {
        "tool": "open_website",
        "args": {"url_or_name": "https://chatgpt.com/?q={group2|urlencode}"},
        "reply": "Asking ChatGPT: {group2}",
    },
    "ask_perplexity": {
        "tool": "open_website",
        "args": {"url_or_name": "https://www.perplexity.ai/search?q={group2|urlencode}"},
        "reply": "Asking Perplexity AI: {group2}",
    },
    "ask_copilot": {
        "tool": "open_website",
        "args": {"url_or_name": "https://copilot.microsoft.com/?q={group2|urlencode}"},
        "reply": "Asking Copilot: {group2}",
    },
    "ask_claude": {
        # Legacy also copied the query to the clipboard; reflex drops that.
        "tool": "open_website",
        "args": {"url_or_name": "https://claude.ai/new"},
        "reply": "Asking Claude: {group2}",
    },
    "type_text": {
        "tool": "keyboard_mouse_action",
        "args": {"action": "type_text", "value": "{group1}"},
        "reply": "Typed: {group1}",
    },
    "search_google": {
        "tool": "web_search",
        "args": {"query": "{group1}"},
        "reply": "Searching Google for {group1}",
    },
    "search_wikipedia": {
        "tool": "open_website",
        "args": {"url_or_name": "https://en.wikipedia.org/wiki/Special:Search?search={group1|urlencode}"},
        "reply": "Searching Wikipedia for {group1}",
    },
    "weather": {
        "tool": "web_search",
        "args": {"query": "weather {group1}"},
        "reply": "Checking weather for {group1}",
    },
    "define_word": {
        "tool": "web_search",
        "args": {"query": "define {group1}"},
        "reply": "Looking up the definition of {group1}",
    },
    "take_note": {
        "tool": "manage_notes",
        "args": {"action": "save", "content": "{group1}"},
        "reply": "Saved note: {group1}",
    },
    "calculate": {"compute": "calc"},
    "tell_joke": {"compute": "joke"},
    "flip_coin": {"compute": "coin"},
    "roll_dice": {"compute": "dice"},
    "tell_time": {"compute": "time"},
    "tell_date": {"compute": "date"},
    "tell_day": {"compute": "day"},
}

EXCLUDED = {"find_file", "ai_summarize", "ai_fix_code", "repeat_last"}

COMPUTE_IDS = {"_action_get_time": "time", "_action_get_date": "date",
               "_action_get_day": "day", "_action_tell_joke": "joke",
               "_action_flip_coin": "coin", "_action_roll_dice": "dice",
               "_action_calculate": "calc"}

SIMPLE_GATED = {
    "_action_lock_pc": ("system_control", {"action": "lock_pc"}, "Locking the workstation"),
    "_action_take_screenshot": ("system_control", {"action": "take_screenshot"}, "Screenshot captured."),
    "_action_empty_recycle_bin": ("system_control", {"action": "empty_recycle_bin"}, "Recycle Bin emptied"),
    "_action_check_battery": ("system_control", {"action": "check_battery"}, None),
    "_action_read_notes": ("manage_notes", {"action": "read"}, None),
    "_action_clear_notes": ("manage_notes", {"action": "clear"}, "Your notes have been cleared."),
    "_action_weather_general": ("web_search", {"query": "weather"}, "Showing the current weather forecast"),
}


def const(node):
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError(f"not a constant: {ast.dump(node)[:80]}")


def str_list(node):
    return [const(e) for e in node.elts]


def main():
    tree = ast.parse(open(SRC).read())
    rules = []
    skipped = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if not (isinstance(t, ast.Attribute) and t.attr == "commands"):
                continue
            for elt in node.value.elts:
                d = {k.value: v for k, v in zip(elt.keys, elt.values)}
                rid = d["id"].value
                patterns = str_list(d["patterns"])
                act = d["action"]
                rule = {"id": rid, "patterns": patterns, "tool": None,
                        "args": {}, "reply": None, "compute": None}

                if rid in EXCLUDED:
                    skipped.append(rid)
                    continue
                if rid in HANDWRITTEN:
                    h = HANDWRITTEN[rid]
                    rule.update({k: h.get(k, rule[k]) for k in
                                 ("tool", "args", "reply", "compute")})
                    if "patterns" in h:
                        rule["patterns"] = h["patterns"]
                    rules.append(rule)
                    continue

                if isinstance(act, ast.Lambda):
                    call = act.body
                    if isinstance(call, ast.Constant):  # identity/help/exit
                        rule["reply"] = call.value
                    elif (isinstance(call, ast.Call)
                          and isinstance(call.func, ast.Attribute)
                          and call.func.value.id == "random"
                          and call.func.attr == "choice"):
                        rule["reply"] = str_list(call.args[0])
                    elif isinstance(call, ast.Call) and isinstance(
                            call.func, ast.Attribute):
                        meth = call.func.attr
                        a = call.args
                        kw = {k.arg: const(k.value) for k in call.keywords
                              if isinstance(k.value, ast.Constant)}
                        if meth == "_open_url":
                            rule.update(tool="open_website",
                                        args={"url_or_name": const(a[0])},
                                        reply=const(a[1]))
                        elif meth == "_press_key":
                            rule.update(tool="keyboard_mouse_action",
                                        args={"action": "press_key",
                                              "value": const(a[0])},
                                        reply=const(a[1]))
                        elif meth == "_hotkey":
                            keys = str_list(a[0])
                            rule.update(tool="keyboard_mouse_action",
                                        args={"action": "press_hotkey",
                                              "value": "+".join(keys)},
                                        reply=const(a[1]))
                        elif meth == "_launch_app":
                            cmd = const(a[0])
                            rule.update(tool="open_application",
                                        args={"app_name": LAUNCH_NORMALIZE.get(
                                            cmd.strip().lower(), cmd)},
                                        reply=const(a[1]))
                        elif meth == "_change_volume":
                            up = kw.get("up", True)
                            # Legacy pressed N times; the ToolSpec does one
                            # step per call (behavior change, now gated).
                            rule.update(tool="system_control",
                                        args={"action": "volume_up" if up else "volume_down"},
                                        reply=kw.get("msg") or (
                                            "Volume increased" if up else "Volume decreased"))
                        elif meth == "_gated":
                            tool_name = const(a[0])
                            args = {const(k): const(v)
                                    for k, v in zip(a[1].keys, a[1].values)}
                            ok = const(a[2]) if len(a) > 2 else None
                            rule.update(tool=tool_name, args=args, reply=ok)
                        elif meth == "_action_scroll":
                            down = kw.get("down", True)
                            # No scroll ToolSpec: closest gated equivalent.
                            rule.update(tool="keyboard_mouse_action",
                                        args={"action": "press_key",
                                              "value": "pagedown" if down else "pageup"},
                                        reply="Scrolled down" if down else "Scrolled up")
                        elif meth in COMPUTE_IDS:
                            rule["compute"] = COMPUTE_IDS[meth]
                        elif meth in SIMPLE_GATED:
                            tool, args, reply = SIMPLE_GATED[meth]
                            rule.update(tool=tool, args=args, reply=reply)
                        else:
                            raise ValueError(f"unhandled lambda method {meth} in {rid}")
                    else:
                        raise ValueError(f"unhandled lambda in {rid}: {ast.dump(call)[:100]}")
                elif isinstance(act, ast.Attribute):
                    # method refs not covered by HANDWRITTEN
                    raise ValueError(f"unhandled methodref {act.attr} in {rid}")
                else:
                    raise ValueError(f"unhandled action in {rid}")
                rules.append(rule)

    # ---- emit ----
    lines = ['"""Reflex rule data — AST-extracted from the legacy voice command table.',
             '',
             'DO NOT EDIT BY HAND. Regenerate with scripts/extract_reflex_rules.py',
             'after changing src/jarvis/voice/interface.py.',
             '',
             'Each rule: patterns -> ToolSpec call (policy-gated by the router)',
             'or a computed/reply-only response. Template syntax in args/reply:',
             '  {groupN}            regex group N (1-based)',
             '  {groupN|urlencode}  URL-encoded group',
             '  {groupN|default:X}  X when the group is empty/missing',
             '"""',
             '',
             'RULES = [']
    for r in rules:
        lines.append('    {')
        lines.append(f'        "id": {r["id"]!r},')
        lines.append('        "patterns": [')
        for p in r["patterns"]:
            lines.append(f'            {p!r},')
        lines.append('        ],')
        lines.append(f'        "tool": {r["tool"]!r},')
        lines.append(f'        "args": {r["args"]!r},')
        lines.append(f'        "reply": {r["reply"]!r},')
        lines.append(f'        "compute": {r["compute"]!r},')
        lines.append('    },')
    lines.append(']')
    lines.append('')
    lines.append(f'JOKES = {JOKES!r}')
    lines.append('')
    open(OUT, "w").write("\n".join(lines) + "\n")
    print(f"wrote {len(rules)} rules, skipped {len(skipped)}: {skipped}")


if __name__ == "__main__":
    main()
