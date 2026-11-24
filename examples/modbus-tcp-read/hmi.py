"""Modbus TCP read: the two values, the raw registers and the client's status items of the server."""
from pxhmi import Page

D = "M."
INK, MUTED, GREEN, RED = "#FF1D2327", "#FF6B7378", "#FF2FA84F", "#FFD23B3B"


def pages():
    p = Page("Modbus TCP", 800, 480, fill="#FFF3F5F6")
    p.text("H", 40, 28, 600, 32, "Modbus TCP server", size=24, weight=700, color=INK)
    p.text("H2", 40, 62, 700, 20, "Read by the controller's own Modbus TCP client, every cycle of the client.",
           size=13, color=MUTED)
    p.ellipse("Lamp", 40, 102, 18, 18, fill=RED, fill_by=(D + "MB_STATE", [(0, RED), (1, GREEN)]))
    p.text("LampOk", 68, 100, 250, 22, "connected, answers", size=15, color=INK, visible=D + "MB_STATE = 1")
    p.text("LampNo", 68, 100, 250, 22, "no connection", size=15, color=RED, visible="NOT (%sMB_STATE = 1)" % D)
    p.rect("Box", 40, 140, 720, 170, fill="#FFFFFFFF", radius=8)
    for i, (label, var, fmt) in enumerate([("Value (float, registers 0-1)", "VALUE", "fixed2"),
                                           ("Value (scaled, register 100)", "VALUE_S", "fixed1")]):
        y = 160 + i * 74
        p.text("L" + var, 60, y + 14, 300, 24, label, size=16, color=INK)
        p.value("V" + var, 380, y, 200, 50, D + var, fmt=fmt, size=36, weight=700, color=INK, align="Right")
    for i, (label, var) in enumerate([("register 0", "VALUE_HI"), ("register 1", "VALUE_LO"), ("register 100", "VALUE10"),
                                      ("connection lost", "MB_OFFLINE"), ("exceptions", "MB_EXC")]):
        x = 40 + i * 145
        p.text("CL" + var, x, 340, 135, 18, label, size=12, color=MUTED)
        p.value("CV" + var, x, 360, 120, 26, D + var, fmt=None, size=17, weight=700, color=INK)
    return [p]
