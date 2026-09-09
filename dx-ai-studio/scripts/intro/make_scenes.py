"""인트로의 세 장면을 그린다.

스톡 사진을 쓰지 않는 이유: 우리가 가진 것들은 톤이 제각각이고 이미 AI 오버레이가
구워져 있어서, 검은 무대 위에 얹으면 인트로가 아니라 브로슈어가 된다. 벡터로 직접
그리면 해상도에 상관없이 선명하고, 의존성이 0 이고, 팔레트를 무대와 정확히 맞출 수
있다 (accent 는 --accent #2997ff 그대로).

세 장면은 work 박자의 세 요청에 각각 대응한다. 실리콘이 마지막인 건 의도적이다 —
앞의 두 세상이 그 위에서 돈다.

    python scripts/intro/make_scenes.py
"""
import pathlib

OUT = pathlib.Path(__file__).resolve().parents[2] / 'launcher/static/img/intro'
HEAD = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 318" '
        'width="600" height="318" fill="none" role="img">')
INK, ACC, AMBER, GREEN = '#05070c', '#2997ff', '#e0a92e', '#1f6f63'
LINE = 'rgba(255,255,255,.08)'
FONT = '-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif'
MONO = 'ui-monospace,SFMono-Regular,Menlo,monospace'


def person_path(cx, base, h):
    w, hr = h * .30, h * .108
    return (f'<circle cx="{cx:.1f}" cy="{base-h+hr:.1f}" r="{hr:.1f}"/>'
            f'<path d="M{cx-w*.5:.1f} {base:.1f}C{cx-w*.56:.1f} {base-h*.45:.1f} '
            f'{cx-w*.60:.1f} {base-h*.64:.1f} {cx-w*.38:.1f} {base-h*.71:.1f}'
            f'L{cx+w*.38:.1f} {base-h*.71:.1f}C{cx+w*.60:.1f} {base-h*.64:.1f} '
            f'{cx+w*.56:.1f} {base-h*.45:.1f} {cx+w*.5:.1f} {base:.1f}Z"/>')


def car_path(cx, base, w):
    h = w * .44
    return (f'<path d="M{cx-w*.5:.1f} {base:.1f}v{-h*.44:.1f}q0 {-h*.17:.1f} {w*.10:.1f} {-h*.21:.1f}'
            f'l{w*.12:.1f} {-h*.32:.1f}q{w*.03:.1f} {-h*.10:.1f} {w*.10:.1f} {-h*.10:.1f}'
            f'h{w*.36:.1f}q{w*.07:.1f} 0 {w*.10:.1f} {h*.10:.1f}l{w*.12:.1f} {h*.32:.1f}'
            f'q{w*.10:.1f} {h*.04:.1f} {w*.10:.1f} {h*.21:.1f}v{h*.44:.1f}Z"/>')


def bbox_of_person(cx, base, h):
    w = h * .30
    return cx - w * .72, base - h, w * 1.44, h


def bbox_of_car(cx, base, w):
    h = w * .44
    return cx - w * .54, base - h - 2, w * 1.08, h + 4


def corners(x, y, w, h, c, t=8, sw=1.4):
    p = []
    for (cx, cy, dx, dy) in ((x, y, 1, 1), (x+w, y, -1, 1), (x, y+h, 1, -1), (x+w, y+h, -1, -1)):
        p.append(f'M{cx+dx*t:.1f} {cy:.1f}H{cx:.1f}V{cy+dy*t:.1f}')
    return f'<path d="{"".join(p)}" stroke="{c}" stroke-width="{sw}" stroke-linecap="square"/>'


# ── 1. 4채널 객체 검출 ───────────────────────────────────────
def detect():
    s = [HEAD, '<defs>'
         '<linearGradient id="pg" x1="0" y1="0" x2="0" y2="1">'
         '<stop offset="0" stop-color="#0b1220"/><stop offset=".62" stop-color="#080d16"/>'
         '<stop offset="1" stop-color="#0a111c"/></linearGradient>'
         '<linearGradient id="sil" x1="0" y1="0" x2="0" y2="1">'
         '<stop offset="0" stop-color="#b9cde8" stop-opacity=".52"/>'
         '<stop offset="1" stop-color="#7d96b8" stop-opacity=".22"/></linearGradient>'
         '<filter id="sb" x="-30%" y="-30%" width="160%" height="160%">'
         '<feGaussianBlur stdDeviation="2.1"/></filter></defs>',
         f'<rect width="600" height="318" fill="{INK}"/>']
    chans = [
        [('p', 78, 118, 62), ('p', 132, 122, 50), ('v', 214, 124, 74)],
        [('v', 128, 126, 104)],
        [('p', 56, 120, 58), ('p', 104, 124, 66), ('p', 158, 118, 52), ('p', 222, 122, 60)],
        [('p', 140, 124, 70), ('p', 190, 120, 46)],
    ]
    warm = {1: 0}
    for i, subs in enumerate(chans):
        ox, oy = 12 + (i % 2) * 294, 12 + (i // 2) * 153
        live = (i == 2)
        s.append(f'<g transform="translate({ox} {oy})">')
        s.append(f'<rect width="282" height="141" rx="7" fill="url(#pg)" '
                 f'stroke="{ACC if live else LINE}" stroke-opacity="{.45 if live else 1}"/>')
        s.append('<g clip-path="inset(0 round 7)">')
        s.append(f'<path d="M0 96H282" stroke="{LINE}"/>')
        s.append(f'<path d="M96 141 138 96M186 141 144 96" stroke="{LINE}" stroke-opacity=".55"/>')
        shapes, boxes = [], []
        for kind, cx, base, size in subs:
            if kind == 'p':
                shapes.append(person_path(cx, base, size)); boxes.append(bbox_of_person(cx, base, size))
            else:
                shapes.append(car_path(cx, base, size)); boxes.append(bbox_of_car(cx, base, size))
        s.append(f'<g fill="url(#sil)" filter="url(#sb)">{"".join(shapes)}</g>')
        for k, (bx, by, bw, bh) in enumerate(boxes):
            c = AMBER if warm.get(i) == k else ACC
            s.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="2" '
                     f'stroke="{c}" stroke-opacity=".26"/>')
            s.append(corners(bx, by, bw, bh, c))
            s.append(f'<rect x="{bx:.1f}" y="{by-7:.1f}" width="{min(bw, 24):.1f}" height="3" rx="1.5" fill="{c}"/>')
        s.append('</g>')
        s.append(f'<text x="13" y="24" font-family="{MONO}" font-size="9.5" letter-spacing=".6" '
                 f'fill="#fff" fill-opacity="{.55 if live else .28}">{i+1:02d}</text>')
        if live:
            s.append(f'<circle cx="269" cy="20" r="2.6" fill="{ACC}"/>')
        s.append('</g>')
    return ''.join(s) + '</svg>'


# ── 2. 시맨틱 분할 ───────────────────────────────────────────
def segment():
    H, LEG = 112, 286
    classes = [('sky', '#1b3a63'), ('building', '#24406b'), ('road', '#161e2d'),
               ('vehicle', ACC), ('person', AMBER), ('vegetation', GREEN)]
    s = [HEAD, '<defs>'
         '<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">'
         '<stop offset="0" stop-color="#0f2444"/><stop offset="1" stop-color="#22456f"/></linearGradient>'
         '<linearGradient id="road" x1="0" y1="0" x2="0" y2="1">'
         '<stop offset="0" stop-color="#101826"/><stop offset="1" stop-color="#1b2436"/></linearGradient>'
         '</defs>',
         f'<rect width="600" height="318" fill="{INK}"/>', '<g clip-path="inset(0)">',
         f'<rect width="600" height="{LEG}" fill="url(#sky)"/>',
         f'<path d="M0 {LEG}V42h40V22h34v34h28V12h48v46h30V34h38v206Z" fill="#24406b"/>',
         f'<path d="M600 {LEG}V30h-46V8h-36v40h-30V22h-42v40h-26V40h-36v206Z" fill="#1d3559"/>',
         f'<path d="M0 {LEG} 228 {H}h144l228 {LEG-H}Z" fill="url(#road)"/>',
         f'<path d="M0 {LEG} 228 {H}h30L96 {LEG}Z" fill="#1b2334"/>',
         f'<path d="M600 {LEG} 372 {H}h-30l162 {LEG-H}Z" fill="#1b2334"/>',
         f'<path d="M296 {H+26}h9l-3 15h-10ZM288 {H+56}h11l-4 20h-13ZM276 {H+94}h14l-6 28h-17Z" '
         f'fill="#3d5175" opacity=".8"/>']
    # 나무는 인도 안쪽, 사람과 겹치지 않는 자리에
    for cx, base, h in ((196, 276, 32), (446, 262, 27)):
        s.append(f'<g fill="{GREEN}"><rect x="{cx-1.6:.1f}" y="{base-h*.34:.1f}" width="3.2" '
                 f'height="{h*.34:.1f}" opacity=".8"/><ellipse cx="{cx}" cy="{base-h*.62:.1f}" '
                 f'rx="{h*.30:.1f}" ry="{h*.34:.1f}"/></g>')
    # 차선을 나눠 세워 겹치지 않게 한다
    s.append(f'<g fill="{ACC}">{car_path(340, 210, 96)}</g>')
    s.append(f'<g fill="{ACC}" opacity=".62">{car_path(268, 150, 46)}</g>')
    # 사람은 인도 위에 — 도로 폴리곤 안에 두면 분할 결과가 거짓말이 된다
    s.append(f'<g fill="{AMBER}">'
             + person_path(66, 268, 50) + person_path(88, 250, 40)
             + person_path(534, 254, 42) + '</g>')
    s.append(f'<path d="M0 {H}h600" stroke="#fff" stroke-opacity=".05"/>')
    s.append('</g>')
    s.append(f'<rect y="{LEG}" width="600" height="{318-LEG}" fill="#070a10"/>')
    s.append(f'<path d="M0 {LEG}.5h600" stroke="#fff" stroke-opacity=".07"/>')
    for i, (name, col) in enumerate(classes):
        x = 18 + i * 96
        s.append(f'<rect x="{x}" y="{LEG+11}" width="8" height="8" rx="2" fill="{col}"/>')
        s.append(f'<text x="{x+13}" y="{LEG+18.5}" font-family="{FONT}" font-size="9" '
                 f'fill="#fff" fill-opacity=".58">{name}</text>')
    return ''.join(s) + '</svg>'


# ── 3. 실리콘 ────────────────────────────────────────────────
def silicon():
    PX, PY, PS = 184, 40, 232
    s = [HEAD, '<defs>'
         '<linearGradient id="pkg" x1="0" y1="0" x2=".35" y2="1">'
         '<stop offset="0" stop-color="#68717e"/><stop offset=".42" stop-color="#2b323c"/>'
         '<stop offset="1" stop-color="#151920"/></linearGradient>'
         '<linearGradient id="die" x1="0" y1="0" x2=".4" y2="1">'
         '<stop offset="0" stop-color="#111925"/><stop offset="1" stop-color="#070b12"/></linearGradient>'
         '<linearGradient id="rake" x1="0" y1="0" x2="1" y2="1">'
         '<stop offset=".30" stop-color="#fff" stop-opacity="0"/>'
         '<stop offset=".45" stop-color="#fff" stop-opacity=".18"/>'
         '<stop offset=".57" stop-color="#fff" stop-opacity="0"/></linearGradient>'
         '<radialGradient id="halo" cx=".5" cy=".5" r=".5">'
         '<stop offset="0" stop-color="#2997ff" stop-opacity=".30"/>'
         '<stop offset=".62" stop-color="#2997ff" stop-opacity=".07"/>'
         '<stop offset="1" stop-color="#2997ff" stop-opacity="0"/></radialGradient>'
         '<linearGradient id="fadeL" x1="1" y1="0" x2="0" y2="0">'
         '<stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
         '<linearGradient id="fadeR" x1="0" y1="0" x2="1" y2="0">'
         '<stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
         f'<mask id="mL"><rect width="{PX}" height="318" fill="url(#fadeL)"/></mask>'
         f'<mask id="mR"><rect x="{PX+PS}" width="{600-PX-PS}" height="318" fill="url(#fadeR)"/></mask>'
         '</defs>',
         f'<rect width="600" height="318" fill="{INK}"/>',
         '<ellipse cx="300" cy="158" rx="236" ry="146" fill="url(#halo)"/>']
    L, R = [], []
    for i in range(11):
        y = PY + 14 + i * 20.4
        run = 44 + (i % 4) * 26
        L.append(f'M{PX} {y:.1f}H{PX-run}')
        R.append(f'M{PX+PS} {y:.1f}H{PX+PS+run}')
    s.append(f'<g stroke="{ACC}" stroke-opacity=".34">'
             f'<path d="{"".join(L)}" mask="url(#mL)"/>'
             f'<path d="{"".join(R)}" mask="url(#mR)"/></g>')
    s.append(f'<g transform="translate({PX} {PY})">')
    s.append(f'<rect width="{PS}" height="{PS}" rx="12" fill="url(#pkg)"/>')
    s.append(f'<rect x="1" y="1" width="{PS-2}" height="{PS-2}" rx="11" stroke="#fff" stroke-opacity=".14"/>')
    s.append('<rect x="18" y="18" width="196" height="196" rx="5" fill="url(#die)" stroke="#fff" stroke-opacity=".08"/>')
    for (bx, by, bw, bh, op) in [(28, 28, 92, 92, .34), (128, 28, 76, 44, .17), (128, 82, 34, 38, .17),
                                 (170, 82, 34, 38, .24), (28, 130, 44, 84, .17), (82, 130, 38, 40, .14),
                                 (82, 180, 38, 34, .20), (128, 130, 76, 40, .14), (128, 180, 76, 34, .17)]:
        s.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="3" fill="{ACC}" '
                 f'fill-opacity="{op}" stroke="{ACC}" stroke-opacity=".32"/>')
    s.append('<path d="' + ''.join(f'M{36+c*14} {36+r*14}h8v8h-8Z' for r in range(6) for c in range(6))
             + '" fill="#9fd0ff" fill-opacity=".24"/>')
    s.append('<rect x="18" y="18" width="196" height="196" rx="5" fill="url(#rake)"/>')
    s.append(f'<text x="116" y="248" text-anchor="middle" font-family="{FONT}" font-size="11" '
             f'font-weight="600" letter-spacing="2.2" fill="#fff" fill-opacity=".8">DX-M1</text>')
    return ''.join(s) + '</g></svg>'


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in (('scene-detect', detect), ('scene-segment', segment), ('scene-silicon', silicon)):
        path = OUT / f'{name}.svg'
        path.write_text(fn(), encoding='utf-8')
        print(f'{path.name:22s} {path.stat().st_size:6d} bytes')
