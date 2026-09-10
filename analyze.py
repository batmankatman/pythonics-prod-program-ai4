#!/usr/bin/env python3
"""Audit the waking-day activity log and generate a small SVG portfolio."""

import csv
import html
import math
import re
from statistics import NormalDist
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parent
INPUT = ROOT / "dataset.txt"
OUT = ROOT / "analysis_output"
CATEGORIES = ("P", "R", "E", "S", "W", "F", "GOD")
COLORS = {"P": "#1b6ca8", "R": "#4b0082", "E": "#e07a2d", "S": "#8e5aa7", "W": "#2a9d8f", "F": "#e9c46a", "GOD": "#d1495b"}
HEADER_RE = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2})\s+(M|T|W|Th|F|Sa|Su)\s+(\d{4})-(\d{4})\s*$")
ROW_RE = re.compile(r"^(\d{4})\s+(\S+)(?:\s+(.*?))?\s*$")


def minutes(value):
    return int(value[:2]) * 60 + int(value[2:])


def clean_category(raw):
    if raw.lower() == "eat":
        return "E", "normalized category Eat to E"
    return raw, ""


def clock_gap(older_clock, newer_clock):
    """Minutes from the older row's clock to the newer row above it."""
    gap = minutes(newer_clock) - minutes(older_clock)
    # Duplicate timestamps are simultaneous entries, not a full-day rollover.
    return 0 if gap == 0 else (gap if gap > 0 else gap + 1440)


def parse_file():
    blocks = []
    malformed = []
    current = None
    for line_number, raw in enumerate(INPUT.read_text(encoding="utf-8").splitlines(), 1):
        text = raw.strip()
        if not text:
            continue
        header = HEADER_RE.match(text)
        if header:
            month, day, year, weekday, wake, _ = header.groups()
            current = {
                "date": date(2000 + int(year), int(month), int(day)),
                "weekday": weekday,
                "wake": wake,
                "rows": [],
                "line": line_number,
            }
            blocks.append(current)
            continue
        if current is None:
            malformed.append({"line": line_number, "raw": text, "reason": "before first header"})
            continue
        row = ROW_RE.match(text)
        if not row:
            malformed.append({"line": line_number, "raw": text, "reason": "unparseable activity row"})
            continue
        clock, raw_category, description = row.groups()
        category, note = clean_category(raw_category)
        current["rows"].append({
            "line": line_number,
            "clock": clock,
            "category": category,
            "raw_category": raw_category,
            "description": (description or "").strip(),
            "normalization": note,
        })
    return blocks, malformed


def recording_id(blocks, index):
    if index == 0 or (blocks[index - 1]["date"] - blocks[index]["date"]).days != 1:
        return f"trial-pair{sum(1 for i in range(index + 1) if i == 0 or (blocks[i - 1]['date'] - blocks[i]['date']).days != 1):02d}"
    return recording_id(blocks, index - 1)


def analyze(blocks, malformed):
    activities, daily, sleeps, anomalies = [], [], [], []
    for index, block in enumerate(blocks):
        rid = recording_id(blocks, index)
        rows = block["rows"]
        lo_rows = [row for row in rows if row["category"] == "LO"]
        if len(lo_rows) != 1:
            anomalies.append({"kind": "missing_or_multiple_lo", "date": block["date"].isoformat(), "line": block["line"], "detail": len(lo_rows)})
        totals = defaultdict(int)
        for row_index, row in enumerate(rows):
            if row["category"] == "LO":
                continue
            if row_index == 0:
                anomalies.append({"kind": "activity_before_lo", "date": block["date"].isoformat(), "line": row["line"], "detail": row["description"]})
                continue
            newer = rows[row_index - 1]
            duration = clock_gap(row["clock"], newer["clock"])
            if row["category"] not in CATEGORIES:
                anomalies.append({"kind": "invalid_category", "date": block["date"].isoformat(), "line": row["line"], "detail": row["raw_category"]})
            if duration > 300:
                anomalies.append({"kind": "activity_over_5_hours", "date": block["date"].isoformat(), "line": row["line"], "detail": f"{duration} minutes: {row['category']} {row['description']}"})
            if duration < 0:
                anomalies.append({"kind": "negative_duration", "date": block["date"].isoformat(), "line": row["line"], "detail": duration})
            totals[row["category"]] += duration
            activities.append({
                "date": block["date"].isoformat(), "recording": rid, "line": row["line"],
                "start": row["clock"], "end": newer["clock"], "duration_minutes": duration,
                "category": row["category"], "description": row["description"],
                "normalization": row["normalization"],
            })
        daily.append({"date": block["date"].isoformat(), "recording": rid, "weekday": block["weekday"], "wake": block["wake"], **{category: totals[category] for category in CATEGORIES}})

    for index in range(len(blocks) - 1):
        next_day, sleep_day = blocks[index], blocks[index + 1]
        if (next_day["date"] - sleep_day["date"]).days != 1:
            continue
        lo = next((row for row in sleep_day["rows"] if row["category"] == "LO"), None)
        if not lo:
            continue
        lo_date = sleep_day["date"] + (timedelta(days=1) if minutes(lo["clock"]) < minutes(sleep_day["wake"]) else timedelta())
        wake_dt = datetime.combine(next_day["date"], datetime.min.time()) + timedelta(minutes=minutes(next_day["wake"]))
        lo_dt = datetime.combine(lo_date, datetime.min.time()) + timedelta(minutes=minutes(lo["clock"]))
        sleep_minutes = int((wake_dt - lo_dt).total_seconds() / 60)
        sleeps.append({"date": sleep_day["date"].isoformat(), "next_wake": next_day["date"].isoformat(), "recording": recording_id(blocks, index + 1), "sleep_minutes": sleep_minutes})
    for item in malformed:
        anomalies.append({"kind": item["reason"], "date": "", "line": item["line"], "detail": item["raw"]})
    return activities, daily, sleeps, anomalies


def write_csv(name, rows):
    path = OUT / name
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def svg_start(title, width, height):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<style>text{font-family:system-ui,-apple-system,sans-serif;fill:#263238} .muted{fill:#667085;font-size:12px} .grid{stroke:#dfe4ea;stroke-width:1} .axis{stroke:#334155;stroke-width:1.2}</style>', f'<rect width="100%" height="100%" fill="#fbfaf7"/><text x="48" y="36" font-size="21" font-weight="700">{html.escape(title)}</text>']


def save_svg(name, parts):
    (OUT / name).write_text("\n".join(parts + ["</svg>"]), encoding="utf-8")


def heatmap(daily):
    total_column_width = 105
    width, left, top, cell_w, cell_h = 980 + total_column_width, 105, 70, 112, 25
    height = top + len(daily) * cell_h + 95
    parts = svg_start("Waking-day composition: where time went", width, height)
    max_value = max((int(row[c]) for row in daily for c in CATEGORIES), default=1)
    for ci, category in enumerate(CATEGORIES):
        x = left + ci * cell_w + 4
        parts.append(f'<text x="{x + 45}" y="58" text-anchor="middle" font-size="12" font-weight="700">{category}</text>')
    total_x = left + len(CATEGORIES) * cell_w
    parts.append(f'<text x="{total_x + total_column_width / 2}" y="58" text-anchor="middle" font-size="12" font-weight="700">total h</text>')
    for ri, row in enumerate(daily):
        y = top + ri * cell_h
        parts.append(f'<text x="{left - 8}" y="{y + 17}" text-anchor="end" class="muted">{row["date"]}</text>')
        for ci, category in enumerate(CATEGORIES):
            value = int(row[category]); opacity = 0.12 + 0.88 * value / max_value
            x = left + ci * cell_w
            parts.append(f'<rect x="{x}" y="{y}" width="104" height="22" rx="2" fill="{COLORS[category]}" opacity="{opacity:.2f}"/>')
            if value:
                parts.append(f'<text x="{x + 52}" y="{y + 16}" text-anchor="middle" font-size="11">{value // 60}h {value % 60:02d}</text>')
        day_total = sum(int(row[category]) for category in CATEGORIES)
        parts.append(f'<text x="{total_x + total_column_width / 2}" y="{y + 16}" text-anchor="middle" font-size="11">{day_total / 60:.1f}</text>')
    category_totals = {category: sum(int(row[category]) for row in daily) for category in CATEGORIES}
    grand_total = sum(category_totals.values()) or 1
    summary_y = top + len(daily) * cell_h + 28
    parts.append(f'<text x="{left - 8}" y="{summary_y + 4}" text-anchor="end" font-size="11" font-weight="700">share</text>')
    for ci, category in enumerate(CATEGORIES):
        x = left + ci * cell_w
        parts.append(f'<text x="{x + 52}" y="{summary_y + 4}" text-anchor="middle" font-size="11" font-weight="700">{category_totals[category] / grand_total:.1%}</text>')
    parts.append(f'<text x="{total_x + total_column_width / 2}" y="{summary_y + 4}" text-anchor="middle" font-size="11" font-weight="700">100%</text>')
    parts.append(f'<text x="48" y="{height - 18}" class="muted">Darker cells indicate more minutes; each row is one waking-day recording. Values are calculated from that recording&apos;s activity sequence, not calendar midnight.</text>')
    save_svg("01_composition_heatmap.svg", parts)


def relationship(daily, sleeps):
    sleep_by_date = {row["date"]: int(row["sleep_minutes"]) for row in sleeps}
    points = [(sleep_by_date[row["date"]], int(row["P"])) for row in daily if row["date"] in sleep_by_date]
    width, height, left, top, plot_w, plot_h = 900, 560, 86, 70, 750, 400
    parts = svg_start("Sleep and productive time: a weak relationship with useful exceptions", width, height)
    max_x = max([p[0] for p in points] + [600]); max_y = max([p[1] for p in points] + [600])
    def px(x): return left + x / max_x * plot_w
    def py(y): return top + plot_h - y / max_y * plot_h
    for hour in range(0, int(max_x / 60) + 1, 2):
        x = px(hour * 60); parts.append(f'<line x1="{x}" y1="{top}" x2="{x}" y2="{top + plot_h}" class="grid"/><text x="{x}" y="{top + plot_h + 22}" text-anchor="middle" class="muted">{hour}h</text>')
    for hour in range(0, int(max_y / 60) + 1, 2):
        y = py(hour * 60); parts.append(f'<line x1="{left}" y1="{y}" x2="{left + plot_w}" y2="{y}" class="grid"/><text x="{left - 9}" y="{y + 4}" text-anchor="end" class="muted">{hour}h</text>')
    if len(points) > 1:
        mean_x = sum(x for x, _ in points) / len(points); mean_y = sum(y for _, y in points) / len(points)
        den = sum((x - mean_x) ** 2 for x, _ in points) or 1
        slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / den
        intercept = mean_y - slope * mean_x
        parts.append(f'<line x1="{px(0)}" y1="{py(intercept)}" x2="{px(max_x)}" y2="{py(intercept + slope * max_x)}" stroke="#d1495b" stroke-width="2" stroke-dasharray="6 5"/>')
    for x, y in points:
        parts.append(f'<circle cx="{px(x):.1f}" cy="{py(y):.1f}" r="5" fill="#1b6ca8" opacity=".75"/>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/><line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    parts.append(f'<text x="{left + plot_w / 2}" y="535" text-anchor="middle" class="muted">Sleep before the waking day</text><text x="20" y="280" transform="rotate(-90 20 280)" text-anchor="middle" class="muted">Productive minutes</text>')
    save_svg("02_sleep_productivity.svg", parts)


def timeline(activities, daily):
    ordered_daily = sorted(daily, key=lambda row: row["date"])
    weeks = weekly_groups(ordered_daily)
    width, height, left, top, plot_w, plot_h = 1200, 650, 105, 90, 930, 430
    parts = svg_start("Total waking activity by seven-day recording", width, height)
    parts.append('<text x="48" y="62" class="muted">Each bar is one seven-day period; its stacked segments are day 1 through day 7 total recorded hours, calculated from each day&apos;s waking-day recording.</text>')
    max_week_hours = max((sum(sum(int(day[category]) for category in CATEGORIES) for day in week) / 60 for week in weeks), default=1)
    bar_w = plot_w / len(weeks) * 0.72
    for hour in range(0, math.ceil(max_week_hours / 12) * 12 + 1, 12):
        y = top + plot_h - hour / max_week_hours * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/><text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="muted">{hour}h</text>')
    for week_index, week in enumerate(weeks):
        x = left + (week_index + 0.5) / len(weeks) * plot_w - bar_w / 2
        bottom = top + plot_h
        week_total = 0
        for day_index, day in enumerate(week):
            day_total = sum(int(day[category]) for category in CATEGORIES) / 60
            bar_h = day_total / max_week_hours * plot_h
            bottom -= bar_h
            week_total += day_total
            fill = COLORS[CATEGORIES[day_index]]
            parts.append(f'<rect x="{x:.1f}" y="{bottom:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{fill}" stroke="#ffffff"><title>W{week_index + 1:02d}, day {day_index + 1}: {day_total:.1f} hours</title></rect>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 22}" text-anchor="middle" font-size="12" font-weight="700">W{week_index + 1:02d}</text>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{bottom - 6:.1f}" text-anchor="middle" font-size="11" font-weight="700">{week_total:.1f}h</text>')
    for index, category in enumerate(CATEGORIES):
        x = 115 + index * 130
        parts.append(f'<rect x="{x}" y="38" width="10" height="10" fill="{COLORS[category]}"/><text x="{x + 16}" y="47" class="muted">day {index + 1}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/><line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    parts.append('<text x="600" y="590" text-anchor="middle" class="muted">Ten bars, one for each complete seven-day period; segment colors identify the day position within the period.</text>')
    save_svg("03_activity_timeline.svg", parts)


def weekly_groups(daily):
    ordered = sorted(daily, key=lambda row: row["date"])
    return [ordered[start:start + 7] for start in range(0, len(ordered), 7) if len(ordered[start:start + 7]) == 7]


def sleep_stem_leaf(sleeps, daily):
    weekday_by_date = {row["date"]: row["weekday"] for row in daily}
    weekday_order = ("M", "T", "W", "Th", "F", "Sa", "Su")
    values = defaultdict(list)
    for row in sleeps:
        weekday = weekday_by_date.get(row["next_wake"])
        if weekday:
            rounded = int((int(row["sleep_minutes"]) + 15) // 30) * 30
            values[weekday].append(rounded // 60 * 2 + (rounded % 60) // 30)
    width, height = 900, 430
    parts = svg_start("Sleep by waking-day weekday: stem and leaf", width, height)
    parts.append('<text x="48" y="62" class="muted">Values are rounded to the nearest half-hour; each leaf is a half-hour unit (0 = :00, 1 = :30).</text>')
    parts.append('<text x="115" y="105" font-size="13" font-weight="700">weekday</text><text x="220" y="105" font-size="13" font-weight="700">stem | leaves</text>')
    for index, weekday in enumerate(weekday_order):
        y = 140 + index * 36
        leaves = sorted(values[weekday])
        rendered = " ".join(str(value % 2) for value in leaves)
        stems = sorted(set(value // 2 for value in leaves))
        stem_text = "; ".join(f"{stem} | {' '.join(str(value % 2) for value in leaves if value // 2 == stem)}" for stem in stems) or "no observations"
        parts.append(f'<text x="170" y="{y}" text-anchor="end" font-size="14" font-weight="700">{weekday}</text>')
        parts.append(f'<text x="220" y="{y}" font-family="monospace" font-size="14">{stem_text}</text>')
    parts.append('<text x="48" y="405" class="muted">Stem is whole hours of sleep; leaves preserve the nearest 30-minute increment. The day is assigned to the following wake day.</text>')
    save_svg("06_sleep_stem_leaf.svg", parts)


def correlation(values):
    count = len(values)
    means = [sum(column) / count for column in zip(*values)]
    deviations = [[value - mean for value, mean in zip(column, means)] for column in zip(*values)]
    result = []
    for left_column in deviations:
        row = []
        for right_column in deviations:
            denominator = math.sqrt(sum(value * value for value in left_column) * sum(value * value for value in right_column))
            row.append(sum(left * right for left, right in zip(left_column, right_column)) / denominator if denominator else 0)
        result.append(row)
    return result


def weekly_correlation_matrix(daily):
    groups = weekly_groups(daily)
    weekly_totals = [[sum(int(row[category]) for row in group) for category in CATEGORIES] for group in groups]
    matrix = correlation(weekly_totals)
    width, height, left, top, cell = 760, 610, 150, 100, 58
    parts = svg_start("Correlation matrix of category totals across ten weeks", width, height)
    parts.append('<text x="48" y="62" class="muted">Each observation is one complete seven-day period; coefficients are Pearson correlations of weekly minutes.</text>')
    for index, category in enumerate(CATEGORIES):
        x = left + index * cell + cell / 2
        y = top + index * cell + cell / 2
        parts.append(f'<text x="{x}" y="{top - 12}" text-anchor="middle" font-size="12" font-weight="700">{category}</text>')
        parts.append(f'<text x="{left - 12}" y="{y + 4}" text-anchor="end" font-size="12" font-weight="700">{category}</text>')
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            x = left + column_index * cell
            y = top + row_index * cell
            red = int(255 - max(0, value) * 105)
            blue = int(255 - max(0, -value) * 105)
            fill = f"rgb({red}, {int(255 - abs(value) * 80)}, {blue})"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" stroke="#ffffff"/>')
            parts.append(f'<text x="{x + cell / 2}" y="{y + cell / 2 + 5}" text-anchor="middle" font-size="12">{value:.2f}</text>')
    parts.append('<text x="150" y="565" class="muted">Blue indicates positive association; red indicates negative association.</text>')
    save_svg("08_weekly_category_correlation.svg", parts)


def daily_category_qq(daily, category):
    observed = sorted(int(row[category]) for row in daily)
    mean = sum(observed) / len(observed)
    standard_deviation = math.sqrt(sum((value - mean) ** 2 for value in observed) / max(1, len(observed) - 1))
    reference = [mean + standard_deviation * NormalDist().inv_cdf((index + 0.5) / len(observed)) for index in range(len(observed))]
    values = observed + reference
    minimum, maximum = min(values), max(values)
    span = max(1, maximum - minimum)
    width, height, left, top, plot_w, plot_h = 800, 560, 90, 70, 610, 400
    parts = svg_start(f"Normal Q-Q plot of daily {category} totals (70 days)", width, height)
    def px(value): return left + (value - minimum) / span * plot_w
    def py(value): return top + plot_h - (value - minimum) / span * plot_h
    parts.append(f'<line x1="{px(minimum)}" y1="{py(minimum)}" x2="{px(maximum)}" y2="{py(maximum)}" stroke="#d1495b" stroke-width="2" stroke-dasharray="6 5"/>')
    for expected, actual in zip(reference, observed):
        parts.append(f'<circle cx="{px(expected):.1f}" cy="{py(actual):.1f}" r="3.5" fill="{COLORS[category]}"/>')
    for value in (minimum, maximum):
        parts.append(f'<text x="{px(value):.1f}" y="{top + plot_h + 22}" text-anchor="middle" class="muted">{value:.0f}</text><text x="{left - 8}" y="{py(value) + 4:.1f}" text-anchor="end" class="muted">{value:.0f}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/><line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    parts.append('<text x="395" y="535" text-anchor="middle" class="muted">Expected normal quantiles, fitted to the 70 daily totals</text><text x="20" y="280" transform="rotate(-90 20 280)" text-anchor="middle" class="muted">Observed sorted daily minutes</text>')
    save_svg(f"{category.lower()}_daily_qq.svg", parts)


def weekday_strip_plot(daily):
    weekday_order = ("M", "T", "W", "Th", "F", "Sa", "Su")
    ordered = sorted(daily, key=lambda row: row["date"])
    width, height, left, top, plot_w, plot_h = 1200, 760, 90, 80, 1020, 580
    maximum = max((int(row[category]) for row in ordered for category in CATEGORIES), default=60)
    maximum = max(60, math.ceil(maximum / 60) * 60)
    parts = svg_start("Weekday distributions across all trial pairs", width, height)
    parts.append('<text x="48" y="62" class="muted">Each point is one day; colors identify categories and preserve the ten observations for every weekday.</text>')
    for hour in range(0, maximum + 1, 120):
        y = top + plot_h - hour / maximum * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/><text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="muted">{hour // 60}h</text>')
    band = plot_w / len(weekday_order)
    for day_index, weekday in enumerate(weekday_order):
        center = left + (day_index + 0.5) * band
        parts.append(f'<text x="{center:.1f}" y="{top + plot_h + 24}" text-anchor="middle" font-size="13" font-weight="700">{weekday}</text>')
        day_rows = [row for row in ordered if row["weekday"] == weekday]
        for category_index, category in enumerate(CATEGORIES):
            offset = (category_index - (len(CATEGORIES) - 1) / 2) * 4.2
            for row in day_rows:
                value = int(row[category])
                y = top + plot_h - value / maximum * plot_h
                parts.append(f'<circle cx="{center + offset:.1f}" cy="{y:.1f}" r="2.8" fill="{COLORS[category]}"><title>{row["date"]} {weekday} {category}: {value} minutes</title></circle>')
    for index, category in enumerate(CATEGORIES):
        x = 120 + index * 145
        parts.append(f'<circle cx="{x}" cy="35" r="4" fill="{COLORS[category]}"/><text x="{x + 10}" y="39" class="muted">{category}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/><line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    save_svg("04_bad_weekday_category_strip.svg", parts)


def daily_composition(daily):
    ordered = sorted(daily, key=lambda row: row["date"])
    width, height, left, top, plot_w, plot_h = 1200, 620, 100, 80, 1040, 430
    parts = svg_start("Daily activity composition as percentages", width, height)
    parts.append('<text x="48" y="62" class="muted">Each bar is normalized to 100% of recorded category time, separating composition from total recorded duration.</text>')
    for percent in range(0, 101, 20):
        y = top + plot_h - percent / 100 * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/><text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="muted">{percent}%</text>')
    bar_w = max(2, plot_w / len(ordered) * 0.82)
    for index, row in enumerate(ordered):
        total = sum(int(row[category]) for category in CATEGORIES) or 1
        x = left + (index + 0.5) / len(ordered) * plot_w - bar_w / 2
        bottom = top + plot_h
        for category in CATEGORIES:
            share = int(row[category]) / total
            bar_h = share * plot_h
            bottom -= bar_h
            parts.append(f'<rect x="{x:.1f}" y="{bottom:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{COLORS[category]}"><title>{row["date"]} {category}: {int(row[category])} minutes ({share:.1%})</title></rect>')
    for index, category in enumerate(CATEGORIES):
        x = 115 + index * 145
        parts.append(f'<rect x="{x}" y="35" width="10" height="10" fill="{COLORS[category]}"/><text x="{x + 16}" y="44" class="muted">{category}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/><line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    parts.append('<text x="600" y="570" text-anchor="middle" class="muted">Chronological waking days; hover over a segment for exact minutes and share.</text>')
    save_svg("12_daily_composition_percent.svg", parts)


def solve_linear_system(matrix, values):
    augmented = [row[:] + [value] for row, value in zip(matrix, values)]
    size = len(values)
    for pivot in range(size):
        pivot_row = max(range(pivot, size), key=lambda row: abs(augmented[row][pivot]))
        if abs(augmented[pivot_row][pivot]) < 1e-10:
            continue
        augmented[pivot], augmented[pivot_row] = augmented[pivot_row], augmented[pivot]
        divisor = augmented[pivot][pivot]
        augmented[pivot] = [value / divisor for value in augmented[pivot]]
        for row in range(size):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [current - factor * pivot_value for current, pivot_value in zip(augmented[row], augmented[pivot])]
    return [augmented[index][-1] for index in range(size)]


def residual_correlation_matrix(daily):
    weekday_order = ("M", "T", "W", "Th", "F", "Sa", "Su")
    design = []
    for row in daily:
        total = sum(int(row[category]) for category in CATEGORIES)
        design.append([1] + [1 if row["weekday"] == weekday else 0 for weekday in weekday_order[1:]] + [total])
    transpose = list(zip(*design))
    gram = [[sum(left * right for left, right in zip(row_left, row_right)) for row_right in transpose] for row_left in transpose]
    residuals = []
    for category in CATEGORIES:
        target = [int(row[category]) for row in daily]
        right_side = [sum(column_value * target_value for column_value, target_value in zip(column, target)) for column in transpose]
        coefficients = solve_linear_system(gram, right_side)
        residuals.append([target_value - sum(coefficient * predictor for coefficient, predictor in zip(coefficients, predictors)) for target_value, predictors in zip(target, design)])
    matrix = correlation(list(zip(*residuals)))
    width, height, left, top, cell = 760, 610, 150, 100, 58
    parts = svg_start("Residual category correlations", width, height)
    parts.append('<text x="48" y="62" class="muted">Pearson correlations after removing weekday and total recorded-time effects from each category.</text>')
    for index, category in enumerate(CATEGORIES):
        x = left + index * cell + cell / 2
        y = top + index * cell + cell / 2
        parts.append(f'<text x="{x}" y="{top - 12}" text-anchor="middle" font-size="12" font-weight="700">{category}</text>')
        parts.append(f'<text x="{left - 12}" y="{y + 4}" text-anchor="end" font-size="12" font-weight="700">{category}</text>')
    for row_index, row in enumerate(matrix):
        for column_index, value in enumerate(row):
            x = left + column_index * cell
            y = top + row_index * cell
            red = int(255 - max(0, value) * 105)
            blue = int(255 - max(0, -value) * 105)
            fill = f"rgb({red}, {int(255 - abs(value) * 80)}, {blue})"
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" fill="{fill}" stroke="#ffffff"/>')
            parts.append(f'<text x="{x + cell / 2}" y="{y + cell / 2 + 5}" text-anchor="middle" font-size="12">{value:.2f}</text>')
    save_svg("13_residual_category_correlation.svg", parts)


def category_pair_matrix(daily):
    ordered = sorted(daily, key=lambda row: row["date"])
    values = {category: [int(row[category]) for row in ordered] for category in CATEGORIES}
    means = {category: sum(series) / len(series) for category, series in values.items()}
    cell = 138
    left, top = 105, 100
    width = left + cell * len(CATEGORIES) + 35
    height = top + cell * len(CATEGORIES) + 70
    parts = svg_start("Daily category pair matrix: above and below average", width, height)
    parts.append('<text x="48" y="62" class="muted">Each off-diagonal panel compares two categories across all 70 waking days. Dashed lines mark each category&apos;s daily mean.</text>')
    for index, category in enumerate(CATEGORIES):
        center = left + index * cell + cell / 2
        parts.append(f'<text x="{center}" y="88" text-anchor="middle" font-size="12" font-weight="700">{category}</text>')
        parts.append(f'<text x="{left - 12}" y="{top + index * cell + cell / 2 + 4}" text-anchor="end" font-size="12" font-weight="700">{category}</text>')
    for row_index, y_category in enumerate(CATEGORIES):
        y_values = values[y_category]
        y_max = max(y_values + [means[y_category], 1])
        for column_index, x_category in enumerate(CATEGORIES):
            x_values = values[x_category]
            x_max = max(x_values + [means[x_category], 1])
            x0 = left + column_index * cell
            y0 = top + row_index * cell
            parts.append(f'<rect x="{x0}" y="{y0}" width="{cell - 2}" height="{cell - 2}" fill="#ffffff" stroke="#dfe4ea"/>')
            if x_category == y_category:
                parts.append(f'<text x="{x0 + cell / 2}" y="{y0 + cell / 2 - 4}" text-anchor="middle" font-size="13" font-weight="700">mean</text>')
                parts.append(f'<text x="{x0 + cell / 2}" y="{y0 + cell / 2 + 16}" text-anchor="middle" font-size="13">{means[x_category]:.0f} min</text>')
                continue
            x_mean = means[x_category] / x_max * (cell - 24)
            y_mean = (cell - 24) - means[y_category] / y_max * (cell - 24)
            parts.append(f'<line x1="{x0 + 12 + x_mean:.1f}" y1="{y0 + 8}" x2="{x0 + 12 + x_mean:.1f}" y2="{y0 + cell - 16}" stroke="#d1495b" stroke-dasharray="3 3"/>')
            parts.append(f'<line x1="{x0 + 12}" y1="{y0 + 8 + y_mean:.1f}" x2="{x0 + cell - 14}" y2="{y0 + 8 + y_mean:.1f}" stroke="#d1495b" stroke-dasharray="3 3"/>')
            for x_value, y_value in zip(x_values, y_values):
                x = x0 + 12 + x_value / x_max * (cell - 24)
                y = y0 + cell - 16 - y_value / y_max * (cell - 24)
                parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.8" fill="{COLORS[y_category]}" opacity=".55"/>')
    parts.append(f'<text x="{left + cell * len(CATEGORIES) / 2}" y="{height - 18}" text-anchor="middle" class="muted">Horizontal position: category in the column; vertical position: category in the row. Upper-left quadrants indicate above-average row values and below-average column values.</text>')
    save_svg("14_daily_category_pair_matrix.svg", parts)




def weekday_stacked_bar(daily):
    weekday_order = ("M", "T", "W", "Th", "F", "Sa", "Su")
    totals = {weekday: {category: 0 for category in CATEGORIES} for weekday in weekday_order}
    for row in daily:
        for category in CATEGORIES:
            totals[row["weekday"]][category] += int(row[category])
    width, height, left, top, plot_w, plot_h = 1000, 600, 90, 75, 830, 405
    max_value = max(sum(values.values()) for values in totals.values())
    parts = svg_start("All-data category totals by weekday", width, height)
    for hour in range(0, math.ceil(max_value / 1200) * 1200 + 1, 1200):
        y = top + plot_h - hour / max_value * plot_h
        parts.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + plot_w}" y2="{y:.1f}" class="grid"/><text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end" class="muted">{hour // 60}h</text>')
    bar_w = plot_w / len(weekday_order) * 0.68
    for index, weekday in enumerate(weekday_order):
        x = left + (index + 0.5) / len(weekday_order) * plot_w - bar_w / 2
        bottom = top + plot_h
        for category in CATEGORIES:
            value = totals[weekday][category]
            bar_h = value / max_value * plot_h
            bottom -= bar_h
            parts.append(f'<rect x="{x:.1f}" y="{bottom:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" fill="{COLORS[category]}"><title>{weekday} {category}: {value} minutes</title></rect>')
            if bar_h >= 18:
                parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{bottom + bar_h / 2 + 4:.1f}" text-anchor="middle" font-size="10" fill="#263238">{value / 60:.1f}h</text>')
        parts.append(f'<text x="{x + bar_w / 2:.1f}" y="{top + plot_h + 22}" text-anchor="middle" class="muted">{weekday}</text>')
    for index, category in enumerate(CATEGORIES):
        x = 105 + index * 120
        parts.append(f'<rect x="{x}" y="45" width="10" height="10" fill="{COLORS[category]}"/><text x="{x + 16}" y="54" class="muted">{category}</text>')
    parts.append(f'<line x1="{left}" y1="{top + plot_h}" x2="{left + plot_w}" y2="{top + plot_h}" class="axis"/><line x1="{left}" y1="{top}" x2="{left}" y2="{top + plot_h}" class="axis"/>')
    save_svg("10_weekday_stacked_bar.svg", parts)


def main():
    OUT.mkdir(exist_ok=True)
    blocks, malformed = parse_file()
    activities, daily, sleeps, anomalies = analyze(blocks, malformed)
    write_csv("activities.csv", activities)
    write_csv("daily_totals.csv", daily)
    write_csv("sleep.csv", sleeps)
    write_csv("anomalies.csv", anomalies)
    heatmap(daily); relationship(daily, sleeps); timeline(activities, daily)
    sleep_stem_leaf(sleeps, daily)
    weekly_correlation_matrix(daily)
    for category in CATEGORIES:
        daily_category_qq(daily, category)
    weekday_stacked_bar(daily)
    weekday_strip_plot(daily)
    daily_composition(daily)
    residual_correlation_matrix(daily)
    category_pair_matrix(daily)
    print(f"day_headers={len(blocks)} activity_rows={len(activities)} sleep_intervals={len(sleeps)}")
    print(f"recordings={len({row['recording'] for row in daily})} anomalies={len(anomalies)}")
    print(f"five_hour_activity_anomalies={sum(row['kind'] == 'activity_over_5_hours' for row in anomalies)}")
    print(f"output={OUT}")


if __name__ == "__main__":
    main()