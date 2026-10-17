import re

PRESETS = {
    "karaoke": {
        "accent": "#B4F16F",
        "size": 76,
        "y": 0.73,
        "box": False,
        "upper": False,
    },
    "bold": {"accent": "#FFE45E", "size": 90, "y": 0.72, "box": False, "upper": True},
    "minimal": {
        "accent": "#FFFFFF",
        "size": 58,
        "y": 0.82,
        "box": False,
        "upper": False,
    },
    "neon": {"accent": "#B999FF", "size": 80, "y": 0.7, "box": False, "upper": True},
    "boxed": {"accent": "#FFFFFF", "size": 72, "y": 0.74, "box": True, "upper": False},
}


def ass_time(t):
    cs = max(0, round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def srt_time(t):
    ms = max(0, round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def escape(text):
    return re.sub(r"[{}\\\r\n]", "", text)


def color(hex):
    return "&H00" + hex[5:7] + hex[3:5] + hex[1:3]


def build_ass(words, width=1080, height=1920, style="karaoke", brand=None):
    p = PRESETS[style]
    brand = brand or {}
    accent = color(brand.get("color") or p["accent"])
    base = color(brand.get("text_color", "#FFFFFF"))
    size = round(p["size"] * height / 1920)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,{brand.get("font", "DejaVu Sans")},{size},{base},{accent},&H00202020,&H80000000,-1,0,0,0,100,100,0,0,{3 if p["box"] else 1},4,1,5,50,50,80,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events = []
    # Small groups prevent wrapping outside vertical safe zones; long words stand alone.
    groups = []
    group = []
    length = 0
    for w in words:
        if group and (
            len(group) >= 4
            or length + len(w["text"]) > 24
            or w["start"] - group[-1]["end"] > 0.5
        ):
            groups.append(group)
            group = []
            length = 0
        group.append(w)
        length += len(w["text"]) + 1
    if group:
        groups.append(group)
    for group in groups:
        for i, w in enumerate(group):
            a = w["start"]
            b = min(w["end"], group[i + 1]["start"]) if i + 1 < len(group) else w["end"]
            if round(b * 100) <= round(a * 100):
                continue
            chunks = []
            for j, other in enumerate(group):
                text = escape(other["text"])
                text = text.upper() if p["upper"] else text
                chunks.append(
                    (
                        f"{{\\c{accent}\\t(0,75,\\fscx108\\fscy108)}}"
                        if i == j
                        else f"{{\\c{base}}}"
                    )
                    + text
                    + "{\\r}"
                )
            text = (
                f"{{\\an5\\pos({width // 2},{round(height * p['y'])})}}"
                + " ".join(chunks)
                + ((" " + escape(brand["emoji"])) if brand.get("emoji") else "")
            )
            events.append(
                f"Dialogue: 0,{ass_time(a)},{ass_time(b)},Default,,0,0,0,,{text}"
            )
    return header + "\n".join(events) + "\n"


def build_srt(words, offset=0):
    out = []
    for i in range(0, len(words), 8):
        g = words[i : i + 8]
        out.append(
            f"{len(out) + 1}\n{srt_time(g[0]['start'] + offset)} --> {srt_time(g[-1]['end'] + offset)}\n"
            + " ".join(w["text"] for w in g)
        )
    return "\n\n".join(out) + "\n"
