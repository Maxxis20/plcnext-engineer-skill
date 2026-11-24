"""Modbus RTU probe: choose device, function and start address; see six registers raw and as floats."""
from pxhmi import Page

D = "M."
MUTED, GREEN, RED = "#FF6B7378", "#FF2FA84F", "#FFD23B3B"


def pages():
    p = Page("Probe", 1000, 600, fill="#FFF3F5F6")
    p.text("H", 40, 28, 600, 32, "Modbus RTU probe", size=24, weight=700)
    p.text("H2", 40, 62, 900, 20, "Reads 6 registers once a second through the serial module. Change the request until the "
           "device answers and the numbers make sense.", size=13, color=MUTED)
    for i, (label, var, steps) in enumerate([("Device address", "SLAVE", (-10, -1, 1, 10)), ("Function (3 holding, 4 input)", "FC", (-1, 1)),
                                             ("Start address", "START", (-100, -10, -1, 1, 10, 100))]):
        y = 110 + i * 52
        p.text("L" + var, 40, y + 6, 250, 24, label, size=16)
        p.value("V" + var, 290, y, 80, 34, D + var, fmt=None, size=24, weight=700, align="Right")
        for k, st in enumerate(steps):
            p.button("B%s%d" % (var, k), 400 + k * 76, y, 68, 36, ("+%d" if st > 0 else "%d") % st, step=(D + var, st), size=15)
    p.ellipse("Lamp", 40, 282, 18, 18, fill=RED, fill_by=(D + "ANSWERS", [(0, RED), (1, GREEN)]))
    p.text("LampOk", 68, 280, 200, 22, "device answers", size=15, visible=D + "ANSWERS")
    p.text("LampNo", 68, 280, 200, 22, "no answer", size=15, color=RED, visible="NOT " + D + "ANSWERS")
    for i, (label, var) in enumerate([("good", "N_OK"), ("no answer", "N_NOANSWER"), ("damaged", "N_BAD"), ("refused", "N_REFUSED"),
                                      ("exception code", "EXC")]):
        p.text("CL" + var, 290 + i * 135, 270, 125, 18, label, size=12, color=MUTED)
        p.value("CV" + var, 290 + i * 135, 288, 100, 24, D + var, fmt=None, size=17, weight=700)
    p.rect("Box", 40, 336, 920, 226, fill="#FFFFFFFF", radius=8)
    p.text("T1", 60, 350, 200, 20, "Register (start + n)", size=13, color=MUTED)
    p.text("T2", 60, 384, 200, 22, "Value 0..65535", size=15)
    p.text("T3", 60, 440, 220, 22, "Float, high word first", size=15)
    p.text("T4", 60, 496, 220, 22, "Float, low word first", size=15)
    for n in range(6):
        x = 290 + n * 110
        p.text("N%d" % n, x, 350, 90, 20, "+%d" % n, size=13, color=MUTED, align="Right")
        p.value("R%d" % n, x, 382, 90, 26, "%sR%d" % (D, n + 1), fmt=None, size=17, weight=700, align="Right")
    for n in range(3):
        x = 290 + n * 220
        p.value("HI%d" % n, x, 438, 200, 26, "%sHI%d" % (D, n + 1), fmt="fixed3", size=17, weight=700, align="Right")
        p.value("LO%d" % n, x, 494, 200, 26, "%sLO%d" % (D, n + 1), fmt="fixed3", size=17, weight=700, align="Right")
    return [p]
