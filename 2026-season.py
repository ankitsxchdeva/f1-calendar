import calendar
from io import BytesIO
from datetime import date, timedelta
from pathlib import Path
from urllib.request import urlopen

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

WIDTH, HEIGHT = 18 * inch, 24 * inch

race_sundays = {
    (3, 8): "AUSTRALIA",
    (3, 15): "CHINA",
    (3, 29): "JAPAN",
    (4, 12): "BAHRAIN",
    (4, 19): "SAUDI ARABIA",
    (5, 3): "MIAMI",
    (5, 24): "CANADA",
    (6, 7): "MONACO",
    (6, 14): "BARCELONA",
    (6, 28): "AUSTRIA",
    (7, 5): "GREAT BRITAIN",
    (7, 19): "BELGIUM",
    (7, 26): "HUNGARY",
    (8, 23): "NETHERLANDS",
    (9, 6): "ITALY",
    (9, 13): "MADRID",
    (9, 26): "AZERBAIJAN",
    (10, 11): "SINGAPORE",
    (10, 25): "AUSTIN",
    (11, 1): "MEXICO",
    (11, 8): "BRAZIL",
    (11, 21): "LAS VEGAS",
    (11, 29): "QATAR",
    (12, 6): "ABU DHABI",
}

# ISO 2-letter country codes for flag images (flagcdn.com)
COUNTRY_FLAG_CODES = {
    "AUSTRALIA": "au",
    "CHINA": "cn",
    "JAPAN": "jp",
    "BAHRAIN": "bh",
    "SAUDI ARABIA": "sa",
    "MIAMI": "us",
    "CANADA": "ca",
    "MONACO": "mc",
    "BARCELONA": "es",  # Spain
    "SPAIN (BARCELONA)": "es",
    "AUSTRIA": "at",
    "GREAT BRITAIN": "gb",
    "BELGIUM": "be",
    "HUNGARY": "hu",
    "NETHERLANDS": "nl",
    "ITALY": "it",
    "MADRID": "es",
    "AZERBAIJAN": "az",
    "SINGAPORE": "sg",
    "AUSTIN": "us",
    "MEXICO": "mx",
    "BRAZIL": "br",
    "LAS VEGAS": "us",
    "QATAR": "qa",
    "ABU DHABI": "ae",
}

_flag_cache = {}


def get_flag_image(cc: str) -> "ImageReader | None":
    """Return ImageReader for country code, or None if unavailable. Cached in memory and on disk."""
    if cc in _flag_cache:
        return _flag_cache[cc]
    # Try local cache first (works offline after first run)
    flags_dir = Path(__file__).resolve().parent / "flags"
    local_path = flags_dir / f"{cc}.png"
    if local_path.exists():
        try:
            _flag_cache[cc] = ImageReader(str(local_path))
            return _flag_cache[cc]
        except Exception:
            pass
    # Fetch from URL and cache locally
    try:
        url = f"https://flagcdn.com/w80/{cc}.png"
        data = urlopen(url, timeout=5).read()
        flags_dir.mkdir(exist_ok=True)
        local_path.write_bytes(data)
        _flag_cache[cc] = ImageReader(BytesIO(data))
        return _flag_cache[cc]
    except Exception:
        _flag_cache[cc] = None
        return None


def month_weeks(month: int):
    cal = calendar.Calendar(firstweekday=6)  # Sunday
    return cal.monthdayscalendar(2026, month)


def draw_checkered(c, x, y, w, h, color1, color2, squares=24):
    # simple alternating rectangles
    sq_w = w / squares
    for i in range(squares):
        c.setFillColor(color1 if i % 2 == 0 else color2)
        c.rect(x + i * sq_w, y, sq_w, h, stroke=0, fill=1)


def draw_month(c, x, y, w, h, month, theme):
    """
    Draws a month block at top-left (x,y) where y is top edge.
    """
    text = theme["ink"]
    accent = theme["accent"]
    light_ink = theme["ink_light"]

    # Padding inside month block
    pad = 0.12 * inch
    header_h = 0.32 * inch
    list_h = 0.72 * inch  # space for race list under grid (fits 4 races + gap)

    # Month name
    c.setFillColor(text)
    c.setFont(theme["font"], 14)
    c.drawString(x + pad, y - pad - 10, calendar.month_name[month].upper())

    # Calendar grid area
    grid_top = y - pad - header_h
    grid_left = x + pad
    grid_w = w - 2 * pad
    grid_h = h - (pad + header_h + list_h + pad)

    # Weekday header: thin band (not a full cell height)
    weekday_row_h = 0.11 * inch
    day_grid_h = grid_h - weekday_row_h
    day_row_h = day_grid_h / 6.0
    col_w = grid_w / 7.0

    weekdays = ["S", "M", "T", "W", "T", "F", "S"]
    c.setFont(theme["font"], 8)
    c.setFillColor(light_ink)
    weekday_center_y = grid_top - weekday_row_h / 2
    for col, wd in enumerate(weekdays):
        cx = grid_left + col * col_w + col_w / 2
        c.drawCentredString(cx, weekday_center_y - 2.5, wd)

    # Grid lines (subtle): one under weekday band, then 6 day rows
    c.setStrokeColor(theme["grid"])
    c.setLineWidth(0.3)
    grid_bottom = grid_top - weekday_row_h - 6 * day_row_h
    # Horizontal lines
    c.line(grid_left, grid_top, grid_left + grid_w, grid_top)
    c.line(grid_left, grid_top - weekday_row_h, grid_left + grid_w, grid_top - weekday_row_h)
    for r in range(1, 7):
        yy = grid_top - weekday_row_h - r * day_row_h
        c.line(grid_left, yy, grid_left + grid_w, yy)
    # Vertical lines
    for col in range(0, 8):
        xx = grid_left + col * col_w
        c.line(xx, grid_top, xx, grid_bottom)

    # Days
    weeks = month_weeks(month)  # list of week rows (length 4-6), 0 for blanks
    # We will map them into 6 rows for consistent layout
    while len(weeks) < 6:
        weeks.append([0] * 7)

    # Precompute weekend underline days for this month (Fri/Sat/Sun of race weekends)
    underline_days = set()
    for (m, d), _ in race_sundays.items():
        if m != month:
            continue
        sun = date(2026, m, d)
        fri = sun - timedelta(days=2)
        sat = sun - timedelta(days=1)
        underline_days.update(
            [(fri.month, fri.day), (sat.month, sat.day), (sun.month, sun.day)]
        )

    day_font = theme["font"]
    day_size = 8
    c.setFont(day_font, day_size)
    c.setFillColor(text)

    for r in range(6):
        week = weeks[r]
        for col in range(7):
            day = week[col]
            if day == 0:
                continue
            cell_x = grid_left + col * col_w
            # Row r top: grid_top - weekday_row_h - r*day_row_h (was r+1, which shifted all rows down)
            cell_top = grid_top - weekday_row_h - r * day_row_h
            cx = cell_x + col_w / 2
            ty = cell_top - day_row_h + 3  # baseline near bottom of cell

            day_str = str(day)
            c.drawCentredString(cx, ty, day_str)

            # Underline only under the date number (race weekend days)
            if (month, day) in underline_days:
                digit_width = c.stringWidth(day_str, day_font, day_size)
                uy = ty - 3
                c.setStrokeColor(accent)
                c.setLineWidth(0.8)
                c.line(cx - digit_width / 2, uy, cx + digit_width / 2, uy)
                c.setStrokeColor(theme["grid"])
                c.setLineWidth(0.3)

    # Race list under calendar (flag + date and name, no header)
    gap_below_grid = 0.14 * inch  # clear gap between calendar grid and race list
    list_y_top = grid_bottom - gap_below_grid
    flag_w, flag_h = 14, 10  # points
    text_indent = grid_left + flag_w + 4  # space for flag + gap
    c.setFillColor(text)
    c.setFont(theme["font"], 8)
    races = [(d, race_sundays[(month, d)]) for (m, d) in race_sundays if m == month]
    races.sort(key=lambda t: t[0])
    line_h = 10  # points per race line (flag + text)
    for d, name in races:
        cc = COUNTRY_FLAG_CODES.get(name)
        if cc:
            img = get_flag_image(cc)
            if img is not None:
                # Align flag with text: text baseline is list_y_top, cap height ~6pt → center flag there
                flag_y = list_y_top - 2  # flag bottom; top at list_y_top+8 so flag centers with 8pt text
                c.drawImage(img, grid_left, flag_y, width=flag_w, height=flag_h)
        c.drawString(text_indent, list_y_top, f"{d:02d} – {name}")
        list_y_top -= line_h


def make_poster(path, theme):
    c = canvas.Canvas(path, pagesize=(WIDTH, HEIGHT))

    # Background
    c.setFillColor(theme["paper"])
    c.rect(0, 0, WIDTH, HEIGHT, stroke=0, fill=1)

    margin = 0.75 * inch

    # Header (larger title, no strip – uses that space)
    header_y = HEIGHT - margin
    c.setFillColor(theme["ink"])
    c.setFont(theme["font_bold"], 42)
    c.drawString(margin, header_y - 48, "2026 FORMULA 1 SEASON")

    # Grid for months: 3 columns x 4 rows
    grid_top = header_y - 80
    grid_bottom = margin
    grid_h = grid_top - grid_bottom
    cols, rows = 3, 4
    gap_x = 0.35 * inch
    gap_y = 0.40 * inch
    cell_w = (WIDTH - 2 * margin - (cols - 1) * gap_x) / cols
    cell_h = (grid_h - (rows - 1) * gap_y) / rows

    month = 1
    for r in range(rows):
        for col in range(cols):
            x = margin + col * (cell_w + gap_x)
            y = grid_top - r * (cell_h + gap_y)
            # draw month block
            # subtle month block outline (very light)
            c.setStrokeColor(theme["grid"])
            c.setLineWidth(0.6)
            c.roundRect(x, y - cell_h, cell_w, cell_h, 10, stroke=1, fill=0)
            draw_month(c, x, y, cell_w, cell_h, month, theme)
            month += 1

    c.showPage()
    c.save()


theme = {
    "paper": colors.HexColor("#E4E2DC"),   # greyish warm off-white (good contrast with black text)
    "ink": colors.HexColor("#1A1A1A"),
    "ink_light": colors.HexColor("#5C5A54"),
    "accent": colors.HexColor("#C1121F"),  # classic red
    "grid": colors.HexColor("#CAC6BE"),    # subtle grid, harmonizes with grey paper
    "font": "Helvetica",
    "font_bold": "Helvetica-Bold",
}

OUTPUT_DIR = Path(__file__).resolve().parent
output_path = str(OUTPUT_DIR / "Formula-1-2026-Calendar.pdf")

make_poster(output_path, theme)
