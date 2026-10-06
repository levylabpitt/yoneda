r"""
fill_codeblocks.py: the other half of the fill step.

LaTeX macros (\input profile) fill PROSE tissue. But macros do NOT expand inside
verbatim / Check / lstlisting environments, nor inside inline \verb, so slot
tokens print literally there. This does what the macro layer cannot: a scoped
TEXT substitution of \labXxx tokens with RAW values, but ONLY inside code
contexts, leaving prose to the macros. Produces a filled build tree and compiles.

Usage: python fill_codeblocks.py <lab_key>
  (expects generator/book-template/profile-<lab>.tex to exist)
"""
import re, os, sys, shutil, subprocess

TPL = os.path.join(os.path.dirname(__file__), "book-template")
CODE_ENVS = ("verbatim", "Check", "lstlisting")

def unescape(v):
    return (v.replace(r"\textbackslash{}", "\\").replace(r"\&", "&")
             .replace(r"\%", "%").replace(r"\_", "_").replace(r"\#", "#")
             .replace(r"\$", "$"))

def load_profile(lab):
    txt = open(os.path.join(TPL, f"profile-{lab}.tex"), encoding="utf-8").read()
    slots = {}
    for m in re.finditer(r"\\renewcommand\{\\(lab[A-Za-z]+)\}(?:\[\d+\])?\{(.*)\}\s*$", txt, re.M):
        slots[m.group(1)] = unescape(m.group(2))
    return slots

def _sub_tokens(block, slots):
    def repl(m):
        return slots.get(m.group(1), m.group(0))
    block = re.sub(r"!\\(lab[A-Za-z]+)!", repl, block)   # listings escape wrappers
    block = re.sub(r"\\(lab[A-Za-z]+)\{\}", repl, block)
    block = re.sub(r"\\(lab[A-Za-z]+)\b", repl, block)
    return block

def fill_code(text, slots):
    out, i = [], 0
    pat = re.compile(r"\\begin\{(" + "|".join(CODE_ENVS) + r")\}(.*?)\\end\{\1\}", re.S)
    for m in pat.finditer(text):
        out.append(text[i:m.start()])
        out.append("\\begin{" + m.group(1) + "}")
        out.append(_sub_tokens(m.group(2), slots))
        out.append("\\end{" + m.group(1) + "}")
        i = m.end()
    out.append(text[i:])
    text2 = "".join(out)
    # inline \verb<delim>...<delim>
    def verb_repl(m):
        delim, inner = m.group(1), m.group(2)
        for name in sorted(slots, key=len, reverse=True):
            inner = inner.replace("\\" + name, slots[name])
        return "\\verb" + delim + inner + delim
    text2 = re.sub(r"\\verb(.)(.*?)\1", verb_repl, text2)
    return text2

def main():
    lab = sys.argv[1]
    slots = load_profile(lab)
    build = os.path.join(TPL, f"build-{lab}")
    if os.path.exists(build):
        try: shutil.rmtree(build)
        except Exception: pass
    os.makedirs(os.path.join(build, "chapters"), exist_ok=True)
    n_sub = 0
    for f in sorted(os.listdir(os.path.join(TPL, "chapters"))):
        if not f.endswith(".tex"): continue
        src = open(os.path.join(TPL, "chapters", f), encoding="utf-8").read()
        filled = fill_code(src, slots)
        n_sub += len(re.findall(r"\\lab[A-Za-z]+", src)) - len(re.findall(r"\\lab[A-Za-z]+", filled))
        open(os.path.join(build, "chapters", f), "w", encoding="utf-8").write(filled)
    for f in ("slots.tex", f"profile-{lab}.tex", "tiers.sty"):
        shutil.copy(os.path.join(TPL, f), os.path.join(build, f))
    comp = open(os.path.join(TPL, "compendium.tex"), encoding="utf-8").read().replace("profile-levylab", f"profile-{lab}")
    open(os.path.join(build, "compendium.tex"), "w", encoding="utf-8").write(comp)
    print(f"build-{lab}: substituted {n_sub} slot tokens in code contexts")
    r = subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "compendium.tex"],
                       cwd=build, capture_output=True, text=True)
    pdf = os.path.join(build, "compendium.pdf")
    print("  latexmk exit:", r.returncode, "| pdf:", os.path.exists(pdf))
    if os.path.exists(pdf):
        txt = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
        real = sorted(set(re.findall(r"lab[A-Z][A-Za-z]+", txt)))
        print(f"  unexpanded macros left: {len(real)}", real[:6])

if __name__ == "__main__":
    main()
