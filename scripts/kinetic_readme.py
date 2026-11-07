from __future__ import annotations

import html
import math
from collections import Counter
from datetime import date
from pathlib import Path

FG = "#E8FAF7"
MUTED = "#9DBECA"
MINT = "#6FF4CD"
TEAL = "#46BFBE"
AMBER = "#FEC58B"
RED = "#FF8CAB"
BLUE = "#8EAAFF"
BG = "#050E1D"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def text(x: float, y: float, value: object, size: int, color: str=FG, weight: int=400, letter_spacing: float=0) -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{color}" font-family="Inter,Arial,sans-serif" '
            f'font-size="{size}" font-weight="{weight}" letter-spacing="{letter_spacing}">{esc(value)}</text>')


def shell(title: str, content: list[str], *, height: int=700) -> str:
    styles = """
    @keyframes tracer{to{stroke-dashoffset:-200}}
    @keyframes rotate{to{transform:rotate(360deg)}}
    @keyframes breathe{0%,100%{opacity:.36}50%{opacity:.83}}
    @keyframes rise{0%{opacity:0;transform:translateY(8px)}50%,100%{opacity:1;transform:translateY(0)}}
    @keyframes march{to{transform:translateX(42px)}}
    @keyframes orbit{to{transform:rotate(-360deg)}}
    .dash{stroke-dasharray:7 14;animation:tracer 10s linear infinite}
    .ring{animation:rotate 45s linear infinite;transform-origin:1232px 328px}
    .counterring{animation:orbit 65s linear infinite;transform-origin:1232px 328px}
    .glow{animation:breathe 3s ease-in-out infinite}
    .enter{animation:rise 1s ease-out both}
    .march{animation:march 5s linear infinite}
    @media(prefers-reduced-motion:reduce){.dash,.ring,.counterring,.glow,.enter,.march{animation:none!important}}
    """
    defs = (f'<defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#061727"/>'
            f'<stop offset=".48" stop-color="#070E21"/><stop offset="1" stop-color="#0D1B2B"/></linearGradient>'
            f'<linearGradient id="beam"><stop stop-color="{MINT}" stop-opacity=".1"/>'
            f'<stop offset=".5" stop-color="{MINT}" stop-opacity=".8"/>'
            f'<stop offset="1" stop-color="{BLUE}" stop-opacity=".14"/></linearGradient>'
            '<radialGradient id="orb"><stop stop-color="#1F7478" stop-opacity=".52"/>'
            '<stop offset=".55" stop-color="#10444D" stop-opacity=".18"/>'
            '<stop offset="1" stop-color="#08152A" stop-opacity="0"/></radialGradient>'
            '<filter id="bloom" x="-70%" y="-70%" width="240%" height="240%">'
            '<feGaussianBlur stdDeviation="5"/></filter></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="{height}" '
            f'viewBox="0 0 1600 {height}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title><style>{styles}</style>{defs}'
            f'<rect width="1600" height="{height}" fill="url(#bg)"/>'
            + "".join(content) + "</svg>\n")


def kinetic_cover(view: dict) -> str:
    metrics = view["metrics"]
    as_of = date.fromisoformat(view["as_of"])
    apps = [a for a in view["applications"] if a["days"] >= 0]
    apps.sort(key=lambda a:(a["days"],a["id"]))
    bins = [
        sum(0<=a["days"]<=3 for a in apps),
        sum(4<=a["days"]<=7 for a in apps),
        sum(8<=a["days"]<=14 for a in apps),
        sum(15<=a["days"]<=30 for a in apps),
        sum(31<=a["days"]<=60 for a in apps),
    ]
    future = len(apps)
    parts = [
        '<rect x="0" y="0" width="1600" height="700" fill="none" stroke="#19384F" stroke-width="2"/>',
        '<path d="M0 638 H1600" stroke="#294559"/>',
        '<path d="M64 110 H893" stroke="#2F596C" stroke-width="1"/>',
        '<path d="M64 526 H835" stroke="#204353" stroke-dasharray="3 12"/>',
        '<circle cx="1232" cy="328" r="375" fill="url(#orb)"/>',
        text(64,75,"/ /  EVIDENCEGRAPH  ·  INTELLIGENCE ENGINE",20,MINT,700,3),
        text(64,160,"RESEARCH.",88,FG,800,-3),
        text(64,252,"VERIFY.",88,FG,800,-3),
        text(64,344,"DECIDE.",88,MINT,800,-3),
        text(68,392,"APPLICATION RESEARCH AS AN EXPLORABLE EVIDENCE SYSTEM",20,MUTED,500,1),
        text(69,432,"Live workflows  /  Counterfactual scenarios  /  Temporal evidence",18,FG,400),
        text(69,462,"No fabricated acceptance predictions or submission states",16,MUTED,400),
        text(69,573,"OBSERVED SNAPSHOT   "+as_of.isoformat(),16,MUTED,700,2),
        text(69,609,"EXPLORE THE SYSTEM",17,MINT,700,3),
        '<path class="dash" d="M 307 603 L 590 603" stroke="url(#beam)" stroke-width="3" fill="none"/>',
        '<path d="M575 593 l17 10 -17 10" stroke="#6FF4CD" stroke-width="3" fill="none"/>',
        text(64,676,"DATA-DRIVEN VISUAL SIGNALS  /  INTERACT THROUGH THE NATIVE GITHUB CONTROLS BELOW",14,MUTED,600,1.5),
        text(1260,672,f'{metrics["research_papers"]} RESEARCH SIGNALS',13,MUTED,700,1.2),
    ]
    for i in range(32):
        y = 25+i*22
        x= 850+(i*31)%150
        op=.13+(i%6)*.035
        parts.append(f'<path d="M{x} {y} l31 -8" stroke="{BLUE}" stroke-opacity="{op:.2f}" stroke-width="1.2"/>')
    radii=[96,171,250,325]
    ring_labels=["0–3d","4–7d","8–14d","15–60d"]
    for i,(radius,caption) in enumerate(zip(radii,ring_labels)):
        parts.append(f'<circle cx="1232" cy="328" r="{radius}" fill="none" stroke="#2C5261" '
                     f'stroke-opacity="{.8-i*.13:.2f}" stroke-width="1.5" stroke-dasharray="4 9"/>')
        parts.append(text(1232+radius*.76,328-radius*.72-10,caption,12,MUTED,600))
    parts.append('<g class="ring"><path d="M1232 3 A325 325 0 0 1 1557 328" stroke="#6FF4CD" stroke-width="4" stroke-linecap="round" fill="none" opacity=".62"/>'
                 '<path d="M907 328 A325 325 0 0 1 1232 3" stroke="#8EAAFF" stroke-width="1.5" fill="none" opacity=".37"/></g>')
    parts.append('<g class="counterring"><path d="M1232 78 A250 250 0 0 0 982 328" stroke="#FFCB8B" stroke-width="3" stroke-linecap="round" fill="none" opacity=".72"/></g>')
    for i,a in enumerate(apps[:75]):
        days=a["days"]
        radius=96 if days<=3 else 171 if days<=7 else 250 if days<=14 else 325
        theta=((i*.61803398875)%1)*2*math.pi
        x=1232+radius*math.cos(theta)
        y=328+radius*math.sin(theta)
        color=RED if days<=3 else AMBER if days<=7 else MINT if days<=14 else BLUE
        size=5.5 if days<=7 else 4
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size+5:.1f}" fill="{color}" opacity=".1" filter="url(#bloom)"/>')
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}" fill="{color}" class="glow">'
                     f'<title>{esc(a["id"])} / {esc(a["deadline"])} / {esc(a["name"])}</title></circle>')
        if i%5==0 and i<45:
            parts.append(f'<path d="M 1232 328 L {x:.1f} {y:.1f}" stroke="{color}" stroke-opacity=".13" stroke-width="1"/>')
    parts.extend([
        '<circle cx="1232" cy="328" r="73" fill="#0A2B37" stroke="#58DCC2" stroke-width="1.5"/>',
        '<circle cx="1232" cy="328" r="62" fill="none" stroke="#5D9EAC" stroke-dasharray="2 8"/>',
        text(1198,331,"FUTURE",16,FG,700,2),
        text(1207,360,f'{future}',29,MINT,800),
        text(1093,95,"DEADLINE SPACE",15,MUTED,700,3),
        text(994,580,f'{metrics["next_seven_days"]} WITHIN 7 DAYS    /    {metrics["source_conflicts"]} SOURCE CONFLICTS',16,AMBER,700,1),
    ])
    bar_x=1025
    maximum=max(1,*bins)
    labels=["0–3","4–7","8–14","15–30","31–60"]
    for i,(n,label_) in enumerate(zip(bins,labels)):
        x=bar_x+i*102
        h=14+int(n*56/maximum)
        parts.append(f'<rect x="{x}" y="{617-h}" width="58" height="{h}" rx="5" fill="{RED if i==0 else AMBER if i==1 else MINT}" opacity=".8"/>')
        parts.append(text(x,630,label_,13,MUTED,600))
    return shell("Animated data-backed PhD intelligence hero with actual application deadline orbits",parts)


def kinetic_lane(view: dict) -> str:
    metrics=view["metrics"]
    providers=view["providers"]
    good=sum(p["health"]=="ok" for p in providers)
    total=len(providers)
    statements=[
        ("SOURCE DISCOVERY",f"{good}/{total} healthy",MINT),
        ("VERIFY ASSERTIONS",f'{metrics["source_conflicts"]} conflicting',AMBER),
        ("RECONCILE IDENTITIES",f'{metrics["tracked"]} tracked',BLUE),
        ("EXECUTE DECISIONS",f'{metrics["next_seven_days"]} ≤7d',MINT)
    ]
    parts=[
        '<path d="M 60 158 L 1540 158" stroke="#2B5266" stroke-width="1.8"/>',
        text(63,66,"RESEARCH SIGNAL PIPELINE",24,FG,750,2),
        text(63,102,"The motion follows a real source-to-decision pipeline, not a simulated application success rate",16,MUTED),
    ]
    for i,(name,value,color) in enumerate(statements):
        x=63+i*377
        parts.append(f'<circle cx="{x+27}" cy="158" r="18" fill="#081A2C" stroke="{color}" stroke-width="2"/>')
        parts.append(f'<circle cx="{x+27}" cy="158" r="4" fill="{color}" class="glow"/>')
        parts.append(text(x+7,208,name,15,color,700,1))
        parts.append(text(x+7,246,value,30,FG,800))
    parts.append('<circle r="5" fill="#6FF4CD"><animateMotion dur="7s" repeatCount="indefinite" path="M 90 158 L 1221 158 L 1500 158"/></circle>')
    parts.append('<circle r="3.5" fill="#FFD3A3"><animateMotion dur="7s" begin="-3.5s" repeatCount="indefinite" path="M 90 158 L 1500 158"/></circle>')
    return shell("Animated verified research to decision signal pipeline",parts,height=293)


def write_assets(view: dict, directory: Path) -> tuple[str,str]:
    directory.mkdir(parents=True,exist_ok=True)
    a,b="kinetic_cover.svg","kinetic_lane.svg"
    (directory/a).write_text(kinetic_cover(view),encoding="utf-8")
    (directory/b).write_text(kinetic_lane(view),encoding="utf-8")
    return a,b
