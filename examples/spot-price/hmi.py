"""Operator page of the spot price project: the price now, the upcoming 24 hours as bars (green = the load may
run), the plan (cheapest consecutive hours) and the price-controlled load with its settings."""
from pxhmi import Page

D = "M."
GREEN, AMBER, RED, BLUE = "#FF2FA84F", "#FFE0A020", "#FFD23B3B", "#FF2F7FD0"
BG, CARD, EDGE, INK, DIM, BAR = "#FFF1F3F5", "#FFFFFFFF", "#FFD5DADF", "#FF1E2428", "#FF6B747B", "#FFB4BCC3"
W, H = 1280, 720


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

    def seg(x, y, w, var, items):
        for i, (label, val) in enumerate(items):
            bx = x + i * (w + 8)
            p.rect(oid(), bx - 2, y - 2, w + 4, 36, fill=BLUE, line_width=0, radius=4, visible="%s = %d" % (D + var, val))
            p.button(oid(), bx, y, w, 32, label, write=(D + var, str(val)), size=13)

    def setting(x, y, label, var, st, fmt, unit, lw=150):
        t(x, y + 5, lw, 20, label, size=12, color=DIM)
        p.button(oid(), x + lw, y, 30, 28, "-", step=(D + var, -st), size=16)
        v(x + lw + 32, y + 3, 44, 22, var, fmt=fmt, size=14, align="Center")
        p.button(oid(), x + lw + 78, y, 30, 28, "+", step=(D + var, st), size=16)
        t(x + lw + 114, y + 6, 44, 18, unit, size=11, color=DIM)

    # header
    p.rect(oid(), 0, 0, W, 64, fill="#FF1F2A33", line_width=0)
    t(24, 10, 500, 30, "Spot price", size=24, color="#FFFFFFFF", weight=700)
    t(24, 40, 700, 18, "day-ahead electricity price from the price bridge (Modbus TCP), c/kWh without VAT", size=12, color="#FFB9C4CC")
    p.ellipse(oid(), 1010, 24, 16, 16, fill=RED, line_width=0, fill_by=(D + "VALID", [(0, RED), (1, GREEN)]))
    t(1034, 21, 230, 22, "price data OK", size=15, color="#FFFFFFFF", visible=D + "VALID")
    t(1034, 21, 230, 22, "NO PRICE DATA", size=15, color="#FFFF9A9A", weight=700, visible="NOT " + D + "VALID")

    # 1: now
    card(16, 80, 300, 624, "Now")
    v(34, 122, 170, 70, "PRICE", fmt="fixed2", size=52)
    t(212, 150, 90, 30, "c/kWh", size=18, color=DIM)
    rows = [("with VAT and margin", "PRICE_TOTAL", "fixed2", "c/kWh"), ("rank of the hour today", "RANK", None, "/ 24"),
            ("hour of the day", "HOUR", None, ""), ("upcoming hours known", "KNOWN", None, "h"),
            ("their average", "P_AVG", "fixed2", "c/kWh"), ("lowest", "P_MIN", "fixed2", "c/kWh"),
            ("highest", "P_MAX", "fixed2", "c/kWh")]
    for i, (label, var, fmt, unit) in enumerate(rows):
        y = 220 + i * 30
        t(34, y, 170, 20, label, size=12, color=DIM)
        v(196, y - 2, 64, 22, var, fmt=fmt, size=14)
        t(266, y, 46, 20, unit, size=12, color=DIM)
    p.rect(oid(), 34, 530, 264, 1, fill=EDGE, line_width=0)
    t(34, 540, 200, 18, "Price bridge", size=13, weight=700)
    lamps = [("connection", "LINK"), ("bridge says valid", "SRC_VALID"), ("beat moves", "BEAT_OK"), ("tomorrow published", "TOMO_OK")]
    for i, (label, var) in enumerate(lamps):
        y = 566 + i * 24
        p.ellipse(oid(), 36, y + 3, 12, 12, fill=RED, line_width=0,
                  fill_by=(D + var, [(0, BAR if var == "TOMO_OK" else RED), (1, GREEN)]))
        t(56, y, 150, 18, label, size=12, color=DIM)
    t(196, 566, 60, 18, "beat", size=12, color=DIM); v(232, 564, 60, 20, "BEAT", fmt=None, size=13)
    t(196, 590, 60, 18, "age min", size=12, color=DIM); v(232, 588, 60, 20, "AGE_MIN", fmt=None, size=13)
    t(196, 614, 60, 18, "lost", size=12, color=DIM); v(232, 612, 60, 20, "MB_OFFLINE", fmt=None, size=13)

    # 2: upcoming hours
    x, y = 332, 80
    card(x, y, 600, 356, "Upcoming hours")
    t(x + 250, y + 16, 332, 18, "green = the load may run     blue foot = negative price", size=11, color=DIM, align="Right")
    bx, by, bh, bw, gap = x + 44, y + 64, 220, 17, 5
    t(x + 6, by - 8, 32, 16, "0", size=11, color=DIM, value=D + "SCALE", fmt="fixed0", align="Right")
    t(x + 6, by + bh - 8, 32, 16, "0", size=11, color=DIM, align="Right")
    t(x + 6, by + 14, 32, 14, "c/kWh", size=9, color=DIM, align="Right")
    p.rect(oid(), bx - 4, by, 24 * (bw + gap) + 4, 1, fill=EDGE, line_width=0)
    p.rect(oid(), bx - 4, by + bh // 2, 24 * (bw + gap) + 4, 1, fill=EDGE, line_width=0)
    p.rect(oid(), bx - 4, by + bh, 24 * (bw + gap) + 4, 1, fill="#FF8A939A", line_width=0)
    p.rect(oid(), bx - 3, by - 8, bw + 6, bh + 36, fill="#FFDDEBFA", line=BLUE, line_width=1, radius=3)
    t(bx - 12, by - 26, 60, 16, "now", size=11, color=BLUE, weight=700)
    for h in range(24):
        hx = bx + h * (bw + gap)
        if h:
            p.rect(oid(), hx - 3, by - 14, 1, bh + 42, fill="#FF8A939A", line_width=0, visible="%sHL%02d = 0" % (D, h))
            t(hx + 1, by - 26, 80, 16, "tomorrow", size=11, color=DIM, visible="%sHL%02d = 0" % (D, h))
        p.rect(oid(), hx, by, bw, bh, fill=BAR, line_width=0, fill_by=("%sPL%02d" % (D, h), [(0, BAR), (1, GREEN)]),
               grow=("%sBT%02d" % (D, h), 0, 100), axis="y")
        p.rect(oid(), hx, by + bh + 1, bw, 5, fill=BLUE, line_width=0, visible="%sPT%02d < 0.0" % (D, h))
        v(hx - 4, by + bh + 9, bw + 8, 14, "HL%02d" % h, fmt=None, size=10, color=DIM, weight=400, align="Center")
        t(hx - 4, by + bh + 22, bw + 8, 14, "-", size=10, color=DIM, align="Center", visible="%sKNOWN <= %d" % (D, h))
    t(bx, y + 330, 520, 16, "hour of the day under each bar; '-' = price not published yet", size=11, color=DIM)

    # 3: plan
    y = 452
    card(x, y, 600, 252, "How the price is used")
    seg(x + 18, y + 48, 272, "STRAT", (("Cheapest consecutive hours", 0), ("Cheapest hours of the day", 1)))
    setting(x + 18, y + 98, "block length", "N_BLOCK", 1, None, "h", lw=120)
    setting(x + 308, y + 98, "hours per day", "N_CHEAP", 1, None, "h", lw=120)
    setting(x + 18, y + 136, "never above", "LIM_HIGH", 1, "fixed1", "c/kWh", lw=120)
    setting(x + 308, y + 136, "always at or below", "LIM_LOW", 1, "fixed1", "c/kWh", lw=120)
    p.rect(oid(), x + 18, y + 176, 564, 1, fill=EDGE, line_width=0)
    s0, s1 = D + "STRAT = 0", D + "STRAT = 1"
    ok, run = D + "PLAN_OK", D + "IN_BLOCK"
    t(x + 18, y + 188, 110, 20, "Planned block:", size=13, weight=700, visible=s0)
    t(x + 130, y + 188, 300, 20, "no plan: fewer hours known than the block needs", size=13, color=AMBER,
      visible="%s AND NOT %s" % (s0, ok))
    g = "%s AND %s AND NOT %s" % (s0, ok, run)
    t(x + 130, y + 188, 60, 20, "starts in", size=13, visible=g)
    v(x + 190, y + 187, 30, 22, "START_IN", fmt=None, size=14, align="Center", visible=g)
    t(x + 222, y + 188, 60, 20, "h, at", size=13, visible=g)
    v(x + 258, y + 187, 30, 22, "START_AT", fmt=None, size=14, align="Center", visible=g)
    t(x + 290, y + 188, 30, 20, ":00", size=13, visible=g)
    g = "%s AND %s AND %s" % (s0, ok, run)
    t(x + 130, y + 188, 100, 20, "running now,", size=13, color=GREEN, weight=700, visible=g)
    v(x + 226, y + 187, 30, 22, "LEFT_H", fmt=None, size=14, align="Center", visible=g)
    t(x + 258, y + 188, 60, 20, "h left", size=13, visible=g)
    g = "%s AND %s" % (s0, ok)
    t(x + 340, y + 188, 110, 20, "average price", size=12, color=DIM, visible=g)
    v(x + 430, y + 187, 54, 22, "P_BLOCK", fmt="fixed2", size=14, visible=g)
    t(x + 490, y + 190, 50, 18, "c/kWh", size=11, color=DIM, visible=g)
    p.button(oid(), x + 18, y + 214, 110, 26, "Plan again", write=(D + "REPLAN", "TRUE"), size=12, visible=s0)
    t(x + 140, y + 219, 440, 18, "the block is kept until it has run; planned again when tomorrow's prices arrive",
      size=11, color=DIM, visible=s0)
    t(x + 18, y + 188, 564, 40, "The load runs in the hours whose rank today is within the number set above "
      "(rank from the bridge, per calendar day). The graph marks only the running hour.", size=12, color=DIM, visible=s1)

    # 4: load
    x = 948
    card(x, 80, 316, 624, "Storage tank heater")
    t(x + 18, 122, 100, 18, "Control", size=12, color=DIM)
    seg(x + 18, 144, 86, "MODE", (("Off", 0), ("On", 1), ("By price", 2)))
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
