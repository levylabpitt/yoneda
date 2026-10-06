r"""
build-slots-manifest.py: extract the 202 book-template slots into slots-manifest.json,
which the site Worker bundles and feeds to Workers AI as slot-fill context.

Reads generator/book-template/slots.tex and emits, for every
  \providecommand{\labName}[opt]{default}
an entry { name: { "default": <default text>, "arity": <n> } }.

Run from anywhere: python site/build-slots-manifest.py
"""
import re, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
SLOTS = os.path.join(HERE, "..", "generator", "book-template", "slots.tex")
OUT = os.path.join(HERE, "slots-manifest.json")

txt = open(SLOTS, encoding="utf-8").read()
pat = re.compile(r"\\providecommand\{\\(lab[A-Za-z]+)\}(\[\d+\])?\{")

slots = {}
for m in pat.finditer(txt):
    name = m.group(1)
    arity = int(m.group(2)[1:-1]) if m.group(2) else 0
    # balanced-brace scan starting at the '{' captured at m.end()-1
    j = m.end() - 1
    depth = 0
    start = j
    while j < len(txt):
        c = txt[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        j += 1
    default = txt[start + 1:j].strip()
    slots[name] = {"default": default, "arity": arity}

json.dump(slots, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"count {len(slots)}")
print("arity>0:", [k for k, v in slots.items() if v["arity"] > 0])
print(f"wrote {OUT}")
