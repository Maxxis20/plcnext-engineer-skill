"""Modbus TCP to Profinet on the device side: the three values, the Modbus and Profinet state, the controller's data."""
from pxhmi import Page

BG, CARD, LINE, INK, DIM = "#FF15191C", "#FF22282C", "#FF3A4248", "#FFF2F4F5", "#FF9AA3A9"
GREEN, RED, BLUE = "#FF2FA84F", "#FFD23B3B", "#FF4DA3E0"


def pages():
    p = Page("Device", 960, 520, fill=BG)
    p.text("Title", 40, 28, 700, 34, "Modbus TCP to Profinet", size=26, weight=700, color=INK)
    p.text("Sub", 40, 66, 860, 22, "three registers of a Modbus TCP server, sent to the Profinet controller", size=14, color=DIM)
    for oid, x, head in (("C1", 40, "From Modbus TCP"), ("C2", 500, "Profinet")):
        p.rect(oid, x, 110, 420, 370, fill=CARD, line=LINE, radius=10)
        p.text(oid + "H", x + 24, 128, 360, 26, head, size=18, weight=700, color=INK)
    p.ellipse("MbLamp", 64, 172, 16, 16, fill=RED, fill_by=("M.MB_STATE", [(0, RED), (1, GREEN), (2, RED)]))
    p.text("MbOk", 90, 168, 260, 24, "server answers", size=15, color=INK, visible="M.MB_STATE = 1")
    p.text("MbNo", 90, 168, 260, 24, "no answer", size=15, color=RED, visible="M.MB_STATE <> 1")
    rows = [("Temperature", "M.TEMP", "°C", "fixed1"), ("Humidity", "M.HUM", "%", "fixed1"), ("Battery", "M.VDD", "mV", None)]
    for i, (label, var, unit, fmt) in enumerate(rows):
        y = 214 + i * 56
        p.text("L%d" % i, 64, y + 6, 160, 26, label, size=16, color=DIM)
        p.value("V%d" % i, 230, y, 110, 38, var, fmt=fmt, size=28, weight=700, color=INK, align="Right")
        p.text("U%d" % i, 348, y + 8, 60, 26, unit, size=15, color=DIM)
    p.text("Off", 64, 400, 160, 22, "offline count", size=13, color=DIM)
    p.value("OffV", 230, 400, 110, 22, "M.MB_OFFLINE", fmt=None, size=13, color=DIM, align="Right")
    p.ellipse("PnLamp", 524, 172, 16, 16, fill=RED, fill_by=("M.PN_VALID", [(0, RED), (1, GREEN)]))
    p.text("PnOk", 550, 168, 330, 24, "controller exchanges data", size=15, color=INK, visible="M.PN_VALID")
    p.text("PnNo", 550, 168, 330, 24, "no controller", size=15, color=RED, visible="NOT M.PN_VALID")
    rows = [("our counter", "M.BEAT", None, ""), ("controller's counter", "M.FROM_A_CNT", None, ""),
            ("controller's room", "M.FROM_A_TEMP", "fixed1", "°C")]
    for i, (label, var, fmt, unit) in enumerate(rows):
        y = 214 + i * 56
        p.text("PL%d" % i, 524, y + 6, 200, 26, label, size=16, color=DIM)
        p.value("PV%d" % i, 730, y, 100, 38, var, fmt=fmt, size=28, weight=700, color=BLUE, align="Right")
        p.text("PU%d" % i, 838, y + 8, 50, 26, unit, size=15, color=DIM)
    p.text("Station", 524, 400, 380, 22, "station name plc-b, 16 bytes each way", size=13, color=DIM)
    return [p]
