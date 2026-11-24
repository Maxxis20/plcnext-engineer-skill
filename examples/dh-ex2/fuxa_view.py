#!/usr/bin/env python3
"""FUXA view of the district heating example, fed over MQTT: controller -> Mosquitto -> mqtt-flatten.js -> FUXA.

    python3 fuxa_view.py            # writes DH-ex2.fuxa.json beside this file
    pxe.sh fuxa DH-ex2.fuxa.json    # loads it into the FUXA on the VM and shows it

Every value here is one of the ports flagged { OutputPort, PROFICLOUD } in src/DH_EX2/Variables.var.
"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts"))
from pxfuxa import Fuxa

T = "plcnext/dh/"
GREY, BLUE, RED, GREEN, AMBER = "#5f6368", "#0b57d0", "#d93025", "#34a853", "#f9ab00"
f = Fuxa("DH-ex2 over MQTT", width=980, height=560, title="District heating substation: AXC F 2152 over MQTT")
t = {n: f.tag(n, T + n) for n in "TE1 TE2A TE2B TOUT DHW_SP HEAT_SP TV1 TV2 P1_RUN P2_RUN SUMMER ALARM_SUM "
                                 "P1_FAULT P2_FAULT DHW_TEMP_ALM HEAT_TEMP_ALM".split()}


def card(x, y, w, h, title):
    f.box(x, y, w, h); f.text(x + 16, y + 26, title, 14, weight="bold")


def number(x, y, label, tag, unit, colour=BLUE):
    f.text(x, y, label, 12, fill=GREY); f.value(x, y + 30, t[tag], digits=1, fill=colour); f.text(x + 74, y + 30, unit, 12, fill=GREY)


def state(x, y, label, tag, on=GREEN, off="#bdc1c6"):
    f.lamp(x + 8, y - 4, t[tag], on=on, off=off, r=8); f.text(x + 26, y, label, 12)


# outdoor and mode
card(20, 20, 300, 150, "Outdoor")
number(36, 76, "Outdoor temperature TE2B", "TE2B", "°C")
number(190, 76, "Plant model", "TOUT", "°C", GREY)
state(36, 150, "Summer stop", "SUMMER", on=AMBER)

# domestic hot water
card(340, 20, 300, 250, "Domestic hot water (TC1)")
number(356, 76, "Hot water TE1", "TE1", "°C", RED)
number(500, 76, "Set point", "DHW_SP", "°C", GREY)
number(356, 146, "Valve TV1", "TV1", "%")
state(356, 220, "Circulation pump P1 running", "P1_RUN")
state(356, 248, "P1 fault", "P1_FAULT", on=RED)

# heating
card(660, 20, 300, 250, "Heating (TC2)")
number(676, 76, "Supply TE2A", "TE2A", "°C", RED)
number(820, 76, "Set point", "HEAT_SP", "°C", GREY)
number(676, 146, "Valve TV2", "TV2", "%")
state(676, 220, "Heating pump P2 running", "P2_RUN")
state(676, 248, "P2 fault", "P2_FAULT", on=RED)

# alarms
card(20, 190, 300, 180, "Alarms")
state(36, 246, "Alarm, any", "ALARM_SUM", on=RED)
state(36, 276, "Hot water temperature", "DHW_TEMP_ALM", on=RED)
state(36, 306, "Heating supply temperature", "HEAT_TEMP_ALM", on=RED)

# where the values come from
card(340, 290, 620, 80, "Data path")
f.text(356, 346, "AXC F 2152 firmware MQTT client  ->  Mosquitto  ->  one topic per value  ->  FUXA (read only)", 13, fill=GREY)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "DH-ex2.fuxa.json")
f.save(out); print(out, f.stats())
