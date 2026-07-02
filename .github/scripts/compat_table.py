#!/usr/bin/env python3
"""Splice the top DXNN version-compatibility block in one or more markdown files.

suite unchanged  -> replace the top block in-place (same row)
suite changed    -> prepend a new block
nothing changed  -> leave file untouched (no date churn)

DX-TRON is carried forward verbatim (deprecated, never auto-updated / never bolded).
Bold rule: only when the DX-AllSuite version is a PATCH bump (x.x.PATCH up) vs the
previous release — then changed component cells are bolded. A MINOR/MAJOR bump
(x.MINOR.x / MAJOR.x.x up) leaves the whole block plain.
"""
import re, sys, argparse

TBODY_RE = re.compile(r'(<tbody[^>]*>)(.*?)(</tbody>)', re.S)
TR_RE = re.compile(r'<tr>.*?</tr>', re.S)
TD_RE = re.compile(r'<td[^>]*>(.*?)</td>', re.S)

# td order within a 3-row block
KEYS = ["date", "suite", "compiler", "runtime",
        "dxcom", "dxtron", "dxfw", "driver", "dxrt", "dxstream", "dxapp"]


def bare(cell):
    return re.sub(r'</?b>', '', cell).strip()


def parse_block(three_trs):
    tds = []
    for tr in three_trs:
        tds += TD_RE.findall(tr)
    if len(tds) != 11:
        sys.exit(f"unexpected td count {len(tds)} in block (want 11)")
    return dict(zip(KEYS, [bare(t) for t in tds]))


def fmt(val, prev):
    return f"<b>{val}</b>" if prev is not None and val != prev else val


def ver_tuple(s):
    n = [int(x) for x in re.findall(r'\d+', s)]
    return tuple((n + [0, 0, 0])[:3])


def is_patch_bump(new_s, prev_s):
    a, b = ver_tuple(new_s), ver_tuple(prev_s)
    return a[0] == b[0] and a[1] == b[1] and a[2] != b[2]


def build_block(v, prev):
    def p(k):
        return prev.get(k) if prev else None
    return (
        f'<tr>\n'
        f'      <td rowspan="3">{v["date"]}</td>\n'
        f'      <td colspan="7">{v["suite"]}</td>\n'
        f'    </tr>\n'
        f'    <tr>\n'
        f'      <td colspan="2">{fmt(v["compiler"], p("compiler"))}</td>\n'
        f'      <td colspan="5">{fmt(v["runtime"], p("runtime"))}</td>\n'
        f'    </tr>\n'
        f'    <tr>\n'
        f'      <td>{fmt(v["dxcom"], p("dxcom"))}</td>\n'
        f'      <td>{v["dxtron"]}</td>\n'
        f'      <td>{fmt(v["dxfw"], p("dxfw"))}</td>\n'
        f'      <td>{fmt(v["driver"], p("driver"))}</td>\n'
        f'      <td>{fmt(v["dxrt"], p("dxrt"))}</td>\n'
        f'      <td>{fmt(v["dxstream"], p("dxstream"))}</td>\n'
        f'      <td>{fmt(v["dxapp"], p("dxapp"))}</td>\n'
        f'    </tr>'
    )


def process(path, new):
    text = open(path, encoding="utf-8").read()
    m = TBODY_RE.search(text)
    if not m:
        sys.exit(f"<tbody> not found: {path}")
    inner = m.group(2)
    trs = list(TR_RE.finditer(inner))
    if not trs or len(trs) % 3 != 0:
        sys.exit(f"bad <tr> count {len(trs)} in {path}")

    top = parse_block([trs[0].group(), trs[1].group(), trs[2].group()])
    second = parse_block([trs[3].group(), trs[4].group(), trs[5].group()]) if len(trs) >= 6 else None

    v = dict(new)
    v["dxtron"] = top["dxtron"]  # carry forward, never touched

    comp_keys = ["compiler", "runtime", "dxcom", "dxfw", "driver", "dxrt", "dxstream", "dxapp"]
    suite_changed = v["suite"] != top["suite"]
    comps_changed = any(v[k] != top[k] for k in comp_keys)

    if not suite_changed and not comps_changed:
        return False  # untouched, no date churn

    # previous release = old top (prepend) or the block below (in-place)
    prev = top if suite_changed else second
    bold_vs = prev if (prev and is_patch_bump(v["suite"], prev["suite"])) else None

    b0_start = trs[0].start()
    b0_end = trs[2].end()
    if suite_changed:  # prepend a new block
        block = build_block(v, bold_vs)
        new_inner = inner[:b0_start] + block + "\n    " + inner[b0_start:]
    else:              # replace the top row in-place
        block = build_block(v, bold_vs)
        new_inner = inner[:b0_start] + block + inner[b0_end:]

    new_text = text[:m.start(2)] + new_inner + text[m.end(2):]
    open(path, "w", encoding="utf-8").write(new_text)
    return True


def main():
    ap = argparse.ArgumentParser()
    for k in ["date", "suite", "compiler", "runtime",
              "dxcom", "dxfw", "driver", "dxrt", "dxstream", "dxapp"]:
        ap.add_argument("--" + k, required=True)
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    new = {k: getattr(a, k) for k in
           ["date", "suite", "compiler", "runtime",
            "dxcom", "dxfw", "driver", "dxrt", "dxstream", "dxapp"]}
    for f in a.files:
        r = process(f, new)
        print(("updated  " if r else "unchanged ") + f)


if __name__ == "__main__":
    main()
