"""DH-ex2 operator page: the substation with live values, alarms and the plant model's controls.

Layout after the Schneider EBO graphic of the same example.
Pump and control valve are pxhmi's own shapes: placed by their centre on the pipe, coloured by state.
"""
from pxhmi import Page

D = "DH."                                           # program instance
INK, MUTED, BLUE, GREEN, RED, AMBER, GREY = "#FF2B2F33", "#FF6B7075", "#FF1F5FD0", "#FF1E8E3E", "#FFD93A32", "#FFF29D0C", "#FFB8BCBF"
PIPE_HOT, PIPE_COLD = "#FFD93A32", "#FF2F74D0"


def pages():
    p = Page("Home", 1280, 800, fill="#FFF3F4F6")
    n = [0]

    def oid(prefix):
        n[0] += 1
        return "%s%d" % (prefix, n[0])

    def label(x, y, text, w=260, size=13, weight=400, color=MUTED, align="Left"):
        p.text(oid("L"), x, y, w, size + 8, text, size=size, weight=weight, color=color, align=align)

    def val(x, y, var, unit, size=14, color=BLUE, fmt="fixed1", w=70):
        """value right-aligned in w, unit after it"""
        p.value(oid("V"), x, y, w, size + 8, D + var, size=size, weight=700, align="Right", fmt=fmt, color=color)
        p.text(oid("U"), x + w + 5, y, 60, size + 8, unit, size=size, weight=700, color=color)

    def card(x, y, w, h, title, sub=None):
        p.rect(oid("K"), x, y, w, h, fill="#FFFFFFFF", line="#FFD5D9DD", radius=8)
        label(x + 16, y + 12, title, w=w - 30, size=16, weight=700, color=INK)
        if sub:
            label(x + 16, y + 36, sub, w=w - 30)

    def lamp(x, y, var, on=RED, size=18):
        p.ellipse(oid("S"), x, y, size, size, fill=GREY, fill_by=(D + var, [(0, GREY), (1, on)]))

    def steps(x, y, var, amounts):
        for i, a in enumerate(amounts):
            p.button(oid("B"), x + i * 62, y, 56, 32, ("+%g" if a > 0 else "%g") % a, step=(D + var, a), size=15)

    p.text("Title", 24, 14, 1100, 36, "DH-ex2  District heating substation: domestic hot water and heating",
           size=24, weight=700, color=INK)

    # ---- left column: plant model inputs and alarms
    card(24, 64, 300, 236, "Outdoor temperature", "model, click to change")
    val(40, 126, "TOUT", "°C", size=26, w=90)
    steps(40, 172, "TOUT", [-5, -1, 1, 5])
    label(40, 218, "controller TE2B", color=INK); val(170, 216, "TE2B", "°C")
    label(40, 242, "filtered TE2B_F", color=INK); val(170, 240, "TE2B_F", "°C")
    label(40, 268, "Summer stop", color=INK)
    p.text("SumOff", 175, 266, 80, 22, "off", size=14, weight=700, color=MUTED, visible="NOT " + D + "SUMMER")
    p.text("SumOn", 175, 266, 80, 22, "ACTIVE", size=14, weight=700, color=AMBER, visible=D + "SUMMER")

    card(24, 312, 300, 124, "Hot water tapping (model)")
    val(40, 346, "DHW_TAP", "l/min", size=26, w=90)
    steps(40, 392, "DHW_TAP", [-3, -1, 1, 3])

    card(24, 448, 300, 330, "Alarms")
    rows = [("ALARM_SUM", "Common alarm (HS)", 700), ("TE2B_FAULT", "TE2B sensor fault", 400), ("TE1_FAULT", "TE1 sensor fault", 400),
            ("DHW_TEMP_ALM", "Hot water temperature", 400), ("TE2A_FAULT", "TE2A sensor fault", 400),
            ("HEAT_TEMP_ALM", "Heating supply temperature", 400), ("P1_FAULT", "P1 pump fault", 400), ("P2_FAULT", "P2 pump fault", 400)]
    for i, (var, text, weight) in enumerate(rows):
        lamp(42, 490 + i * 34, var)
        label(74, 489 + i * 34, text, size=14, weight=weight, color=INK)

    # ---- the two loops
    def loop(x0, title, sp, pv, pv_name, tv, tv_open, tv_pos, pump, st, trip, out_hot, out_cold, circulation):
        card(x0, 64, 456, 626, title)
        label(x0 + 24, 108, "Set value", size=14)
        val(x0 + 14, 130, sp, "°C", size=26, color=GREEN, w=90)
        label(x0 + 250, 108, pv_name, size=14)
        val(x0 + 240, 130, pv, "°C", size=26, w=90)

        ys, yr = 262, 420                                                       # supply and return pipe
        p.rect(oid("P"), x0 + 20, ys, 416, 7, fill=PIPE_HOT, line=PIPE_HOT, line_width=0)
        p.rect(oid("P"), x0 + 20, yr, 416, 7, fill=PIPE_COLD, line=PIPE_COLD, line_width=0)
        label(x0 + 20, ys - 66, "district heating supply", size=14)
        label(x0 + 20, yr + 14, "district heating return", size=14)
        label(x0 + 280, ys - 62, out_hot, size=14)
        label(x0 + 280, yr + 14, out_cold, size=14)

        p.valve(oid("C"), x0 + 100, ys + 3.5, D + tv_pos)                       # on the supply, before the exchanger
        label(x0 + 66, ys + 20, tv, w=40, size=15, weight=700, color=INK); val(x0 + 96, ys + 18, tv, "%", size=15, w=56)
        p.rect(oid("G"), x0 + 66, ys + 48, 112, 10, fill="#FFFFFFFF", line="#FFB8BCBF")
        p.rect(oid("G"), x0 + 67, ys + 49, 110, 8, fill=AMBER, line=AMBER, line_width=0, grow=(D + tv_pos, 0, 100))
        label(x0 + 66, ys + 62, "model position"); val(x0 + 56, ys + 80, tv_pos, "%", size=13, color=MUTED, w=46)

        p.rect(oid("E"), x0 + 196, ys - 36, 66, yr - ys + 80, fill="#FFE9EBEE", line=INK, line_width=2)   # heat exchanger
        p.line(oid("E"), x0 + 196, yr + 44, x0 + 262, ys - 36, color=INK, width=2)

        # pumps sit on the return side: P2 on the heating return, P1 on the return of the hot water circulation
        if circulation:
            yp = (ys + yr) // 2
            p.rect(oid("P"), x0 + 262, yp, 174, 7, fill="#FFE8853A", line="#FFE8853A", line_width=0)
            label(x0 + 280, yp - 50, "circulation return", size=14)
            ty = yp + 36
        else:
            yp, ty = yr, yr - 56
        px = x0 + 372 if circulation else x0 + 400
        p.pump(oid("M"), px, yp + 3.5, D + st, flow="left")                     # return flows towards the exchanger
        px -= 24
        label(px - 4, ty, pump[:2], w=30, size=15, weight=700, color=INK)
        for code, text, color in [(0, "STOP", MUTED), (1, "RUN", GREEN), (2, "FAULT", RED)]:
            p.text(oid("T"), px + 26, ty, 70, 23, text, size=15, weight=700, color=color, visible="%s%s = %d" % (D, st, code))

        p.rect(oid("K"), x0 + 16, 560, 424, 110, fill="#FFEFF3F6", line="#FFD5D9DD", radius=6)
        label(x0 + 30, 570, "%s motor protection (model)" % pump[:2], size=14, weight=700, color=INK)
        lamp(x0 + 32, 612, trip); label(x0 + 60, 611, "tripped", size=14, color=INK)
        p.button(oid("B"), x0 + 150, 604, 120, 36, "Trip", write=(D + trip, "TRUE"), size=15)
        p.button(oid("B"), x0 + 282, 604, 120, 36, "Reset", write=(D + trip, "FALSE"), size=15)

    loop(340, "TC1  Domestic hot water", "DHW_SP", "TE1", "TE1 hot water", "TV1", "TV1_OPEN", "TV1_POS", "P1_ON", "P1_ST", "P1_TRIP",
         "hot water", "cold water", True)
    loop(808, "TC2  Heating", "HEAT_SP", "TE2A", "TE2A supply", "TV2", "TV2_OPEN", "TV2_POS", "P2_ON", "P2_ST", "P2_TRIP",
         "heating supply", "heating return", False)
    return [p]
