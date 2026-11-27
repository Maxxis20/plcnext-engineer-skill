"""Operator page of the spot price project (MQTT road): area and resolution, the price now, the upcoming slots as
bars (green = the load may run), the plan (cheapest consecutive hours) and the price-controlled load."""
import json
import os

from pxhmi import Page

D = "M."
GREEN, AMBER, RED, BLUE = "#FF2FA84F", "#FFE0A020", "#FFD23B3B", "#FF2F7FD0"
BG, CARD, EDGE, INK, DIM, BAR = "#FFF1F3F5", "#FFFFFFFF", "#FFD5DADF", "#FF1E2428", "#FF6B747B", "#FFB4BCC3"
W, H = 1280, 720
AREAS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "areas.json")))


def pages():
    p = Page("Spot", W, H, fill=BG)
    n = [0]

    def oid():
        n[0] += 1
        return "o%d" % n[0]

    def t(x, y, w, h, s, size=14, color=INK, **kw):
        p.text(oid(), x, y, w, h, s, size=size, color=color, **kw)

    def v(x, y, w, h, var, fmt="fixed1", size=14, color=INK, weight=700, align="Right", **kw):
        p.value(oid(), x, y, w, h, D + var, fmt=fmt, size=size, color=color, weight=weight, align=align, **kw)

    def card(x, y, w, h, title):
        p.rect(oid(), x, y, w, h, fill=CARD, line=EDGE, radius=10)
        t(x + 18, y + 12, w - 36, 24, title, size=17, weight=700)

    def seg(x, y, w, items):
        """items: (label, variable, value to write, expression that is TRUE when chosen)"""
        for i, (label, var, val, on) in enumerate(items):
            bx = x + i * (w + 8)
            p.rect(oid(), bx - 2, y - 2, w + 4, 36, fill=BLUE, line_width=0, radius=4, visible=on)
            p.button(oid(), bx, y, w, 32, label, write=(D + var, val), size=13)

    def unit(x, y, w, h, size=12, color=DIM, vis=None, **kw):
        """the price unit, following the toggle"""
        for s, g in (("c/kWh", "NOT " + D + "UNIT_MWH"), ("€/MWh", D + "UNIT_MWH")):
            t(x, y, w, h, s, size=size, color=color, visible=g if not vis else "%s AND %s" % (vis, g), **kw)

    def setting(x, y, label, var, st, fmt, un, lw=150, show=None):
        """show: variable to display instead of var (a price in the chosen unit); the buttons step var"""
        t(x, y + 5, lw, 20, label, size=12, color=DIM)
        p.button(oid(), x + lw, y, 30, 28, "-", step=(D + var, -st), size=16)
        v(x + lw + 32, y + 3, 44, 22, show or var, fmt=fmt, size=14, align="Center")
        p.button(oid(), x + lw + 78, y, 30, 28, "+", step=(D + var, st), size=16)
        if un == "price":
            unit(x + lw + 114, y + 6, 44, 18, size=11)
        else:
            t(x + lw + 114, y + 6, 44, 18, un, size=11, color=DIM)

    # header
    p.rect(oid(), 0, 0, W, 64, fill="#FF1F2A33", line_width=0)
    t(24, 10, 500, 30, "Spot price", size=24, color="#FFFFFFFF", weight=700)
    t(24, 40, 700, 18, "day-ahead electricity price from the price bridge (MQTT). All prices VAT 0 %", size=12, color="#FFB9C4CC")
    p.ellipse(oid(), 1010, 24, 16, 16, fill=RED, line_width=0, fill_by=(D + "VALID", [(0, RED), (1, GREEN)]))
    t(1034, 21, 230, 22, "price data OK", size=15, color="#FFFFFFFF", visible=D + "VALID")
    t(1034, 21, 230, 22, "NO PRICE DATA", size=15, color="#FFFF9A9A", weight=700, visible="NOT " + D + "VALID")

    # 1: now, with area and resolution
    card(16, 80, 300, 624, "Now")
    t(34, 122, 60, 18, "Area", size=12, color=DIM)
    p.button(oid(), 80, 116, 30, 28, "<", step=(D + "AREA", -1), size=15, visible=D + "AREA > 0")
    for i, a in enumerate(AREAS):
        t(112, 119, 60, 24, a, size=17, weight=700, align="Center", visible="%sAREA = %d" % (D, i))
    p.button(oid(), 174, 116, 30, 28, ">", step=(D + "AREA", 1), size=15, visible="%sAREA < %d" % (D, len(AREAS) - 1))
    t(34, 160, 60, 18, "Price", size=12, color=DIM)
    seg(80, 152, 104, (("hourly", "RES15", "FALSE", "NOT " + D + "RES15"), ("15 min", "RES15", "TRUE", D + "RES15")))
    v(24, 228, 180, 70, "D_PRICE", fmt="fixed2", size=50)
    unit(210, 246, 90, 26, size=17)
    t(210, 270, 90, 18, "VAT 0 %", size=12, color=DIM, weight=700)
    t(34, 190, 40, 18, "Unit", size=12, color=DIM)
    seg(80, 186, 104, (("c/kWh", "UNIT_MWH", "FALSE", "NOT " + D + "UNIT_MWH"), ("€/MWh", "UNIT_MWH", "TRUE", D + "UNIT_MWH")))
    rows = [("with VAT and margin", "D_TOTAL", "fixed2", "price"), ("rank of the hour today", "RANK", None, "/ 24"),
            ("hour of the day", "HOUR", None, ""), ("prices known ahead", "KNOWN_H", "fixed1", "h"),
            ("their average (VAT 0 %)", "D_AVG", "fixed2", "price"), ("lowest", "D_MIN", "fixed2", "price"),
            ("highest", "D_MAX", "fixed2", "price")]
    for i, (label, var, fmt, un) in enumerate(rows):
        y = 318 + i * 29
        t(34, y, 170, 20, label, size=12, color=DIM)
        v(196, y - 2, 64, 22, var, fmt=fmt, size=14)
        if un == "price":
            unit(266, y, 46, 20)
        else:
            t(266, y, 46, 20, un, size=12, color=DIM)
    p.rect(oid(), 34, 530, 264, 1, fill=EDGE, line_width=0)
    t(34, 540, 200, 18, "Price bridge", size=13, weight=700)
    lamps = [("broker connected", "MQ_CONNECTED"), ("bridge says valid", "SRC_VALID"), ("beat moves", "BEAT_OK"), ("tomorrow published", "TOMO_OK")]
    for i, (label, var) in enumerate(lamps):
        y = 566 + i * 24
        p.ellipse(oid(), 36, y + 3, 12, 12, fill=RED, line_width=0,
                  fill_by=(D + var, [(0, BAR if var == "TOMO_OK" else RED), (1, GREEN)]))
        t(56, y, 150, 18, label, size=12, color=DIM)
    t(188, 566, 60, 18, "messages", size=12, color=DIM); v(238, 564, 54, 20, "MQ_MSGS", fmt=None, size=13)
    t(188, 590, 60, 18, "bytes", size=12, color=DIM); v(238, 588, 54, 20, "MQ_LEN", fmt=None, size=13)
    t(188, 614, 60, 18, "reconn.", size=12, color=DIM); v(238, 612, 54, 20, "MQ_RECONN", fmt=None, size=13)

    # 2: upcoming slots, two sets of bars: 36 hours, or 96 quarters (24 h)
    x, y = 332, 80
    card(x, y, 600, 356, "Upcoming prices (VAT 0 %)")
    t(x + 250, y + 16, 332, 18, "green = the load may run     blue foot = negative price", size=11, color=DIM, align="Right")
    bx, by, bh = x + 40, y + 64, 220
    t(x + 4, by - 8, 32, 16, "0", size=11, color=DIM, value=D + "D_SCALE", fmt="fixed0", align="Right")
    t(x + 4, by + bh - 8, 32, 16, "0", size=11, color=DIM, align="Right")
    unit(x + 4, by + 14, 34, 14, size=9, align="Right")
    for yy, col in ((by, EDGE), (by + bh // 2, EDGE), (by + bh, "#FF8A939A")):
        p.rect(oid(), bx - 4, yy, 552, 1, fill=col, line_width=0)
    t(bx - 10, by - 26, 60, 16, "now", size=11, color=BLUE, weight=700)
    for nbar, bw, gap, gate in ((36, 12, 3, "NOT " + D + "RES15"), (96, 5, 0.7, D + "RES15")):
        pitch = bw + gap
        p.rect(oid(), bx - 2, by - 8, bw + 4, bh + 36, fill="#FFDDEBFA", line=BLUE, line_width=1, radius=2, visible=gate)
        for i in range(nbar):
            hx = bx + i * pitch
            if i:
                p.rect(oid(), hx - gap / 2 - 0.5, by - 14, 1, bh + 42, fill="#FF8A939A", line_width=0,
                       visible="%s AND %sHL%02d = 0" % (gate, D, i))
            p.rect(oid(), hx, by, bw, bh, fill=BAR, line_width=0, fill_by=("%sPL%02d" % (D, i), [(0, BAR), (1, GREEN)]),
                   grow=("%sBT%02d" % (D, i), 0, 100), axis="y", visible=gate)
            p.rect(oid(), hx, by + bh + 1, bw, 5, fill=BLUE, line_width=0, visible="%s AND %sNG%02d" % (gate, D, i))
            v(hx - 6, by + bh + 9, bw + 12, 14, "HL%02d" % i, fmt=None, size=9, color=DIM, weight=400, align="Center",
              visible="%s AND %sHL%02d >= 0" % (gate, D, i))
    t(bx, y + 330, 540, 16, "hour of the day under the bars; vertical line = midnight; empty = not published yet", size=11, color=DIM)

    # 3: plan
    y = 452
    card(x, y, 600, 252, "How the price is used")
    seg(x + 18, y + 48, 272, (("Cheapest consecutive hours", "STRAT", "0", D + "STRAT = 0"),
                              ("Cheapest hours of the day", "STRAT", "1", D + "STRAT = 1")))
    setting(x + 18, y + 98, "block length", "N_BLOCK", 1, None, "h", lw=120)
    setting(x + 308, y + 98, "hours per day", "N_CHEAP", 1, None, "h", lw=120)
    setting(x + 18, y + 136, "never above", "LIM_HIGH", 1, "fixed1", "price", lw=120, show="D_HIGH")
    setting(x + 308, y + 136, "always at or below", "LIM_LOW", 1, "fixed1", "price", lw=120, show="D_LOW")
    p.rect(oid(), x + 18, y + 176, 564, 1, fill=EDGE, line_width=0)
    s0, s1 = D + "STRAT = 0", D + "STRAT = 1"
    ok, run = D + "PLAN_OK", D + "IN_BLOCK"
    t(x + 18, y + 188, 110, 20, "Planned block:", size=13, weight=700, visible=s0)
    t(x + 130, y + 188, 320, 20, "no plan: fewer hours known than the block needs", size=13, color=AMBER,
      visible="%s AND NOT %s" % (s0, ok))
    g = "%s AND %s AND NOT %s" % (s0, ok, run)
    t(x + 130, y + 188, 60, 20, "starts in", size=13, visible=g)
    v(x + 186, y + 187, 46, 22, "START_IN", fmt="fixed2", size=14, align="Center", visible=g)
    t(x + 234, y + 188, 40, 20, "h, at", size=13, visible=g)
    v(x + 268, y + 187, 26, 22, "START_AT_H", fmt=None, size=14, visible=g)
    for m in (0, 15, 30, 45):
        t(x + 295, y + 188, 30, 20, ":%02d" % m, size=14, weight=700, visible="%s AND %sSTART_AT_M = %d" % (g, D, m))
    g = "%s AND %s AND %s" % (s0, ok, run)
    t(x + 130, y + 188, 100, 20, "running now,", size=13, color=GREEN, weight=700, visible=g)
    v(x + 222, y + 187, 46, 22, "LEFT_H", fmt="fixed2", size=14, align="Center", visible=g)
    t(x + 270, y + 188, 60, 20, "h left", size=13, visible=g)
    g = "%s AND %s" % (s0, ok)
    t(x + 350, y + 188, 110, 20, "average price", size=12, color=DIM, visible=g)
    v(x + 436, y + 187, 54, 22, "D_BLOCK", fmt="fixed2", size=14, visible=g)
    unit(x + 496, y + 190, 50, 18, size=11, vis=g)
    p.button(oid(), x + 18, y + 214, 110, 26, "Plan again", write=(D + "REPLAN", "TRUE"), size=12, visible=s0)
    t(x + 140, y + 219, 440, 18, "the block is kept until it has run; planned again when tomorrow's prices arrive",
      size=11, color=DIM, visible=s0)
    t(x + 18, y + 188, 564, 40, "The load runs in the hours whose rank today is within the number set above "
      "(hourly rank from the bridge, per calendar day). The graph marks only the running slot.", size=12, color=DIM, visible=s1)

    # 4: load
    x = 948
    card(x, 80, 316, 624, "Storage tank heater")
    t(x + 18, 122, 100, 18, "Control", size=12, color=DIM)
    seg(x + 18, 144, 86, (("Off", "MODE", "0", D + "MODE = 0"), ("On", "MODE", "1", D + "MODE = 1"),
                          ("By price", "MODE", "2", D + "MODE = 2")))
    reasons = [(0, "Off", DIM), (1, "On by hand: thermostat only", INK), (2, "Released: cheap hour", GREEN),
               (3, "Released: very cheap, boost setpoint", GREEN), (4, "Blocked: price above the limit", AMBER),
               (5, "Waiting for a cheaper hour", AMBER), (6, "No price data: normal operation", RED),
               (7, "Tank cold: heating whatever the price", RED)]
    for val, s, col in reasons:
        t(x + 18, 194, 290, 22, s, size=15, color=col, weight=700, visible="%sREASON = %d" % (D, val))
    p.ellipse(oid(), x + 20, 232, 18, 18, fill=BAR, line_width=0, fill_by=(D + "HEAT", [(0, BAR), (1, AMBER)]))
    t(x + 46, 231, 60, 20, "heater", size=13, color=DIM)
    p.ellipse(oid(), x + 110, 232, 18, 18, fill=BAR, line_width=0, fill_by=(D + "RELEASE", [(0, BAR), (1, GREEN)]))
    t(x + 136, 231, 70, 20, "released", size=13, color=DIM)
    p.button(oid(), x + 220, 230, 78, 22, "sim x20", write=(D + "SIM_FAST", "TRUE"), size=11, visible="NOT " + D + "SIM_FAST")
    p.button(oid(), x + 220, 230, 78, 22, "sim x1", write=(D + "SIM_FAST", "FALSE"), size=11, visible=D + "SIM_FAST")
    t(x + 18, 272, 120, 18, "Tank (simulated)", size=12, color=DIM)
    v(x + 18, 292, 110, 44, "TANK", size=34)
    t(x + 134, 308, 40, 24, "°C", size=16, color=DIM)
    t(x + 180, 296, 60, 18, "setpoint", size=12, color=DIM); v(x + 236, 294, 44, 20, "SP_ACT", fmt="fixed0", size=14)
    p.rect(oid(), x + 18, 356, 280, 1, fill=EDGE, line_width=0)
    t(x + 18, 368, 200, 18, "Tank settings", size=13, weight=700)
    setting(x + 18, 400, "setpoint", "SP", 1, "fixed0", "°C", lw=140)
    setting(x + 18, 438, "boost setpoint", "SP_BOOST", 1, "fixed0", "°C", lw=140)
    setting(x + 18, 476, "heat regardless below", "T_MIN", 1, "fixed0", "°C", lw=140)
    p.rect(oid(), x + 18, 646, 280, 40, fill=RED, line_width=0, radius=6, visible=D + "AL_NOPRICE")
    t(x + 18, 656, 280, 22, "ALARM: no price data", size=15, color="#FFFFFFFF", weight=700, align="Center", visible=D + "AL_NOPRICE")
    return [p]
