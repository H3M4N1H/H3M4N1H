#!/usr/bin/env python3
"""
Generate the animated, theme-aware profile banner (dark.svg + light.svg).

Left:  TARGET.SCAN - a dithered pixel portrait built from assets/portrait.jpeg.
       Pixels fade in, a scanline sweeps the panel, then on a loop the portrait
       dissolves into particles that spell the handle and reassemble.
Right: SYSTEM.INFO - neofetch-style profile readout with dotted leaders.

Edit PROFILE / INFO / CONTACT below, then run locally:
    pip install pillow numpy
    python3 .github/scripts/generate_banner.py
"""
import html, os, random
from collections import deque

import numpy as np
from PIL import Image, ImageOps

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PORTRAIT = os.path.join(ROOT, "assets", "portrait.jpeg")
# crop box on the source photo (left, top, right) - height follows the panel aspect
CROP = (40, 140, 1010)

HANDLE = "H3M4N1H"
SUBLINE = "> CYBERSEC"
PILL = "H3M4N1H"
TITLE = "h3m4n1h@kali - % ./profile.sh --live"

INFO = [
    ("Subject", "P Hemanth Gupta"),
    ("Role", "Cybersecurity Engineer in the Making"),
    ("Focus", "Offensive Security / CTF Player / Developer"),
    ("Origin", "Chennai, India"),
    ("Education", "B.E. CSE (Cyber Security), VEC '28"),
    ("Status", "Building. Breaking. Learning. Shipping."),
    None,  # spacer
    ("Core.Lang", "Python, JavaScript, TypeScript, C, SQL, Bash"),
    ("Core.Web", "React, Next.js, Tailwind, Flask, Node.js"),
    ("Core.Data", "SQLite, PostgreSQL"),
    ("Core.Infra", "Docker, Linux, Git, Vercel, Render"),
    ("Sec.Arsenal", "Burp, Nmap, Wireshark, Metasploit, SQLMap"),
    ("AI.Stack", "Gemini API, Ollama, scikit-learn"),
]
CONTACT = [
    ("Grid.Mail", "krishnahemanth100@gmail.com"),
    ("Grid.Portfolio", "nodekraft.tech"),
    ("Grid.LinkedIn", "p-hemanth-gupta-657b05353"),
    ("Grid.GitHub", "@H3M4N1H"),
    ("Grid.TryHackMe", "BlackPantherX"),
    ("Grid.CTFtime", "user/235934"),
]

THEMES = {
    "dark": {
        "FRAME": "#070B16", "BG0": "#0A101F", "BG1": "#0C1426", "BAR": "#0B1222",
        "BARLINE": "rgba(255,255,255,0.10)", "PANEL": "#0A101F",
        "PANEL_STROKE": "rgba(34,211,238,0.35)", "PIXEL": "#A78BFA",
        "CYAN": "#22D3EE", "VIOLET": "#A78BFA", "VIOLET2": "#7C3AED", "EMERALD": "#10B981",
        "TEXT": "#F8FAFC", "MUTED": "#94A3B8", "DIM": "#475569",
        "LEADER": "rgba(148,163,184,0.35)", "PILL_BG": "#4C1D95", "PILL_TX": "#E9D5FF",
        "RED": "#F87171",
    },
    "light": {
        "FRAME": "#E2E8F0", "BG0": "#F8FAFC", "BG1": "#FFFFFF", "BAR": "#F1F5F9",
        "BARLINE": "rgba(0,0,0,0.08)", "PANEL": "#FFFFFF",
        "PANEL_STROKE": "rgba(8,145,178,0.35)", "PIXEL": "#7C3AED",
        "CYAN": "#0891B2", "VIOLET": "#7C3AED", "VIOLET2": "#7C3AED", "EMERALD": "#059669",
        "TEXT": "#0F172A", "MUTED": "#475569", "DIM": "#94A3B8",
        "LEADER": "rgba(71,85,105,0.35)", "PILL_BG": "#EDE9FE", "PILL_TX": "#5B21B6",
        "RED": "#DC2626",
    },
}

# ---------------- layout ----------------
W, H = 1180, 650
FONT = "ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace"
PX, PY, PW, PH = 36, 84, 400, 532          # portrait panel
GW, GH, GS = 186, 262, 2                   # portrait grid (cells) and cell scale
GX, GY = PX + (PW - GW * GS) // 2, PY + 4  # portrait origin
REVEAL_END = 3.2                           # seconds until the portrait is complete
CYCLE = 14.0                               # dissolve/reassemble loop length

# 5x7 pixel font for the particle text
GLYPHS = {
    "H": "10001 10001 10001 11111 10001 10001 10001",
    "3": "11110 00001 00001 01110 00001 00001 11110",
    "M": "10001 11011 10101 10101 10001 10001 10001",
    "4": "00010 00110 01010 10010 11111 00010 00010",
    "N": "10001 11001 10101 10011 10001 10001 10001",
    "1": "00100 01100 00100 00100 00100 00100 01110",
    "C": "01110 10001 10000 10000 10000 10001 01110",
    "Y": "10001 10001 01010 00100 00100 00100 00100",
    "B": "11110 10001 10001 11110 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111",
    "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110",
    ">": "10000 01000 00100 00010 00100 01000 10000",
    " ": "00000 00000 00000 00000 00000 00000 00000",
}


def esc(s):
    return html.escape(str(s), quote=True)


# ---------------- portrait ----------------
def portrait_bits(theme):
    """1-bit dithered portrait on a GW x GH grid. Background is flood-filled away."""
    im = Image.open(PORTRAIT).convert("RGB")
    x0, y0, x1 = CROP
    box = (x0, y0, x1, int(y0 + (x1 - x0) * GH / GW))
    c = im.crop(box).resize((GW, GH), Image.LANCZOS)

    rgb = np.asarray(c).astype(float)
    sat = np.asarray(c.convert("HSV"))[..., 1].astype(float)
    bg = (rgb.mean(2) > 140) & (sat < 60)

    # flood fill the bright, unsaturated backdrop from the top and side edges
    outside = np.zeros((GH, GW), bool)
    q = deque([(0, x) for x in range(GW)] + [(y, 0) for y in range(GH)] + [(y, GW - 1) for y in range(GH)])
    while q:
        y, x = q.popleft()
        if not (0 <= y < GH and 0 <= x < GW) or outside[y, x] or not bg[y, x]:
            continue
        outside[y, x] = True
        q.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
    fg = ~outside
    for y in range(GH):  # close gaps such as the white shirt between the lapels
        xs = np.nonzero(fg[y])[0]
        if len(xs):
            fg[y, xs[0]:xs[-1] + 1] = True

    g = np.asarray(ImageOps.autocontrast(c.convert("L"), cutoff=1)).astype(float)
    g = 255 * (g / 255) ** 0.85
    if theme == "light":
        g = 255 - g  # ink the shadows on a light page
    g[~fg] = 0
    return np.asarray(Image.fromarray(g.astype(np.uint8)).convert("1"))


def rle_path(bits):
    out = []
    for y in range(bits.shape[0]):
        row = bits[y]
        x = 0
        while x < len(row):
            if row[x]:
                s = x
                while x < len(row) and row[x]:
                    x += 1
                n = x - s
                out.append(f"M{s} {y}h{n}v1h-{n}z")
            else:
                x += 1
    return "".join(out)


def text_dots(text, scale, x0, y0):
    dots = []
    for i, ch in enumerate(text):
        rows = GLYPHS[ch].split()
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == "1":
                    dots.append((x0 + i * 6 * scale + rx * scale, y0 + ry * scale, scale))
    return dots


def portrait_layer(theme, t):
    rnd = random.Random(7)
    bits = portrait_bits(theme)
    s = []
    a = s.append
    tf = f'transform="translate({GX},{GY}) scale({GS})"'

    # 1) reveal: pixels fade in over random batches
    batches = 40
    assign = np.array([rnd.randrange(batches) for _ in range(bits.size)]).reshape(bits.shape)
    a(f'<g {tf} fill="{t["PIXEL"]}" shape-rendering="crispEdges">')
    a(f'<set attributeName="opacity" to="0" begin="{REVEAL_END}s"/>')
    for b in range(batches):
        begin = 0.2 + b * (REVEAL_END - 0.9) / batches
        a(f'<g opacity="0"><animate attributeName="opacity" values="0;1" dur="0.9s" begin="{begin:.2f}s" '
          f'fill="freeze" calcMode="spline" keyTimes="0;1" keySplines=".4 0 .2 1"/>'
          f'<path d="{rle_path(bits & (assign == b))}"/></g>')
    a('</g>')

    # 2) settled portrait that fades out while particles form the handle, then returns
    kt = "0;0.34;0.35;0.45;0.85;0.95;0.96;1"
    a(f'<g {tf} fill="{t["PIXEL"]}" shape-rendering="crispEdges" opacity="0">'
      f'<set attributeName="opacity" to="1" begin="{REVEAL_END}s"/>'
      f'<g><animate attributeName="opacity" values="1;1;1;0;0;1;1;1" keyTimes="{kt}" dur="{CYCLE}s" '
      f'begin="{REVEAL_END}s" repeatCount="indefinite"/><path d="{rle_path(bits)}"/></g></g>')

    # 3) particles: each starts on a lit portrait pixel and flies to a text dot
    big_w = len(HANDLE) * 24 - 4
    small_w = len(SUBLINE) * 12 - 2
    dots = text_dots(HANDLE, 4, (GW - big_w) // 2, 96) + text_dots(SUBLINE, 2, (GW - small_w) // 2, 136)
    lit = list(zip(*np.nonzero(bits)))
    a(f'<g {tf} fill="{t["PIXEL"]}" shape-rendering="crispEdges">')
    for tx, ty, sc in dots:
        sy, sx = lit[rnd.randrange(len(lit))]
        size = sc - (0.6 if sc > 2 else 0.4)
        a(f'<rect width="{size}" height="{size}" opacity="0">'
          f'<animate attributeName="opacity" values="0;0;1;1;1;1;0;0" keyTimes="{kt}" dur="{CYCLE}s" '
          f'begin="{REVEAL_END}s" repeatCount="indefinite"/>'
          f'<animateTransform attributeName="transform" type="translate" '
          f'values="{sx} {sy};{sx} {sy};{sx} {sy};{tx} {ty};{tx} {ty};{sx} {sy};{sx} {sy};{sx} {sy}" '
          f'keyTimes="{kt}" dur="{CYCLE}s" begin="{REVEAL_END}s" repeatCount="indefinite" '
          f'calcMode="spline" keySplines="0 0 1 1;0 0 1 1;.5 0 .2 1;0 0 1 1;.5 0 .2 1;0 0 1 1;0 0 1 1"/></rect>')
    a('</g>')
    return "".join(s)


# ---------------- info panel ----------------
def info_line(label, value, y, begin, t, width_chars=74):
    dots = "." * max(3, width_chars - len(label) - len(value) - 2)
    return (f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<animateTransform attributeName="transform" type="translate" values="-8 0;0 0" dur="0.4s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<text x="470" y="{y}" font-size="14" textLength="655" lengthAdjust="spacingAndGlyphs" xml:space="preserve">'
            f'<tspan fill="{t["CYAN"]}">{esc(label)} </tspan><tspan fill="{t["LEADER"]}">{dots}</tspan>'
            f'<tspan fill="{t["TEXT"]}" font-weight="600"> {esc(value)}</tspan></text></g>')


def section_line(label, y, begin, t):
    return (f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{begin:.2f}s" fill="freeze"/>'
            f'<text x="470" y="{y}" font-size="14" textLength="655" lengthAdjust="spacingAndGlyphs" xml:space="preserve">'
            f'<tspan fill="{t["MUTED"]}">- {esc(label)} </tspan><tspan fill="{t["LEADER"]}">{"-" * (72 - len(label))}</tspan></text></g>')


def info_panel(t):
    s = []
    a = s.append
    a(f'<text x="470" y="106" font-size="13" letter-spacing="2" fill="{t["CYAN"]}" filter="url(#txtGlow)">SYSTEM.INFO</text>')
    a(f'<line x1="566" y1="102" x2="1061" y2="102" stroke="{t["BARLINE"]}"/>')
    a(f'<text x="1125" y="106" text-anchor="end" font-size="12" fill="{t["RED"]}" font-weight="700"><tspan>&#9679;</tspan> LIVE'
      f'<animate attributeName="opacity" values="1;0.25;1" dur="1.6s" repeatCount="indefinite"/></text>')
    pill_w = len(PILL) * 9 + 20
    a(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="0.6s" fill="freeze"/>'
      f'<rect x="470" y="122" width="{pill_w}" height="20" rx="4" fill="{t["PILL_BG"]}"/>'
      f'<text x="480" y="136" font-size="14" font-weight="700" fill="{t["PILL_TX"]}">{esc(PILL)}</text>'
      f'<line x1="{470 + pill_w + 10}" y1="132" x2="1125" y2="132" stroke="{t["BARLINE"]}"/></g>')

    y, begin = 164, 0.9
    for row in INFO:
        if row is None:
            y += 8
            begin += 0.1
            continue
        a(info_line(*row, y, begin, t))
        y += 22
        begin += 0.11
    y += 9
    a(section_line("Contact", y, begin, t))
    y += 23
    begin += 0.12
    for row in CONTACT:
        a(info_line(*row, y, begin, t))
        y += 22
        begin += 0.11
    a(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.5s" begin="{begin + 0.2:.2f}s" fill="freeze"/>'
      f'<text x="470" y="{y + 10}" font-size="14" fill="{t["MUTED"]}">&#9656; More about me &amp; projects below in README &#8595; '
      f'<tspan fill="{t["CYAN"]}">&#9608;<animate attributeName="fill-opacity" values="1;0;1" dur="1s" repeatCount="indefinite"/></tspan></text></g>')
    return "".join(s)


# ---------------- frame ----------------
def build(theme):
    t = THEMES[theme]
    s = []
    a = s.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}" '
      f'role="img" aria-label="P Hemanth Gupta - profile.sh --live">')
    a('<defs>'
      '<linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">'
      f'<stop offset="0" stop-color="{t["VIOLET2"]}"><animate attributeName="stop-color" values="{t["VIOLET2"]};{t["CYAN"]};{t["EMERALD"]};{t["VIOLET2"]}" dur="10s" repeatCount="indefinite"/></stop>'
      f'<stop offset="0.5" stop-color="{t["CYAN"]}"><animate attributeName="stop-color" values="{t["CYAN"]};{t["EMERALD"]};{t["VIOLET2"]};{t["CYAN"]}" dur="10s" repeatCount="indefinite"/></stop>'
      f'<stop offset="1" stop-color="{t["EMERALD"]}"><animate attributeName="stop-color" values="{t["EMERALD"]};{t["VIOLET2"]};{t["CYAN"]};{t["EMERALD"]}" dur="10s" repeatCount="indefinite"/></stop>'
      '</linearGradient>'
      f'<linearGradient id="panelGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["BG0"]}"/><stop offset="1" stop-color="{t["BG1"]}"/></linearGradient>'
      f'<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{t["CYAN"]}" stop-opacity="0"/>'
      f'<stop offset="0.85" stop-color="{t["CYAN"]}" stop-opacity="0.16"/><stop offset="1" stop-color="{t["CYAN"]}" stop-opacity="0.55"/></linearGradient>'
      '<filter id="glow8" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="8"/></filter>'
      '<filter id="glow3" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="3"/></filter>'
      '<filter id="txtGlow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="0.9" result="b"/>'
      '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
      f'<clipPath id="winClip"><rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="18"/></clipPath>'
      f'<clipPath id="panelClip"><rect x="{PX}" y="{PY}" width="{PW}" height="{PH}" rx="10"/></clipPath>'
      '</defs>')
    a(f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="18" fill="{t["FRAME"]}"/>')
    a('<g clip-path="url(#winClip)">')
    a(f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" fill="url(#panelGrad)"/>')
    a(f'<rect x="2" y="2" width="{W - 4}" height="46" fill="{t["BAR"]}"/>')
    a(f'<line x1="2" y1="48" x2="{W - 2}" y2="48" stroke="{t["BARLINE"]}"/>')
    for i, col in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        a(f'<circle cx="{30 + i * 20}" cy="25" r="5.5" fill="{col}"/>')
    a(f'<text x="{W / 2}" y="29" text-anchor="middle" font-size="12" fill="{t["MUTED"]}">{esc(TITLE)}</text>')

    # portrait panel
    a(f'<text x="{PX + 2}" y="74" font-size="10" letter-spacing="3" fill="{t["DIM"]}">TARGET.SCAN</text>')
    a(f'<rect x="{PX}" y="{PY}" width="{PW}" height="{PH}" rx="10" fill="none" stroke="{t["CYAN"]}" stroke-width="2" opacity="0.45" filter="url(#glow3)"/>')
    a(f'<rect x="{PX}" y="{PY}" width="{PW}" height="{PH}" rx="10" fill="{t["PANEL"]}" stroke="{t["PANEL_STROKE"]}"/>')
    a(portrait_layer(theme, t))
    a(f'<g clip-path="url(#panelClip)"><rect x="{PX}" y="{PY - 70}" width="{PW}" height="70" fill="url(#scan)">'
      f'<animateTransform attributeName="transform" type="translate" values="0 0;0 {PH + 70}" dur="4.2s" repeatCount="indefinite"/></rect></g>')
    a(f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" dur="0.4s" begin="{REVEAL_END}s" fill="freeze"/>'
      f'<rect x="{PX + 12}" y="{PY + PH - 30}" width="168" height="18" rx="4" fill="{t["PANEL"]}" opacity="0.85"/>'
      f'<text x="{PX + 20}" y="{PY + PH - 17}" font-size="10" letter-spacing="1.5" fill="{t["EMERALD"]}">'
      f'<tspan>&#9679;<animate attributeName="opacity" values="1;0.25;1" dur="1.8s" repeatCount="indefinite"/></tspan> IDENTITY VERIFIED</text></g>')
    for x0, y0, dx, dy in ((PX, PY, 1, 1), (PX + PW, PY, -1, 1), (PX, PY + PH, 1, -1), (PX + PW, PY + PH, -1, -1)):
        a(f'<path d="M {x0 + 14 * dx} {y0} L {x0} {y0} L {x0} {y0 + 14 * dy}" fill="none" stroke="{t["CYAN"]}" stroke-width="2" opacity="0.8"/>')

    a(info_panel(t))
    a('</g>')
    a(f'<rect x="3" y="3" width="{W - 6}" height="{H - 6}" rx="17" fill="none" stroke="url(#accent)" stroke-width="3" opacity="0.55" filter="url(#glow8)"/>')
    a(f'<rect x="3" y="3" width="{W - 6}" height="{H - 6}" rx="17" fill="none" stroke="url(#accent)" stroke-width="1.6"/>')
    a('</svg>')
    return "".join(s)


if __name__ == "__main__":
    for theme in ("dark", "light"):
        svg = build(theme)
        path = os.path.join(ROOT, f"{theme}.svg")
        with open(path, "w") as f:
            f.write(svg)
        print(f"wrote {path}: {len(svg) // 1024}KB")
