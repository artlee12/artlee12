"""Render the @artlee12 dashboard from public GitHub data."""

import argparse
from collections import Counter
from datetime import date, timedelta
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen


USER = "artlee12"
PROJECTS = ("biodata_project", "curs")
INK, MUTED, LINE = "#1f2328", "#495660", "#d1d9e0"
GREEN, PURPLE, BLUE, PINK = "#45e36a", "#6434ef", "#258cf4", "#f52780"
LANGUAGE_COLORS = (PURPLE, BLUE, "#28a957", "#d72a75")
STACK = (
    ("Python", BLUE, ("01110", "01000", "11111", "00010", "01110")),
    ("SQL", PURPLE, ("01110", "10001", "11111", "10001", "01110")),
    ("Jupyter", "#bd5221", ("01110", "10001", "00100", "10001", "01110")),
    ("PyTorch", "#c34432", ("00100", "01110", "11011", "10001", "01110")),
    ("Dask", "#cf3866", ("10010", "11011", "01100", "00110", "10010")),
    ("Prefect", "#3967d5", ("11110", "10001", "11110", "10000", "10000")),
    ("PostgreSQL", "#315c94", ("01110", "10101", "11111", "00110", "01100")),
    ("Streamlit", "#cf3866", ("00001", "00011", "11111", "01110", "00100")),
)
PIXELS = {
    "@": ("01110", "10001", "10111", "10101", "10111", "10000", "01111"),
    "a": ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    "r": ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    "t": ("01000", "01000", "11110", "01000", "01000", "01001", "00110"),
    "l": ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    "e": ("00000", "00000", "01110", "10001", "11111", "10000", "01111"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
}
MOSAIC = (
    "..........g.vpl",
    ".........g.pbg.",
    ".......w.gl..vg",
    "......g..l.vgl.",
    "....l..g..p...b",
    "..g..w..lv.gbvl",
    ".l....g..g.p..g",
)
TILES = {"g": GREEN, "v": PURPLE, "p": PINK, "b": BLUE, "l": "#b590fa", "w": "#fff"}


def request(url, accept):
    req = Request(url, headers={
        "Accept": accept,
        "Accept-Language": "en-US,en;q=0.9",
        "User-Agent": "artlee12-public-profile-dashboard",
    })
    with urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8")


class ContributionCalendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}
        self.tooltips = {}
        self.tooltip_id = None
        self.tooltip_text = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and attrs.get("data-date") and "ContributionCalendar-day" in attrs.get("class", "").split():
            self.days[attrs["id"]] = date.fromisoformat(attrs["data-date"])
        if tag == "tool-tip" and attrs.get("for", "").startswith("contribution-day-component-"):
            self.tooltip_id = attrs["for"]
            self.tooltip_text = ""

    def handle_data(self, text):
        if self.tooltip_id:
            self.tooltip_text += text

    def handle_endtag(self, tag):
        if tag != "tool-tip" or not self.tooltip_id:
            return
        match = re.match(r"\s*(No|[\d,]+) contributions? on ", self.tooltip_text)
        if match:
            amount = match.group(1)
            self.tooltips[self.tooltip_id] = 0 if amount == "No" else int(amount.replace(",", ""))
        self.tooltip_id = None

    def series(self):
        if len(self.days) < 365 or self.days.keys() - self.tooltips.keys():
            raise ValueError("The public contribution calendar did not contain a full set of days.")
        counts = {day: self.tooltips[key] for key, day in self.days.items()}
        last = max(counts)
        return [(day, counts[day]) for day in (last - timedelta(days=i) for i in range(364, -1, -1))]


def data():
    parser = ContributionCalendar()
    parser.feed(request(f"https://github.com/users/{USER}/contributions", "text/html"))
    series = parser.series()
    languages = Counter()
    for repo in PROJECTS:
        payload = request(f"https://api.github.com/repos/{USER}/{repo}/languages", "application/vnd.github+json")
        languages.update(json.loads(payload))
    return series, languages


def streaks(counts):
    run = longest = 0
    for amount in counts:
        run = run + 1 if amount else 0
        longest = max(longest, run)
    if not counts[-1]:
        for amount in reversed(counts[:-1]):
            if not amount:
                break
            run += 1
    return run, longest


def text(x, y, value, size=15, *, fill=INK, mono=False, weight=400, anchor="start"):
    style = "mono" if mono else "sans"
    return (
        f'<text x="{x}" y="{y}" class="{style}" font-size="{size}" fill="{fill}" '
        f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(value))}</text>'
    )


def rect(x, y, w, h, fill, extra=""):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" {extra}/>'


def label(x, y, value):
    return text(x, y, value, 13, fill=MUTED, mono=True, weight=600)


def glyph(pattern, x, y, unit, fill):
    commands = [
        f"M{x + col * unit} {y + row * unit}h{unit}v{unit}h-{unit}z"
        for row, line in enumerate(pattern)
        for col, pixel in enumerate(line) if pixel == "1"
    ]
    return f'<path fill="{fill}" shape-rendering="crispEdges" d="{"".join(commands)}"/>'


def divider(x1, y1, x2, y2):
    return f'<path d="M{x1} {y1}L{x2} {y2}" stroke="{LINE}"/>'


def hero(w, compact):
    margin = 24 if compact else 30
    bottom = 194
    split = 308 if compact else 551
    step = 19 if compact else 23
    unit = 5 if compact else 7
    children = [
        rect(0, 0, w, bottom, "#f7f9f8"),
        rect(0, 0, split, bottom, "url(#paper)"),
        rect(0, 0, split, bottom, "url(#grid)"),
        divider(split + 0.5, 0, split + 0.5, bottom),
        divider(0, 43.5, w, 43.5),
        rect(margin, 17, 9, 9, GREEN),
        label(margin + 17, 25, "github.profile"),
        text(w - margin, 25, "~/readme", 13, fill=MUTED, mono=True, anchor="end"),
    ]
    if compact:
        children.extend((
            text(margin, 151, "Аналитика данных", 19, fill=MUTED),
            text(margin, 174, "и машинное обучение", 19, fill=MUTED),
        ))
    else:
        children.extend((
            text(margin, 157, "Аналитика данных и машинное обучение", 22, fill=MUTED),
            text(margin, 177, "PYTHON / SQL", 11, mono=True, fill=MUTED),
        ))
    origin = w - step * len(MOSAIC[0])
    for row, line in enumerate(MOSAIC):
        for col, tile in enumerate(line):
            x = origin + col * step
            if tile in TILES and x >= split + 1:
                y = bottom - (len(MOSAIC) - row) * step
                if y >= 44:
                    delay = 0.045 * (col + row)
                    children.append(rect(x, y, step, step, TILES[tile], f'class="tile" style="--delay:{delay:.2f}s"'))
    for i, char in enumerate("@" + USER):
        children.append(glyph(PIXELS[char], margin + i * unit * 6, 74, unit, INK))
    return children


def stack(w, compact, top, height):
    margin = 24 if compact else 30
    columns = 4 if compact else 8
    gap = 7
    chip_width = (w - margin * 2 - gap * (columns - 1)) // columns
    children = [label(margin, top + 28, "01 / СТЕК")]
    for i, (name, color, icon) in enumerate(STACK):
        x = margin + (i % columns) * (chip_width + gap)
        y = top + 43 + (i // columns) * 36
        children.extend((
            rect(x, y, chip_width, 30, "#fff", f'rx="4" stroke="{LINE}"'),
            glyph(icon, x + 8, y + 10, 2, color),
            text(x + 24, y + 20, name, 11 if compact else 12, weight=550),
        ))
    children.append(divider(0, top + height + 0.5, w, top + height + 0.5))
    return children


def activity(w, compact, top, height, series):
    margin = 24 if compact else 30
    chart_width = w - margin * 2 if compact else 542
    chart_bottom = top + (155 if compact else 177)
    chart_height = 89 if compact else 100
    recent = series[-31:]
    counts = [count for _, count in series]
    maximum = max(1, max(count for _, count in recent))
    gap = 3 if compact else 4
    step = chart_width / len(recent)
    children = [
        label(margin, top + 28, "02 / АКТИВНОСТЬ"),
        text(margin, top + 51, f"Вклады за 31 день · {sum(count for _, count in recent)}", 17, weight=600),
    ]
    for level in (0, 0.5, 1):
        y = chart_bottom - chart_height * level
        children.append(divider(margin, y + .5, margin + chart_width, y + .5))
    for i, (day, count) in enumerate(recent):
        x = round(margin + i * step)
        bar_width = max(2, round(margin + (i + 1) * step) - x - gap)
        if not count:
            children.append(rect(x, chart_bottom - 2, bar_width, 2, "#dce4dd"))
            continue
        bar_height = max(4, round(chart_height * count / maximum))
        fill = PURPLE if count == maximum else "#38b96a"
        children.append(
            f'<g class="bar" style="--delay:{0.17 + i * .037:.2f}s"><title>{day:%d.%m}: {count}</title>'
            + rect(x, chart_bottom - bar_height, bar_width, bar_height, fill)
            + rect(x + 1, chart_bottom - bar_height, max(1, bar_width - 2), 2, "#b5f1c5" if fill != PURPLE else "#c8b7fc")
            + "</g>"
        )
    children.extend((
        text(margin, chart_bottom + 22, f"{recent[0][0]:%d.%m}", 12, fill=MUTED, mono=True),
        text(margin + chart_width, chart_bottom + 22, f"{recent[-1][0]:%d.%m}", 12, fill=MUTED, mono=True, anchor="end"),
    ))
    current, best = streaks(counts)
    stats = (
        (sum(counts), "вкладов за 365 дней"),
        (current, "текущая серия, дн."),
        (best, "лучшая серия, дн."),
    )
    if compact:
        stat_y = top + 188
        children.append(divider(0, stat_y + .5, w, stat_y + .5))
        for i, (number, title) in enumerate(stats):
            x = margin + i * 141
            children.extend((text(x, stat_y + 34, number, 24, mono=True, weight=700), text(x, stat_y + 52, title, 11, fill=MUTED)))
    else:
        boundary = 601
        children.append(divider(boundary + .5, top, boundary + .5, top + height))
        for i, (number, title) in enumerate(stats):
            y = top + 58 + i * 55
            children.extend((text(630, y, number, 29, mono=True, weight=700), text(703, y - 1, title, 14, fill=MUTED)))
    children.append(divider(0, top + height + .5, w, top + height + .5))
    return children


def language_panel(w, compact, top, counts):
    margin = 24 if compact else 30
    children = [label(margin, top + 28, "03 / ЯЗЫКИ")]
    children.append(text(margin, top + 50, "По объёму файлов в двух проектах", 14, fill=MUTED))
    total = sum(counts.values())
    entries = counts.most_common()
    if len(entries) > 4:
        entries = [*entries[:3], ("Другие", sum(count for _, count in entries[3:]))]
    track_x = margin + 150
    track_width = w - track_x - margin - 68
    for i, (language, count) in enumerate(entries):
        y = top + 73 + i * 24
        ratio = count / total
        children.extend((
            text(margin, y + 10, language, 13, mono=True),
            rect(track_x, y, track_width, 10, "#eef1f3"),
            rect(track_x, y, max(2, round(track_width * ratio)), 10, LANGUAGE_COLORS[i],
                 f'class="meter" style="--delay:{0.6 + 0.13 * i:.2f}s"'),
            text(w - margin, y + 10, f"{ratio:.1%}".replace(".", ","), 13, mono=True, anchor="end"),
        ))
    return children, top + 80 + len(entries) * 24


MOTION = """
    @media (prefers-reduced-motion: no-preference) {
      .tile { animation: assemble .76s steps(5, end) var(--delay) both }
      .bar { transform-box: fill-box; transform-origin: center bottom;
             animation: rise .72s steps(7, end) var(--delay) both }
      .meter { transform-box: fill-box; transform-origin: left center;
               animation: fill-meter .85s steps(10, end) var(--delay) both }
      @keyframes assemble { from { opacity: .33 } to { opacity: 1 } }
      @keyframes rise { from { transform: scaleY(.07) } to { transform: scaleY(1) } }
      @keyframes fill-meter { from { transform: scaleX(.06) } to { transform: scaleX(1) } }
    }
"""


def render(series, languages, compact, animated):
    w = 456 if compact else 928
    stack_height = 121 if compact else 91
    activity_height = 256 if compact else 218
    sections, footer = language_panel(w, compact, 194 + stack_height + activity_height, languages)
    height = footer + 39
    margin = 24 if compact else 30
    children = [
        rect(0, 0, w, height, "#fff"),
        *hero(w, compact),
        divider(0, 194.5, w, 194.5),
        *stack(w, compact, 194, stack_height),
        *activity(w, compact, 194 + stack_height, activity_height, series),
        *sections,
        divider(0, footer + .5, w, footer + .5),
        text(margin, footer + 24, "Источник · публичные данные GitHub", 11, fill=MUTED, mono=True),
        text(w - margin, footer + 24, f"{series[-1][0]:%d.%m.%Y}", 11, fill=MUTED, mono=True, anchor="end"),
    ]
    art = "\n".join("    " + item for item in children)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{height}" viewBox="0 0 {w} {height}">
  <title>@{USER} · GitHub dashboard</title>
  <desc>Стек, ежедневные вклады за 31 день, серии активности и языки двух проектов.</desc>
  <style>
    .sans {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif }}
    .mono {{ font-family: ui-monospace, Consolas, 'Liberation Mono', monospace }}
{MOTION if animated else ""}  </style>
  <defs>
    <linearGradient id="paper" x2="1" y2=".28">
      <stop stop-color="#f7effa"/><stop offset=".47" stop-color="#edf8f1"/><stop offset="1" stop-color="#f6f2fd"/>
    </linearGradient>
    <pattern id="grid" width="18" height="18" patternUnits="userSpaceOnUse">
      <path d="M18 0H0V18" stroke="#fff" stroke-width="1.7" fill="none"/>
    </pattern>
    <clipPath id="frame"><rect width="{w}" height="{height}" rx="7"/></clipPath>
  </defs>
  <g clip-path="url(#frame)">
{art}
  </g>
  <rect x=".5" y=".5" width="{w - 1}" height="{height - 1}" rx="6.5" fill="none" stroke="{LINE}"/>
</svg>
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("assets"))
    args = parser.parse_args()
    series, languages = data()
    if not languages:
        raise ValueError("GitHub returned no language data for the selected projects.")
    args.output.mkdir(parents=True, exist_ok=True)
    for compact, size in ((False, ""), (True, "-mobile")):
        for animated, motion in ((True, ""), (False, "-still")):
            target = args.output / f"dashboard{size}{motion}.svg"
            target.write_text(render(series, languages, compact, animated), encoding="utf-8")
    counts = [count for _, count in series]
    print(f"Through {series[-1][0]}: {sum(counts[-31:])} in 31 days, {sum(counts)} in 365 days, streaks {streaks(counts)}.")
    print(f"Language bytes: {dict(languages.most_common())}")


if __name__ == "__main__":
    main()
