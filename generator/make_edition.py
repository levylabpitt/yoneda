"""
make_edition.py: build a lab's book edition from its profile.

Given a group profile JSON (with a lab_slots map) and the book-template, write a
profile-<lab>.tex that fills the template's \\lab... slots, and a
compendium-<lab>.tex that inputs it. Slots the lab does not define fall back to
the template's generic \\providecommand defaults.

Usage: python make_edition.py <profile.json> <lab_key>
"""
import json, re, sys, os

TPL = os.path.join(os.path.dirname(__file__), "book-template")

def template_slots():
    txt = open(os.path.join(TPL, "slots.tex"), encoding="utf-8").read()
    return set(re.findall(r"\\providecommand\{\\(lab[A-Za-z]+)\}", txt))

def main():
    prof_path, lab = sys.argv[1], sys.argv[2]
    prof = json.load(open(prof_path, encoding="utf-8"))
    slots = prof.get("lab_slots", {})
    tpl = template_slots()

    # normalize keys: accept "labX" or "\\labX"
    norm = {}
    for k, v in slots.items():
        name = k[1:] if k.startswith("\\") else k
        val = v if isinstance(v, str) else (v.get("value") if isinstance(v, dict) else str(v))
        if val:
            norm[name] = val

    filled = [n for n in norm if n in tpl]
    unknown = [n for n in norm if n not in tpl]        # lab named a slot the template lacks
    missing = [n for n in tpl if n not in norm]        # template slot the lab did not fill

    # write profile-<lab>.tex
    lines = [f"% {lab} edition profile. Generated from {os.path.basename(prof_path)}.",
             f"% Fills {len(filled)} of {len(tpl)} template slots; the rest use the generic",
             f"% defaults in slots.tex.", ""]
    def esc(s):
        return (s.replace("\\", "\\textbackslash{}").replace("&", "\\&")
                 .replace("%", "\\%").replace("_", "\\_").replace("#", "\\#")
                 .replace("$", "\\$"))
    for n in sorted(filled):
        lines.append(f"\\renewcommand{{\\{n}}}{{{esc(norm[n])}}}")
    open(os.path.join(TPL, f"profile-{lab}.tex"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

    # write compendium-<lab>.tex: same as compendium.tex but swap the profile input
    comp = open(os.path.join(TPL, "compendium.tex"), encoding="utf-8").read()
    comp = comp.replace("profile-levylab", f"profile-{lab}")
    open(os.path.join(TPL, f"compendium-{lab}.tex"), "w", encoding="utf-8").write(comp)

    print(f"edition: {lab}")
    print(f"  filled {len(filled)}/{len(tpl)} template slots")
    print(f"  lab named {len(unknown)} slots the template does not have: {unknown[:8]}")
    print(f"  {len(missing)} template slots fall back to generic defaults")
    print(f"  wrote profile-{lab}.tex and compendium-{lab}.tex")
    # report the most important missing ones (materials/instruments/formats)
    key_missing = [m for m in missing if any(w in m.lower() for w in
                   ("material","instrument","format","sample","cold","measure","field","colleague"))]
    if key_missing:
        print(f"  NOTE: key tissue slots not filled by the lab (will read generic): {key_missing}")

if __name__ == "__main__":
    main()
