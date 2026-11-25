"""Operator page shaped like the room sensor: housing, screen, big temperature, CO2 stoplight. Light and dark look:
every text exists twice, one per look, shown by M.DARK; areas change their fill with it."""
from pxhmi import Page

D = "M."
GREEN, YELLOW, RED, BLUE = "#FF2FA84F", "#FFE0B020", "#FFD23B3B", "#FF4DA3E0"
#        page bg      housing      housing line  screen       ink          dim          rule
LOOK = {0: ("#FFE9ECEE", "#FFFFFFFF", "#FFCFD4D8", "#FFF7F8F9", "#FF1D2327", "#FF6B7378", "#FFD5DADD"),
        1: ("#FF0F1214", "#FF24292D", "#FF3A4248", "#FF15191C", "#FFF2F4F5", "#FF9AA3A9", "#FF3A4248")}


def room():
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
    # the values of B's Modbus TCP sensor, from device plc-b over Profinet
    both(p.text, "H4", x + 262, 424, 160, 22, "From plc-b (Profinet)", size=14, tone=5)
    p.ellipse("PnLamp", x + 262, 456, 14, 14, fill=RED, fill_by=(D + "B_ALIVE", [(0, RED), (1, GREEN)]))
    both(p.value, "PnT", x + 282, 450, 60, 24, D + "B_TEMP", size=16, weight=700, align="Right")
    both(p.text, "PnTU", x + 348, 452, 40, 22, "°C", size=14, tone=5)
    both(p.value, "PnH", x + 282, 480, 60, 24, D + "B_HUM", size=16, weight=700, align="Right")
    both(p.text, "PnHU", x + 348, 482, 40, 22, "%", size=14, tone=5)
    both(p.value, "PnB", x + 282, 510, 60, 22, D + "B_BEAT", fmt=None, size=14, tone=5, align="Right")
    both(p.text, "PnBU", x + 348, 512, 60, 20, "beat", size=12, tone=5)
    both(p.text, "Foot", x, 556, 400, 18, "Setpoint, fan speed and occupancy can be changed here", size=12, tone=5)
    both(p.text, "Foot2", x, 574, 400, 18, "or on the sensor's own screen; the last change wins.", size=12, tone=5)
    return p


# ---- pump start sequence: banner, step flow, pump, active step, interlock ladder (drive simulated at plc-b) ----
PAGE, CARD, LINE, INK, DIM, FAINT = "#FFEEF1F4", "#FFFFFFFF", "#FFD9DEE3", "#FF1E252B", "#FF66707A", "#FFB7BFC7"
SLATE, TEAL, TEAL_L, OK, OK_L, AMBER, AMBER_L, RED, RED_L = ("#FF263340", "#FF0F8B8D", "#FFD7EFEF", "#FF2E9E5B",
    "#FFE1F3E8", "#FFE09A1A", "#FFFBEFD8", "#FFD2453B", "#FFFBE3E1")
WHITE = "#FFFFFFFF"
UNK = "#FFE6E9ED"                                    # a row whose state is not known (no link)
STEPS = ["PRECHECK", "START DRIVE", "RUNNING", "STOP"]
REQS = {1: ["Profinet link to plc-b", "Safety chain closed", "Drive ready", "Drive not in Local", "Room temperature below limit"],
        2: ["No forced stop", "Drive accelerating", "Running feedback"],
        3: ["No forced stop", "Running feedback"],
        4: ["Running feedback off", "Speed zero"]}
TMAX = {1: 15, 2: 10, 3: 3, 4: 15}
FS_TEXT = {11: "Profinet link to plc-b lost", 12: "Safety chain open", 13: "Drive fault"}


def card(p, oid, x, y, w, h, title):
    p.rect(oid, x, y, w, h, fill=CARD, line=LINE, radius=12)
    p.text(oid + "T", x + 18, y + 12, w - 36, 22, title.upper(), size=12, weight=700, color=DIM)


def segmented(p, oid, x, y, w, var, names):
    """Two-way switch: both halves are buttons; the active half is covered dark with white text."""
    bw = w / len(names)
    for i, name in enumerate(names):
        bx = x + i * bw
        p.button("%s_b%d" % (oid, i), bx, y, bw, 32, name, write=(var, str(i)), size=14)
        on = "%s = %d" % (var, i)
        p.rect("%s_a%d" % (oid, i), bx, y, bw, 32, fill=SLATE, line=SLATE, radius=0, visible=on)
        p.text("%s_t%d" % (oid, i), bx, y + 7, bw, 20, name, size=14, weight=700, color=WHITE, align="Center", visible=on)


def pump():
    p = Page("Pump", 1280, 720, fill=PAGE)

    # -- banner: what the unit is doing, in one line, coloured by the state --
    p.rect("Ban", 0, 0, 1280, 76, fill=SLATE, line_width=0,
           fill_by=(D + "SQ_STATE", [(0, SLATE), (1, SLATE), (2, "#FF6A4E12"), (3, "#FF8E2A22"), (4, SLATE)]))
    p.text("BanTag", 28, 12, 120, 30, "P1", size=26, weight=700, color=WHITE)
    p.text("BanSub", 28, 44, 260, 20, "Circulation pump · drive at plc-b", size=12, color="#FFB9C4CE")
    big = [("SQ_STATE = 0 AND %sIL_ACTIVE = 0" % D, "Ready to start"),
           ("SQ_STATE = 0 AND %sIL_ACTIVE > 0" % D, "Not ready: interlock open"),
           ("SQ_STATE = 1 AND %sSQ_STEP < 3" % D, "Starting"),
           ("SQ_STATE = 1 AND %sSQ_STEP = 3" % D, "Running"),
           ("SQ_STATE = 2", "Held: manual control"),
           ("SQ_STATE = 4", "Stopping")]
    for k, (cond, txt) in enumerate(big):
        p.text("BanS%d" % k, 300, 18, 420, 40, txt, size=26, weight=700, color=WHITE, visible=D + cond)
    for s, reqs in REQS.items():
        for i, txt in enumerate(reqs, start=1):
            p.text("BanA%d_%d" % (s, i), 300, 14, 640, 48, "Alarm · %s: %s not met in %d s" % (STEPS[s - 1].title(), txt.lower(), TMAX[s]),
                   size=20, weight=700, color=WHITE, visible="%sSQ_ALARM AND %sAL_STEP = %d AND %sAL_REQ = %d" % (D, D, s, D, i))
    for code, txt in FS_TEXT.items():
        p.text("BanF%d" % code, 300, 18, 640, 40, "Forced stop · " + txt, size=24, weight=700, color=WHITE,
               visible="%sSQ_ALARM AND %sAL_REQ = %d" % (D, D, code))
    p.text("BanSpL", 990, 14, 100, 16, "SPEED", size=11, weight=700, color="#FFB9C4CE")
    p.value("BanSp", 970, 30, 110, 36, D + "ACT_RPM", fmt="fixed0", size=30, weight=700, color=WHITE, align="Right")
    p.text("BanSpU", 1084, 42, 40, 20, "rpm", size=15, color="#FFB9C4CE")
    p.text("BanTL", 1160, 14, 100, 16, "STEP TIME", size=11, weight=700, color="#FFB9C4CE")
    p.value("BanT", 1160, 34, 90, 30, D + "SQ_T", size=22, weight=700, color=WHITE)
    ring_warning(p)

    # -- the steps as a flow: done (green), active (teal), ahead (outline); red when the alarm is in it --
    card(p, "Flow", 24, 92, 1232, 116, "Start sequence")
    p.button("GoNet", 810, 100, 110, 32, "Network  ›", size=14, page="Network")
    p.button("GoTrends", 930, 100, 110, 32, "Trends  ›", size=14, page="Trends")
    segmented(p, "Sm", 1056, 100, 184, D + "SQ_MODE", ["Auto", "Manual"])
    cw, gap, fx = 260, 46, 48
    for n, name in enumerate(STEPS, start=1):
        cx = fx + (n - 1) * (cw + gap)
        rel = "%sSQ_STEP - %d" % (D, n)
        if n > 1:
            p.rect("Link%d" % n, cx - gap, 160, gap, 4, fill=LINE, line_width=0,
                   fill_by=("%sSQ_STEP - %d" % (D, n - 1), [(-9, LINE), (1, OK)]))
        p.rect("Chip%d" % n, cx, 136, cw, 52, fill=CARD, line=FAINT, line_width=1.5, radius=26,
               fill_by=(rel, [(-9, CARD), (0, TEAL), (1, OK_L)]))
        p.rect("ChipA%d" % n, cx, 136, cw, 52, fill=RED, line=RED, radius=26, visible="%sSQ_ALARM AND %sSQ_STEP = %d" % (D, D, n))
        p.ellipse("Num%d" % n, cx + 10, 144, 36, 36, fill=PAGE, line=FAINT)
        p.text("NumT%d" % n, cx + 10, 151, 36, 22, str(n), size=15, weight=700, color=INK, align="Center", visible="%sSQ_STEP <= %d OR %sSQ_STEP = 0" % (D, n, D))
        p.text("NumOk%d" % n, cx + 10, 150, 36, 24, "✓", size=18, weight=700, color=OK, align="Center",
               visible="%sSQ_STEP > %d" % (D, n))
        p.text("ChipT%d" % n, cx + 56, 145, cw - 66, 20, name, size=15, weight=700, color=INK, visible="NOT (%sSQ_STEP = %d)" % (D, n))
        p.text("ChipTa%d" % n, cx + 56, 145, cw - 66, 20, name, size=15, weight=700, color=WHITE, visible="%sSQ_STEP = %d" % (D, n))
        p.value("ChipS%d" % n, cx + 56, 165, 80, 18, D + "SQ_T", size=12, color=WHITE, visible="%sSQ_STEP = %d" % (D, n))
        p.text("ChipSu%d" % n, cx + 100, 165, 20, 18, "s", size=12, color=WHITE, visible="%sSQ_STEP = %d" % (D, n))
        # Manual: pick a step to jump to
        p.button("Pick%d" % n, cx + cw - 100, 144, 60, 36, "Go", write=(D + "SQ_SEL", str(n)), size=13)
        p.rect("PickSel%d" % n, cx + cw - 100, 144, 60, 36, fill="#00FFFFFF", line=TEAL, line_width=3,
               visible="%sSQ_SEL = %d" % (D, n))
        p.rect("PickHide%d" % n, cx + cw - 102, 141, 64, 42, fill="#FFFFFFFF", line_width=0,
               fill_by=(rel, [(-9, CARD), (0, TEAL), (1, OK_L)]), visible="%sSQ_MODE <> 1" % D)
        p.rect("PickHideA%d" % n, cx + cw - 102, 141, 64, 42, fill=RED, line_width=0,
               visible="%sSQ_MODE <> 1 AND %sSQ_ALARM AND %sSQ_STEP = %d" % (D, D, D, n))

    # -- pump --
    card(p, "Pm", 24, 224, 380, 472, "Drive")
    segmented(p, "Dm", 200, 232, 188, D + "DRV_MODE_REQ", ["Auto", "Manual"])
    p.rect("LocalOn", 200, 232, 188, 32, fill=AMBER, line=AMBER, visible=D + "DRV_MODE = 2")
    p.text("LocalT", 200, 239, 188, 20, "LOCAL at the drive", size=13, weight=700, color=WHITE, align="Center", visible=D + "DRV_MODE = 2")
    p.ellipse("Halo", 64, 290, 120, 120, fill=PAGE, line_width=0,
              fill_by=(D + "DRV_STATE", [(0, PAGE), (1, OK_L), (2, RED_L), (3, AMBER_L)]))
    p.pump("Pmp", 124, 350, D + "DRV_STATE", r=44, flow="right",
           colors=[(0, "#FF8592A0"), (1, OK), (2, RED), (3, AMBER)])
    for st, txt, col in [(0, "Stopped", DIM), (1, "Running", OK), (2, "Fault", RED), (3, "Changing speed", AMBER)]:
        p.text("DsT%d" % st, 200, 316, 190, 28, txt, size=20, weight=700, color=col, visible="%sDRV_STATE = %d" % (D, st))
    p.value("PmBig", 180, 346, 120, 50, D + "ACT_RPM", fmt="fixed0", size=40, weight=700, color=INK, align="Right")
    p.text("PmBigU", 304, 368, 50, 24, "rpm", size=18, color=DIM)
    # speed: actual as a thick bar, setpoint as a thin one under it
    p.rect("SpdBg", 48, 440, 332, 18, fill=PAGE, line_width=0, radius=9)
    p.rect("Spd", 48, 440, 332, 18, fill=TEAL, line_width=0, radius=9, grow=(D + "SPEED_ACT", 0, 1000))
    p.rect("SpsBg", 48, 464, 332, 4, fill=PAGE, line_width=0)
    p.rect("Sps", 48, 464, 332, 4, fill=SLATE, line_width=0, grow=(D + "SPEED_OUT", 0, 1000))
    for v in (0, 50, 100):
        p.text("SpdT%d" % v, 48 + 332 * v / 100 - 24, 472, 48, 16, "%d" % (1450 * v // 100), size=11, color=DIM, align="Center")
    p.text("SpsL", 48, 494, 120, 18, "setpoint", size=12, color=DIM)
    p.value("SpsV", 104, 492, 60, 20, D + "OUT_RPM", fmt="fixed0", size=14, weight=700, color=INK)
    p.text("SpsU", 168, 494, 30, 18, "rpm", size=12, color=DIM)
    # manual
    p.rect("ManBox", 40, 528, 348, 152, fill=PAGE, line_width=0, radius=10)
    p.text("ManH", 56, 538, 200, 18, "MANUAL CONTROL", size=11, weight=700, color=DIM)
    p.value("ManV", 56, 562, 90, 36, D + "MAN_RPM", fmt=None, size=28, weight=700, color=INK)
    p.text("ManU", 150, 576, 40, 20, "rpm", size=14, color=DIM)
    p.button("ManDn", 260, 562, 56, 36, "−", step=(D + "MAN_RPM", -50), size=20)
    p.button("ManUp", 322, 562, 56, 36, "+", step=(D + "MAN_RPM", 50), size=20)
    p.button("BStart", 56, 618, 154, 48, "Start", write=(D + "MAN_RUN", "TRUE"), size=17)
    p.button("BStop", 220, 618, 158, 48, "Stop", write=(D + "MAN_RUN", "FALSE"), size=17)
    p.rect("ManVeil", 40, 528, 348, 152, fill="#C8EEF1F4", line_width=0, radius=10, visible="%sDRV_MODE <> 1" % D)
    p.text("ManVeilT", 40, 594, 348, 20, "switch the drive to Manual", size=13, color=DIM, align="Center", visible="%sDRV_MODE <> 1" % D)

    # -- the active step: its checklist, settle and supervision --
    card(p, "St", 420, 224, 440, 472, "Active step")
    for n, name in enumerate(STEPS, start=1):
        p.text("StN%d" % n, 438, 248, 400, 30, "%d · %s" % (n, name.title()), size=22, weight=700, color=INK,
               visible="%sSQ_STEP = %d" % (D, n))
    p.text("StIdle", 438, 248, 400, 30, "Idle", size=22, weight=700, color=INK, visible="%sSQ_STEP = 0" % D)
    p.text("StIdle2", 438, 284, 400, 40, "Start runs the checks below one by one; each step waits its settle time once all are met.",
           size=13, color=DIM, visible="%sSQ_STEP = 0" % D)
    for i in range(1, 6):
        ry = 290 + (i - 1) * 40
        on = "%sSQ_N >= %d" % (D, i)
        p.rect("RqBg%d" % i, 436, ry, 408, 34, fill=CARD, line=LINE, radius=8, visible=on,
               fill_by=("%sRQ_AT - %d" % (D, i), [(-9, CARD), (0, AMBER_L), (1, OK_L)]))
        for s, reqs in REQS.items():
            if i <= len(reqs):
                p.text("Rq%d_%d" % (s, i), 450, ry + 7, 280, 20, reqs[i - 1], size=14, color=INK, visible="%sSQ_STEP = %d" % (D, s))
        p.text("RqOk%d" % i, 760, ry + 8, 76, 18, "OK", size=12, weight=700, color=OK, align="Right",
               visible="%s AND %sRQ_AT > %d" % (on, D, i))
        p.text("RqAt%d" % i, 740, ry + 8, 96, 18, "CHECKING", size=12, weight=700, color="#FFA56A00", align="Right",
               visible="%s AND %sRQ_AT = %d" % (on, D, i))
        p.text("RqNo%d" % i, 760, ry + 8, 76, 18, "next", size=12, color=FAINT, align="Right",
               visible="%s AND %sRQ_AT < %d" % (on, D, i))
    for k, (lab, pct, now, of, col) in enumerate([("Settle", "SETTLE_PCT", "SETTLE_T", "SETTLE", TEAL),
                                                   ("Supervision", "SUP_PCT", "SUP_T", "TMAX", AMBER)]):
        by = 500 + k * 44
        p.text("PbL%d" % k, 438, by, 120, 18, lab.upper(), size=11, weight=700, color=DIM)
        p.value("PbV%d" % k, 690, by - 2, 60, 18, D + now, size=13, weight=700, color=INK, align="Right")
        p.text("PbS%d" % k, 752, by, 14, 18, "/", size=12, color=DIM)
        p.value("PbM%d" % k, 764, by - 2, 50, 18, D + of, size=13, color=DIM)
        p.text("PbU%d" % k, 812, by, 30, 18, "s", size=12, color=DIM)
        p.rect("PbBg%d" % k, 438, by + 20, 404, 8, fill=PAGE, line_width=0, radius=4)
        p.rect("Pb%d" % k, 438, by + 20, 404, 8, fill=col, line_width=0, radius=4, grow=(D + pct, 0, 100))
    p.button("SStart", 436, 600, 130, 40, "Start", write=(D + "SQ_CMD", "1"), size=15)
    p.button("SStop", 574, 600, 130, 40, "Stop", write=(D + "SQ_CMD", "2"), size=15)
    p.button("SCont", 712, 600, 130, 40, "Continue", write=(D + "SQ_CMD", "3"), size=15)
    p.button("BNext", 436, 646, 130, 40, "Next step", write=(D + "SQ_CMD", "4"), size=14)
    p.button("BSel", 574, 646, 130, 40, "Go to chosen", write=(D + "SQ_CMD", "5"), size=14)
    p.rect("ExVeil", 434, 644, 274, 44, fill="#C8FFFFFF", line_width=0, visible="%sSQ_MODE <> 1" % D)
    p.button("BRst", 712, 646, 130, 40, "Reset", write=(D + "SQ_CMD", "6"), size=15)

    # -- interlocks as a ladder: rail, a contact per condition, the coil at the end --
    card(p, "Il", 876, 224, 380, 472, "Interlocks")
    p.value("IlN", 1170, 234, 30, 20, D + "IL_ACTIVE", fmt=None, size=13, weight=700, color=RED, align="Right", visible="%sIL_ACTIVE > 0" % D)
    p.text("IlNt", 1204, 236, 50, 20, "open", size=12, color=RED, visible="%sIL_ACTIVE > 0" % D)
    p.text("IlOk", 1150, 236, 96, 20, "all closed", size=12, color=OK, align="Right", visible="%sIL_ACTIVE = 0" % D)

    def rung(gid, gy, title, rows, coil, unknown=()):
        p.text(gid + "H", 896, gy, 300, 20, title, size=14, weight=700, color=INK)
        top, bot = gy + 30, gy + 30 + len(rows) * 40
        p.rect(gid + "Rail", 896, top, 3, bot - top - 8, fill=SLATE, line_width=0)
        for i, (txt, var) in enumerate(rows):
            ry = top + i * 40
            p.rect("%sRow%d" % (gid, i), 906, ry, 250, 32, fill=CARD, line_width=0, radius=6,
                   fill_by=(D + var, [(0, RED_L), (1, CARD)]))
            p.rect("%sW%d" % (gid, i), 899, ry + 15, 12, 2, fill=SLATE, line_width=0)
            p.rect("%sCa%d" % (gid, i), 911, ry + 6, 3, 20, fill=SLATE, line_width=0)
            p.rect("%sCb%d" % (gid, i), 925, ry + 6, 3, 20, fill=SLATE, line_width=0)
            p.rect("%sCc%d" % (gid, i), 913, ry + 14, 13, 4, fill=OK, line_width=0, visible=D + var)
            p.rect("%sCo%d" % (gid, i), 913, ry + 8, 13, 16, fill="#00FFFFFF", line=RED, line_width=1.5, visible="NOT " + D + var)
            p.text("%sT%d" % (gid, i), 938, ry + 7, 214, 20, txt, size=13, color=INK)
            if var in unknown:                       # no link to plc-b: B's bits are not known
                p.rect("%sU%d" % (gid, i), 906, ry, 250, 32, fill=UNK, line_width=0, radius=6, visible=D + "B_UNK")
                p.text("%sUq%d" % (gid, i), 912, ry + 6, 20, 20, "?", size=15, weight=700, color=DIM, align="Center", visible=D + "B_UNK")
                p.text("%sUt%d" % (gid, i), 938, ry + 7, 214, 20, txt + " · unknown", size=13, color=DIM, visible=D + "B_UNK")
        cy = top + (len(rows) * 40 - 8) / 2
        p.rect(gid + "Bus", 1160, cy + 14, 30, 2, fill=SLATE, line_width=0)
        p.ellipse(gid + "Coil", 1190, cy, 30, 30, fill=RED, line=SLATE, line_width=2, fill_by=(D + coil, [(0, RED), (1, OK)]))
        p.text(gid + "CoilT", 1166, cy + 34, 80, 16, coil, size=10, color=DIM, align="Center")
        p.rect(gid + "Bar", 1156, top, 3, bot - top - 8, fill=SLATE, line_width=0)

    rung("Fs", 262, "Forced stop", [("Profinet link to plc-b", "IL_PN"), ("Safety chain closed", "IL_SIS"),
                                     ("Drive without fault", "IL_DRVF")], "FS_OK", unknown=("IL_SIS", "IL_DRVF"))
    rung("Sp", 430, "Start permissive", [("No forced stop", "FS_OK"), ("Drive ready", "IL_RDY"), ("Drive not in Local", "IL_REM"),
                                          ("Room temperature below limit", "IL_TEMP")], "PERM_OK",
         unknown=("IL_RDY", "IL_REM"))
    p.text("TmL", 896, 640, 60, 18, "ROOM", size=11, weight=700, color=DIM)
    p.value("TmV", 896, 656, 64, 26, D + "TEMP", size=18, weight=700, color=INK)
    p.text("TmL2", 974, 640, 60, 18, "LIMIT", size=11, weight=700, color=DIM)
    p.value("TmX", 974, 656, 64, 26, D + "TEMP_MAX", size=18, weight=700, color=INK)
    p.text("TmU", 1036, 662, 30, 18, "°C", size=12, color=DIM)
    p.button("TmDn", 1124, 648, 56, 36, "−", step=(D + "TEMP_MAX10", -5), size=18)
    p.button("TmUp", 1186, 648, 56, 36, "+", step=(D + "TEMP_MAX10", 5), size=18)
    return p


def trends():
    """Two charts over the DataLogger sessions Speed and Room (program.json "datalogger"), 1 s samples, the last
    15 minutes (Raw mode: 900 samples per pen, the limit is 1000)."""
    p = Page("Trends", 1280, 720, fill=PAGE)
    p.rect("Ban", 0, 0, 1280, 76, fill=SLATE, line_width=0)
    p.text("BanTag", 28, 12, 120, 30, "P1", size=26, weight=700, color=WHITE)
    p.text("BanSub", 28, 44, 260, 20, "Circulation pump · drive at plc-b", size=12, color="#FFB9C4CE")
    p.text("BanT", 300, 18, 500, 40, "Trends · last 15 minutes", size=26, weight=700, color=WHITE)
    p.button("GoPump", 736, 20, 120, 36, "‹  Pump", size=15, page="Pump")
    p.button("GoNet", 868, 20, 120, 36, "Network", size=15, page="Network")
    p.button("GoHist", 1000, 20, 120, 36, "History", size=15, page="History")
    p.button("GoRoom", 1132, 20, 120, 36, "Room", size=15, page="Room")
    for oid, y, title, session, pens, axis, live in [
            ("Sp", 92, "Pump speed · setpoint and actual, rpm", "Speed",
             [("M.P1_SP_RPM", SLATE, "Left"), ("M.P1_ACT_RPM", TEAL, "Left")], (0, 1500),
             [("setpoint", "OUT_RPM", "rpm"), ("actual", "ACT_RPM", "rpm")]),
            ("Tm", 408, "Room temperature and start limit, °C", "Room",
             [("M.TR_TEMP", AMBER, "Left"), ("M.TR_TEMP_MAX", RED, "Left")], (0, 0),
             [("room", "TEMP", "°C"), ("limit", "TEMP_MAX", "°C")])]:
        card(p, oid, 24, y, 1232, 300, title)
        for k, (lab, var, unit) in enumerate(live):
            x = 900 + k * 180
            p.text("%sL%d" % (oid, k), x, y + 14, 70, 18, lab, size=12, color=DIM, align="Right")
            p.value("%sV%d" % (oid, k), x + 74, y + 10, 60, 24, D + var, size=16, weight=700, color=INK, align="Right")
            p.text("%sU%d" % (oid, k), x + 138, y + 14, 30, 18, unit, size=12, color=DIM)
        p.chart(oid + "Ch", 40, y + 42, 1200, 246, session, pens, minutes=15, sampling_ms=1000, left=axis)
    return p


def history():
    """Read back from ClickHouse (FB_CH's query, every 60 s): the average speed of each of the last 24 minutes.
    Display only: the sequence never uses it. Also the state of the link that stores the samples."""
    p = Page("History", 1280, 720, fill=PAGE)
    p.rect("Ban", 0, 0, 1280, 76, fill=SLATE, line_width=0)
    p.text("BanTag", 28, 12, 120, 30, "P1", size=26, weight=700, color=WHITE)
    p.text("BanSub", 28, 44, 260, 20, "Circulation pump · drive at plc-b", size=12, color="#FFB9C4CE")
    p.text("BanT", 300, 18, 560, 40, "History · from ClickHouse", size=26, weight=700, color=WHITE)
    p.button("GoPump", 1000, 20, 120, 36, "‹  Pump", size=15, page="Pump")
    p.button("GoTr", 1132, 20, 120, 36, "Trends", size=15, page="Trends")
    card(p, "Hs", 24, 92, 1232, 420, "Average speed per minute, last 24 minutes (read back from the database)")
    x0, y0, bw, gap, bh = 80, 140, 40, 8, 300
    for v in (0, 500, 1000, 1500):
        y = y0 + bh - bh * v / 1500
        p.rect("Grid%d" % v, x0 - 8, y, 24 * (bw + gap) + 8, 1, fill=LINE, line_width=0)
        p.text("GridT%d" % v, 36, y - 9, 36, 18, "%d" % v, size=11, color=DIM, align="Right")
    for i in range(1, 25):
        x = x0 + (i - 1) * (bw + gap)
        p.rect("Hb%d" % i, x, y0, bw, bh, fill=TEAL, line_width=0, grow=(D + "H%02d" % i, 0, 1500), axis="y")
        if i in (1, 5, 9, 13, 17, 21, 24):           # wall-clock time of the minute, from the database
            p.value("Hl%d" % i, x - 12, y0 + bh + 8, bw + 24, 16, D + "L%02d" % i, fmt=None, size=11, color=DIM, align="Center")
    p.text("HsU", 36, y0 - 22, 36, 14, "rpm", size=11, color=DIM, align="Right")
    p.text("HsQ", 80, 486, 220, 18, "last answer, s ago", size=12, color=DIM)
    p.value("HsQV", 220, 484, 80, 20, D + "CH_QAGE", fmt="fixed0", size=14, weight=700, color=INK, align="Right")
    p.text("HsN", 330, 486, 120, 18, "values", size=12, color=DIM)
    p.value("HsNV", 380, 484, 40, 20, D + "CH_QN", fmt=None, size=14, weight=700, color=INK, align="Right")
    card(p, "Lk", 24, 528, 1232, 168, "Storing samples (1 s, sent every 10 s over HTTP)")
    rows = [("rows stored", "CH_ROWS", None), ("batch age, s", "CH_AGE", "fixed0"), ("waiting samples", "CH_PEND", None),
            ("errors", "CH_ERR", None), ("dropped rows", "CH_DROP", None), ("last HTTP code", "CH_CODE", None)]
    for k, (lab, var, fmt) in enumerate(rows):
        x = 48 + k * 200
        p.text("LkL%d" % k, x, 570, 190, 18, lab.upper(), size=11, weight=700, color=DIM)
        p.value("LkV%d" % k, x, 592, 180, 40, D + var, fmt=fmt, size=30, weight=700, color=INK)
    p.ellipse("LkLamp", 48, 652, 16, 16, fill=RED, line_width=0,
              fill_by=("%sCH_AGE < 30.0" % D, [(0, RED), (1, OK)]))
    p.text("LkOk", 72, 650, 400, 20, "database link OK", size=14, color=OK, visible="%sCH_AGE < 30.0" % D)
    p.text("LkNo", 72, 650, 600, 20, "no batch stored for 30 s: plant unaffected, samples wait (60 s at most)", size=14,
           color=RED, visible="%sCH_AGE >= 30.0" % D)
    return p


def ring_warning(p, ban_fill=True):
    """The MRP warning at the banner's left end: amber, not a forced stop. Latched in the program until Ack
    (RING_WS 1 open, 2 closed again but not acknowledged, 3 open and acknowledged). A button cannot be hidden: while
    there is nothing to acknowledge a rect in the banner's colour covers it."""
    ws = D + "RING_WS"
    p.rect("RwPill", 16, 8, 280, 60, fill=AMBER, line_width=0, radius=10, visible=ws + " > 0",
           fill_by=(ws, [(0, AMBER), (3, "#FFB07A10")]))
    p.text("RwT1", 30, 14, 190, 24, "Ring open", size=18, weight=700, color=SLATE, visible=ws + " = 1")
    p.text("RwS1", 30, 40, 190, 18, "network warning · pump runs on", size=11, color=SLATE, visible=ws + " = 1")
    p.text("RwT2", 30, 14, 190, 24, "Ring was open", size=18, weight=700, color=SLATE, visible=ws + " = 2")
    p.text("RwS2", 30, 40, 190, 18, "closed again · acknowledge", size=11, color=SLATE, visible=ws + " = 2")
    p.text("RwT3", 30, 14, 190, 24, "Ring open", size=18, weight=700, color=WHITE, visible=ws + " = 3")
    p.text("RwS3", 30, 40, 190, 18, "acknowledged · until closed", size=11, color=WHITE, visible=ws + " = 3")
    p.button("RwAck", 222, 20, 62, 36, "Ack", write=(D + "RING_ACK", "TRUE"), size=14)    # over the pill
    # over the Ack button while there is nothing to acknowledge
    cover = [(0, SLATE), (1, SLATE), (2, "#FF6A4E12"), (3, "#FF8E2A22"), (4, SLATE)] if ban_fill else [(0, SLATE)]
    p.rect("RwHide", 220, 18, 66, 40, fill=SLATE, line_width=0, visible="%s = 0" % ws,
           fill_by=(D + "SQ_STATE", cover) if ban_fill else None)
    p.rect("RwHide3", 220, 18, 66, 40, fill="#FFB07A10", line_width=0, visible="%s = 3" % ws)


DIAG = [  # (ChannelErrorType, ExtChannelErrorType or None, text): Profinet standard, and the XC216's GSDML (0x0100..)
    (0x8000, None, "Data transmission impossible (link down)"), (0x8001, None, "Remote mismatch (neighbour)"),
    (0x8002, 0x8001, "Media redundancy: ring open"), (0x8002, 0x8000, "Media redundancy: manager role failed"),
    (0x8002, 0x8003, "Media redundancy: several managers"), (0x8002, None, "Media redundancy mismatch"),
    (0x8003, None, "Sync mismatch"), (0x8005, None, "Time mismatch"),
    (0x0100, None, "Illegal link up"), (0x0101, None, "Illegal link down"),
    (0x0200, None, "No redundant power supply (L2)"), (0x0201, None, "C-PLUG not available"),
    (0x0202, None, "C-PLUG defective"), (0x0203, None, "Wrong C-PLUG"),
    (0x0205, None, "MRP setting cannot be applied"), (0x0206, None, "MRP setting cannot be applied"),
    (0x0300, None, "Wrong loop detection configuration"), (0x0301, None, "Loop detected"),
    (0x0400, None, "Wrong port mirroring configuration"), (0x0401, None, "Port mirroring enabled"),
    (0x0600, None, "Configuration cannot be applied"), (0x0010, None, "Parameterization fault")]


def network():
    """Profinet diagnosis of A's three devices (B, XC216, the Pi pnpi) and the MRP ring (XC216 manager; ring state from record 0x802A of its two ring ports, read by RDREC)."""
    p = Page("Network", 1280, 720, fill=PAGE)
    p.rect("Ban", 0, 0, 1280, 76, fill=SLATE, line_width=0)
    p.text("BanTag", 28, 12, 120, 30, "P1", size=26, weight=700, color=WHITE)
    p.text("BanSub", 28, 44, 260, 20, "Circulation pump · drive at plc-b", size=12, color="#FFB9C4CE")
    p.text("BanT", 320, 18, 560, 40, "Network · Profinet and MRP ring", size=26, weight=700, color=WHITE)
    p.button("GoPump", 1000, 20, 120, 36, "‹  Pump", size=15, page="Pump")
    p.button("GoTr", 1132, 20, 120, 36, "Trends", size=15, page="Trends")
    ring_warning(p, ban_fill=False)
    rs = D + "RING_STATE"

    # -- the ring: A - B - XC216 in a row, the third cable back underneath --
    card(p, "Rg", 24, 92, 800, 330, "MRP ring · manager XC216, domain default")
    def seg(n):                                       # SEGn: 1 good, 0 broken, -1 unknown
        return (D + "SEG%d" % n, [(-9, FAINT), (0, AMBER), (1, OK)])
    p.rect("Wr2", 236, 186, 100, 8, fill=OK, line_width=0, fill_by=seg(2))              # A port 2 - B port 1
    p.rect("Wr3", 496, 186, 100, 8, fill=OK, line_width=0, fill_by=seg(3))              # B port 2 - XC216 P2
    p.rect("Wr1a", 652, 226, 8, 70, fill=OK, line_width=0, fill_by=seg(1))              # XC216 P1 - A port 1
    p.rect("Wr1b", 152, 288, 508, 8, fill=OK, line_width=0, fill_by=seg(1))
    p.rect("Wr1c", 152, 226, 8, 70, fill=OK, line_width=0, fill_by=seg(1))
    for n, x, y in [(1, 392, 278), (2, 274, 176), (3, 534, 176)]:   # a cross on a broken cable
        p.text("WrX%d" % n, x, y, 24, 28, "✕", size=22, weight=700, color=RED, align="Center", visible="%sSEG%d = 0" % (D, n))
    # the manager's ring ports: it blocks one while the ring is closed
    for n, port, y in [(1, "P1 · cable 1", 240), (2, "P2 · cable 3", 260)]:
        st, lk = D + "XP%d_ST" % n, D + "XP%d_LINK" % n
        p.text("Pt%d" % n, 672, y, 80, 18, port, size=11, color=DIM)
        for k, (cond, txt, col) in enumerate([("%s AND %s = 2" % (lk, st), "blocked", INK),
                                              ("%s AND %s = 5" % (lk, st), "forwarding", INK), ("NOT " + lk, "no link", AMBER)]):
            p.text("Pt%dS%d" % (n, k), 744, y, 76, 18, txt, size=11, weight=700, color=col, visible=cond)
    for oid, x, name, sub, ar in [("NA", 76, "A", "controller · .10", None), ("NB", 336, "B · plc-b", "device · .11", "NB_AR"),
                                  ("NX", 596, "XC216", "manager · .20", "NX_AR")]:
        kw = {"fill_by": (D + ar, [(0, RED_L), (1, CARD)])} if ar else {}
        p.rect(oid, x, 156, 160, 70, fill=CARD, line=SLATE, line_width=2, radius=10, **kw)
        p.text(oid + "T", x + 14, 166, 140, 24, name, size=17, weight=700, color=INK)
        p.text(oid + "S", x + 14, 194, 140, 18, sub, size=12, color=DIM)
        if ar:
            p.ellipse(oid + "L", x + 134, 168, 14, 14, fill=OK, line_width=0, fill_by=(D + ar, [(0, RED), (1, OK)]))
    for oid, x, y, txt in [("Cl2", 256, 166, "cable 2"), ("Cl3", 516, 166, "cable 3"), ("Cl1", 330, 300, "cable 1 · XC216 P1 – A port 1")]:
        p.text(oid, x, y, 260, 16, txt, size=11, color=DIM)
    p.text("RgC", 48, 332, 400, 40, "Ring closed", size=30, weight=700, color=OK, visible=rs + " = 1")
    p.text("RgO", 48, 332, 400, 40, "Ring open", size=30, weight=700, color=AMBER, visible=rs + " = 0")
    p.text("RgU", 48, 332, 500, 40, "Ring state unknown", size=30, weight=700, color=DIM, visible=rs + " < 0")
    p.text("RgCs", 48, 374, 460, 18, "redundant: one cable may fail without a stop", size=13, color=DIM, visible=rs + " = 1")
    p.text("RgOs", 48, 374, 460, 18, "no redundancy: one more break cuts a station off", size=13, color=AMBER, visible=rs + " = 0")
    p.text("RgSim", 48, 396, 460, 18, "SIMULATED (RING_SIM, bench test)", size=11, weight=700, color=RED, visible=D + "RING_SIM")
    p.text("RgUs", 48, 374, 460, 18, "the switch's record cannot be read", size=13, color=DIM, visible=rs + " < 0")
    p.text("RgNl", 560, 336, 160, 18, "RING OPENED", size=11, weight=700, color=DIM)
    p.value("RgN", 560, 352, 90, 40, D + "RING_OPEN_CNT", fmt=None, size=30, weight=700, color=INK)
    p.text("RgNu", 650, 366, 160, 20, "times", size=13, color=DIM)
    p.text("RgRl", 560, 394, 120, 16, "reads ok / failed", size=11, color=DIM)
    p.value("RgR", 680, 392, 70, 18, D + "RR_N", fmt=None, size=12, color=DIM, align="Right")
    p.text("RgRs", 752, 394, 10, 16, "/", size=11, color=DIM)
    p.value("RgRe", 760, 392, 50, 18, D + "RR_NERR", fmt=None, size=12, color=DIM)

    # -- last changes, newest first --
    card(p, "Ev", 840, 92, 416, 330, "Last ring and link changes")
    evs = {1: ("Ring open", AMBER), 2: ("Ring closed", OK), 3: ("plc-b link lost", RED), 4: ("plc-b link back", OK),
           5: ("xc216 link lost", RED), 6: ("xc216 link back", OK), 7: ("Ring state unknown", DIM)}
    for n in range(1, 6):
        y = 132 + (n - 1) * 52
        p.rect("EvR%d" % n, 856, y, 384, 44, fill=PAGE, line_width=0, radius=8, visible="%sEV%d > 0" % (D, n))
        for code, (txt, col) in evs.items():
            p.ellipse("EvL%d_%d" % (n, code), 870, y + 15, 14, 14, fill=col, line_width=0, visible="%sEV%d = %d" % (D, n, code))
            p.text("EvT%d_%d" % (n, code), 894, y + 11, 220, 22, txt, size=15, weight=700, color=INK, visible="%sEV%d = %d" % (D, n, code))
        p.value("EvA%d" % n, 1110, y + 11, 70, 22, D + "EA%d" % n, fmt="fixed0", size=15, color=INK, align="Right", visible="%sEV%d > 0" % (D, n))
        p.text("EvU%d" % n, 1184, y + 13, 52, 18, "s ago", size=12, color=DIM, visible="%sEV%d > 0" % (D, n))
    p.text("EvNone", 860, 140, 380, 20, "no change since the program started", size=13, color=DIM, visible=D + "EV1 = 0")

    # -- one card per station: four in a row (A, B, XC216, the Pi) --
    def lamp_row(oid, x, y, label, good, bad_txt, good_txt, bad_col=RED):
        p.ellipse(oid + "L", x, y + 3, 14, 14, fill=OK, line_width=0, fill_by=(good, [(0, bad_col), (1, OK)]))
        p.text(oid + "N", x + 22, y, 130, 20, label, size=13, color=DIM)
        p.text(oid + "G", x + 150, y, 120, 20, good_txt, size=13, weight=700, color=INK, visible=good)
        p.text(oid + "B", x + 150, y, 120, 20, bad_txt, size=13, weight=700, color=bad_col, visible="NOT (%s)" % good)

    CW, CY, CH = 299, 438, 258                          # card width, top, height; x = 24, 335, 646, 957
    xa, xb, xx, xp = 24, 24 + (CW + 12), 24 + 2 * (CW + 12), 24 + 3 * (CW + 12)

    card(p, "Ca", xa, CY, CW, CH, "A · controller · 192.168.1.10")
    x = xa + 18
    lamp_row("Ca1", x, 476, "Bus fault (BF)", "NOT " + D + "PN_BF", "device missing", "off")
    lamp_row("Ca2", x, 506, "System fault (SF)", "NOT " + D + "PN_SF", "on", "off")
    lamp_row("Ca3", x, 536, "Diagnosis", "NOT " + D + "PN_DIAG", "a device reports", "none", AMBER)
    lamp_row("Ca4", x, 566, "Maintenance", "NOT " + D + "PN_MAINT", "required", "none", AMBER)
    lamp_row("Ca5", x, 596, "Configuration", D + "PN_CFG_OK", "not ready / fault", "ready")
    p.text("Ca6", x + 22, 630, 130, 18, "CONFIG_STATUS", size=11, color=DIM)
    p.value("Ca6v", x + 150, 628, 80, 20, D + "PN_CFG", fmt=None, size=13, color=INK)
    p.text("Ca7", x, 660, CW - 36, 18, "Profinet system variables (PNIO_...)", size=11, color=DIM)

    card(p, "Cb", xb, CY, CW, CH, "B · plc-b · 192.168.1.11")
    x = xb + 18
    lamp_row("Cb1", x, 476, "AR (data exchange)", D + "NB_AR", "lost", "valid")
    lamp_row("Cb2", x, 506, "Diagnosis", "NOT " + D + "NB_DIAG", "pending", "none", AMBER)
    lamp_row("Cb3", x, 536, "Application", D + "NB_RUN", "not running", "running")
    lamp_row("Cb4", x, 566, "Heartbeat (3 s)", D + "B_ALIVE", "stopped", "moving")
    p.text("Cb5", x, 630, CW - 36, 18, "Drive simulator; its bits count only", size=11, color=DIM)
    p.text("Cb6", x, 646, CW - 36, 18, "while AR and heartbeat are good.", size=11, color=DIM)

    card(p, "Cx", xx, CY, CW, CH, "Switch · xc216 · 192.168.1.20")
    x = xx + 18
    lamp_row("Cx1", x, 476, "AR (data exchange)", D + "NX_AR", "lost", "valid")
    lamp_row("Cx2", x, 506, "Diagnosis", "NOT " + D + "NX_DIAG", "pending", "none", AMBER)
    lamp_row("Cx3", x, 536, "Application", D + "NX_RUN", "not running", "running")
    p.text("CxDl", x, 568, 200, 16, "DIAGNOSIS REPORTED", size=11, weight=700, color=DIM)
    p.text("CxDn", x, 586, CW - 36, 20, "none", size=13, weight=700, color=OK, visible=D + "XD_LEN = 0")
    done = []
    for cet, ext, txt in DIAG:
        cond = "%sXD_LEN > 0 AND %sXD_CET = %d" % (D, D, cet)
        if ext is not None:
            cond += " AND %sXD_EXT = %d" % (D, ext)
        else:
            cond += "".join(" AND %sXD_EXT <> %d" % (D, e) for c, e, _ in DIAG if c == cet and e is not None)
        if cet == 0x0010:                            # a parameter the device refused: name the record when it is MRP's
            p.text("CxDm", x, 586, CW - 36, 20, "Parameter refused: MRP record 0x8052", size=13, weight=700, color=AMBER,
                   visible=cond + " AND %sXD_RIDX = 32850" % D)
            cond += " AND %sXD_RIDX <> 32850" % D
        p.text("CxD%d" % len(done), x, 586, CW - 36, 20, txt, size=13, weight=700, color=AMBER, visible=cond)
        done.append(cet)
    for oid, dx, y, lab, var, w in [("CxDc", 0, 614, "error type", "XD_CET", 60), ("CxDe", 132, 614, "ext", "XD_EXT", 60),
                                    ("CxDs", 0, 634, "subslot", "XD_SUB", 60), ("CxDr", 132, 634, "record", "XD_RIDX", 60),
                                    ("CxDo", 0, 654, "offset", "XD_ROFF", 60)]:
        p.text(oid, x + dx, y + 2, 64, 16, lab, size=11, color=DIM)
        p.value(oid + "v", x + dx + 62, y, w, 18, D + var, fmt=None, size=12, color=INK)
    p.text("CxDn2", x, 676, CW - 36, 16, "decimal · record 0xE00C, every 5 s", size=11, color=DIM)

    # the Raspberry Pi with p-net: a demo device on XC216 P5, outside the ring and the interlocks
    card(p, "Cp", xp, CY, CW, CH, "Pi · pnpi · 192.168.1.30")
    x = xp + 18
    lamp_row("Cp1", x, 476, "AR (data exchange)", D + "PI_AR_OK", "lost", "valid")
    lamp_row("Cp2", x, 502, "Diagnosis", "NOT " + D + "PI_DIAG", "pending", "none", AMBER)
    p.text("Cp3", x + 22, 528, 80, 20, "Counter", size=13, color=DIM)
    p.value("Cp3v", x + 96, 526, 46, 22, D + "PI_CNT", fmt=None, size=15, weight=700, color=INK, align="Right")
    p.ellipse("Cp4L", x + 150, 531, 14, 14, fill=FAINT, line_width=0, fill_by=(D + "PI_BTN1", [(0, FAINT), (1, TEAL)]))
    p.text("Cp4", x + 172, 528, 100, 20, "Button 1", size=13, color=DIM)
    p.text("Cp5", x + 22, 560, 80, 20, "LED (bit 7)", size=13, color=DIM)
    for i, (name, val, on) in enumerate([("Off", "FALSE", "NOT " + D + "PI_LED"), ("On", "TRUE", D + "PI_LED")]):
        bx = x + 110 + i * 64
        p.button("Cp5b%d" % i, bx, 554, 64, 30, name, write=(D + "PI_LED", val), size=13)
        p.rect("Cp5a%d" % i, bx, 554, 64, 30, fill=SLATE, line=SLATE, radius=0, visible=on)
        p.text("Cp5t%d" % i, bx, 560, 64, 20, name, size=13, weight=700, color=WHITE, align="Center", visible=on)
    p.text("ECl", x, 596, 200, 16, "ECHO · SLOT 2", size=11, weight=700, color=DIM)
    p.text("ECs", x + 22, 614, 70, 18, "sent", size=12, color=DIM)
    p.value("ECsf", x + 82, 612, 70, 20, D + "PI_TX_F", fmt="fixed2", size=13, color=INK, align="Right")
    p.value("ECsi", x + 162, 612, 90, 20, D + "PI_TX_I", fmt=None, size=13, color=INK, align="Right")
    p.text("ECr", x + 22, 636, 70, 18, "returned", size=12, color=DIM)
    p.value("ECrf", x + 82, 634, 70, 20, D + "PI_RX_F", fmt="fixed2", size=13, color=INK, align="Right")
    p.value("ECri", x + 162, 634, 90, 20, D + "PI_RX_I", fmt=None, size=13, color=INK, align="Right")
    lamp_row("Cp6", x, 660, "Round trip", D + "PI_ECHO_OK", "mismatch", "= sent × gain")
    return p


def pages():
    return [pump(), trends(), history(), room(), network()]
