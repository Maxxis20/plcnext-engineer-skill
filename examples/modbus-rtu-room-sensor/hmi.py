"""Operator page shaped like the room sensor: housing, screen, big temperature, CO2 stoplight. Light and dark look:
every text exists twice, one per look, shown by M.DARK; areas change their fill with it."""
from pxhmi import Page

D = "M."
GREEN, YELLOW, RED, BLUE = "#FF2FA84F", "#FFE0B020", "#FFD23B3B", "#FF4DA3E0"
#        page bg      housing      housing line  screen       ink          dim          rule
LOOK = {0: ("#FFE9ECEE", "#FFFFFFFF", "#FFCFD4D8", "#FFF7F8F9", "#FF1D2327", "#FF6B7378", "#FFD5DADD"),
        1: ("#FF0F1214", "#FF24292D", "#FF3A4248", "#FF15191C", "#FFF2F4F5", "#FF9AA3A9", "#FF3A4248")}


def pages():
    p = Page("Room", 1000, 640, fill=LOOK[1][0])

    def area(oid, x, y, w, h, k, **kw):                      # k = index into LOOK
        p.rect(oid, x, y, w, h, fill=LOOK[1][k], fill_by=(D + "DARK", [(0, LOOK[0][k]), (1, LOOK[1][k])]), **kw)

    def both(fn, oid, *a, tone=4, visible=None, **kw):       # one object per look; tone 4 = ink, 5 = dim, or a colour
        for look in (0, 1):
            cond = (D + "DARK") if look else ("NOT " + D + "DARK")
            if visible:
                cond = "%s AND (%s)" % (cond, visible)
            fn("%s_%d" % (oid, look), *a, color=LOOK[look][tone] if isinstance(tone, int) else tone, visible=cond, **kw)

    area("Bg", 0, 0, 1000, 640, 0, line_width=0)
    area("House", 40, 40, 480, 560, 1, line=LOOK[1][2], line_width=1, radius=28)
    area("Screen", 70, 70, 420, 500, 3, line=LOOK[1][2], line_width=1, radius=14)
    # CO2 stoplight: bar across the top of the screen
    p.rect("Light", 70, 70, 420, 14, fill=GREEN, line_width=0, fill_by=(D + "CO2_LEVEL", [(0, GREEN), (1, YELLOW), (2, RED)]))
    both(p.text, "Brand", 92, 98, 200, 20, "Room", size=13, tone=5)
    both(p.text, "Occ", 300, 96, 170, 22, "OCCUPIED", size=14, weight=700, tone=GREEN, align="Right", visible="NOT " + D + "UNOCC")
    both(p.text, "Unocc", 300, 96, 170, 22, "UNOCCUPIED", size=14, weight=700, tone=5, align="Right", visible=D + "UNOCC")
    # the big number
    both(p.value, "Temp", 110, 150, 250, 110, D + "TEMP", size=92, weight=700, align="Right")
    both(p.text, "TempU", 368, 168, 80, 40, "°C", size=30, tone=5)
    both(p.text, "NoComm", 110, 262, 340, 24, "no answer from the sensor", size=15, weight=700, tone=RED, align="Center",
         visible="NOT " + D + "COMM_OK")
    for i, (label, var, unit, fmt) in enumerate([("Humidity", "HUM", "%", "fixed1"), ("CO2", "CO2", "ppm", "fixed0"),
                                                 ("VOC", "VOC", "", "fixed1")]):
        x = 92 + i * 132
        both(p.text, "L" + var, x, 300, 120, 18, label, size=13, tone=5)
        both(p.value, "V" + var, x, 320, 84, 34, D + var, fmt=fmt, size=26, weight=700)
        both(p.text, "U" + var, x + 86, 330, 44, 20, unit, size=13, tone=5)
    area("Sep", 92, 378, 376, 1, 6, line_width=0)
    # setpoint
    both(p.text, "LSp", 92, 396, 160, 18, "Setpoint", size=13, tone=5)
    both(p.value, "VSp", 92, 418, 110, 44, D + "TSP", size=34, weight=700, tone=BLUE)
    both(p.text, "USp", 204, 432, 40, 22, "°C", size=15, tone=5)
    p.button("SpDn", 290, 414, 84, 50, "-", step=(D + "SP_REQ10", -5), size=26)
    p.button("SpUp", 384, 414, 84, 50, "+", step=(D + "SP_REQ10", 5), size=26)
    pend = D + "SP_REQ10 <> " + D + "SP_SHADOW10"
    both(p.text, "LPend", 92, 468, 60, 16, "sending", size=12, tone=YELLOW, visible=pend)
    both(p.value, "VPend", 150, 468, 60, 16, D + "SP_REQ", size=12, tone=YELLOW, visible=pend)
    p.button("BOcc", 92, 500, 182, 44, "Occupied", write=(D + "UNOCC_REQ", "FALSE"), size=15)
    p.button("BUnocc", 286, 500, 182, 44, "Unoccupied", write=(D + "UNOCC_REQ", "TRUE"), size=15)

    # beside the sensor: what its screen does not show
    x = 570
    both(p.text, "H1", x, 44, 280, 30, "Room sensor", size=22, weight=700)
    p.button("BLight", x + 250, 42, 64, 32, "Light", write=(D + "DARK", "FALSE"), size=13)
    p.button("BDark", x + 320, 42, 64, 32, "Dark", write=(D + "DARK", "TRUE"), size=13)
    both(p.text, "H2", x, 80, 400, 20, "Modbus RTU, address 1, 19200 baud, via AXL F RS UNI 1H", size=13, tone=5)
    rows = [("Dew point (calculated)", "DEW", "°C", "fixed1"), ("Humidity setpoint", "HSP", "%", "fixed1"),
            ("CO2 yellow from", "CO2_Y", "ppm", "fixed0"), ("CO2 red from", "CO2_R", "ppm", "fixed0")]
    for i, (label, var, unit, fmt) in enumerate(rows):
        y = 130 + i * 40
        both(p.text, "RL" + var, x, y, 210, 24, label, size=16)
        both(p.value, "RV" + var, x + 210, y, 90, 24, D + var, fmt=fmt, size=16, weight=700, align="Right")
        both(p.text, "RU" + var, x + 308, y, 60, 24, unit, size=14, tone=5)
    # fan speed 1..5: five steps, lit up to the present one
    both(p.text, "LFan", x, 290, 120, 24, "Fan speed", size=16)
    for n in range(1, 6):
        p.rect("Fan%d" % n, x + 128 + (n - 1) * 20, 290 + (5 - n) * 3, 14, 9 + n * 3, fill="#FF8A9399", line_width=0,
               fill_by=(D + "FAN", [(0, "#FF8A9399"), (n, BLUE)]))
    for n, name in enumerate(["Off", "Low", "Med", "High", "Auto"], start=1):
        both(p.text, "FanN%d" % n, x + 232, 290, 46, 24, name, size=15, weight=700, visible="%sFAN = %d" % (D, n))
    p.button("FanDn", x + 278, 282, 46, 36, "-", step=(D + "FAN_REQ", -1), size=20)
    p.button("FanUp", x + 330, 282, 46, 36, "+", step=(D + "FAN_REQ", 1), size=20)
    both(p.text, "H3", x, 344, 380, 24, "Communication", size=17, weight=700)
    p.ellipse("Lamp", x, 388, 18, 18, fill=RED, fill_by=(D + "COMM_OK", [(0, RED), (1, GREEN)]))
    both(p.text, "LampOk", x + 28, 386, 200, 22, "sensor answers", size=15, visible=D + "COMM_OK")
    both(p.text, "LampNo", x + 28, 386, 200, 22, "no answer", size=15, tone=RED, visible="NOT " + D + "COMM_OK")
    for i, (label, var) in enumerate([("answers", "N_OK"), ("writes", "N_WRITE"), ("errors", "N_ERR"), ("refused", "N_EXC")]):
        y = 424 + i * 30
        both(p.text, "CL" + var, x, y, 120, 22, label, size=14, tone=5)
        both(p.value, "CV" + var, x + 120, y, 110, 22, D + var, fmt=None, size=14, weight=700, align="Right")
    # values another controller writes into this one over OPC UA (0 until it does)
    both(p.text, "H4", x + 262, 424, 150, 22, "From OPC UA client", size=14, tone=5)
    both(p.value, "RmT", x + 262, 452, 60, 24, D + "REMOTE_TEMP", size=16, weight=700, align="Right")
    both(p.text, "RmTU", x + 328, 454, 40, 22, "°C", size=14, tone=5)
    both(p.value, "RmH", x + 262, 482, 60, 24, D + "REMOTE_HUM", size=16, weight=700, align="Right")
    both(p.text, "RmHU", x + 328, 484, 40, 22, "%", size=14, tone=5)
    both(p.value, "RmB", x + 262, 512, 60, 22, D + "REMOTE_BEAT", fmt=None, size=14, tone=5, align="Right")
    both(p.text, "RmBU", x + 328, 514, 60, 20, "beat", size=12, tone=5)
    both(p.text, "Foot", x, 556, 400, 18, "Setpoint, fan speed and occupancy can be changed here", size=12, tone=5)
    both(p.text, "Foot2", x, 574, 400, 18, "or on the sensor's own screen; the last change wins.", size=12, tone=5)
    return [p]
