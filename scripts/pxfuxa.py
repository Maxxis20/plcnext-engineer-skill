#!/usr/bin/env python3
"""pxfuxa.py - FUXA project generator: one MQTT device, one tag per topic, one view with live values.

For a FUXA 1.3.5 that runs beside the Mosquitto broker (findings, section MQTT). The controller publishes all
flagged ports in one JSON message; mqtt-flatten.js beside the broker turns that into one topic per value
("plcnext/dh/TE1" with the plain number as payload), so every tag is a raw MQTT tag whose address is the topic.

    from pxfuxa import Fuxa
    f = Fuxa("DH over MQTT", width=760, height=430)
    te1 = f.tag("TE1", "plcnext/dh/TE1")
    f.box(20, 60, 340, 120); f.text(36, 86, "Hot water, °C", 12, fill="#5f6368")
    f.value(36, 120, te1, digits=1); f.lamp(300, 112, f.tag("P1", "plcnext/dh/P1_RUN"), on="#34a853")
    f.save("project.json")          # then: pxe.sh fuxa project.json [png]

Static shapes besides text / box / line: circle, polygon, polyline (no live binding). A lamp takes `ranges` for a
value with more than two states.

Coordinates are svg pixels from the top left of the view; a text's y is its baseline. Forms proven on FUXA 1.3.5:
a live number is a group type "svg-ext-value" holding one text; a lamp is a group type "svg-ext-gauge_semaphore"
holding one ellipse, coloured by value range. FUXA does not draw a unit and ignores zero decimals, so write the
unit into a label.
"""
import json
from xml.sax.saxutils import escape


class Fuxa:
    def __init__(self, name, width=800, height=480, broker="mqtt://127.0.0.1:1883", background="#f4f5f7", title=None):
        self.name, self.w, self.h, self.broker, self.bg = name, width, height, broker, background
        self.title = title or name
        self.tags, self.items, self.svg, self.n = {}, {}, [], 0

    def _id(self, prefix):
        self.n += 1
        return f"{prefix}_{self.n:03d}"

    def tag(self, name, topic):
        """Subscribe to a topic. Returns the tag id to hand to value() and lamp()."""
        tid = "t_" + name
        if tid in self.tags:
            raise ValueError(f"tag {name} defined twice")
        self.tags[tid] = {"id": tid, "name": name, "type": "raw", "address": topic, "memaddress": topic,
                          "options": {"subs": [topic]},
                          "daq": {"enabled": False, "interval": 60, "changed": False, "restored": False}}
        return tid

    def text(self, x, y, s, size=13, weight="normal", fill="#202124", anchor="start"):
        self.svg.append(f'<text id="{self._id("svg")}" x="{x}" y="{y}" font-family="Arial" font-size="{size}" '
                        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" stroke="none" '
                        f'xml:space="preserve">{escape(str(s))}</text>')

    def box(self, x, y, w, h, fill="#ffffff", stroke="#9aa0a6", radius=8, width=1):
        self.svg.append(f'<rect id="{self._id("svg")}" x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" '
                        f'ry="{radius}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def line(self, x1, y1, x2, y2, stroke="#5f6368", width=2, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.svg.append(f'<line id="{self._id("svg")}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
                        f'stroke-width="{width}"{d}/>')

    def circle(self, cx, cy, r, fill="#ffffff", stroke="#5f6368", width=1.5):
        """Static circle (no live value: use lamp() for one that changes colour)."""
        self.svg.append(f'<circle id="{self._id("svg")}" cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" '
                        f'stroke-width="{width}"/>')

    def polygon(self, points, fill="#5f6368", stroke="none", width=1):
        """Closed static shape through [(x, y), ...]: arrows, valve bodies, triangles."""
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.svg.append(f'<polygon id="{self._id("svg")}" points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def polyline(self, points, stroke="#5f6368", width=1.5, fill="none"):
        """Open static line through [(x, y), ...]: filter zig-zags, coil loops, pipe runs with corners."""
        pts = " ".join(f"{x},{y}" for x, y in points)
        self.svg.append(f'<polyline id="{self._id("svg")}" points="{pts}" fill="{fill}" stroke="{stroke}" stroke-width="{width}"/>')

    def value(self, x, y, tag, digits=1, size=22, fill="#0b57d0", anchor="start"):
        """Live number of a tag."""
        self._known(tag); gid = self._id("VAL")
        self.svg.append(f'<g id="{gid}" type="svg-ext-value"><text id="{gid}_t" x="{x}" y="{y}" font-family="Arial" '
                        f'font-size="{size}" font-weight="bold" fill="{fill}" text-anchor="{anchor}" stroke="none" '
                        f'xml:space="preserve">--</text></g>')
        self.items[gid] = {"id": gid, "type": "svg-ext-value", "name": self.tags[tag]["name"], "label": "Value",
                           "property": {"variableId": tag, "events": [], "actions": [],
                                        "ranges": [{"type": "unit", "min": 0, "max": 0, "text": "", "fractionDigits": digits}]}}

    def lamp(self, x, y, tag, on="#34a853", off="#bdc1c6", r=10, ranges=None, stroke="#5f6368"):
        """Circle that takes colour `on` while the tag is 1 and `off` while it is 0. x, y is the centre.
        ranges=[(min, max, colour), ...] replaces on / off, for a value with more states (a mode 0 ... 4, an
        alarm state 0 ... 5); the circle is drawn in the first range's colour until a value arrives."""
        self._known(tag); gid = self._id("LMP")
        rs = [{"min": a, "max": b, "color": c} for a, b, c in ranges] if ranges else \
             [{"min": 0, "max": 0, "color": off}, {"min": 1, "max": 1, "color": on}]
        self.svg.append(f'<g id="{gid}" type="svg-ext-gauge_semaphore"><ellipse id="{gid}_e" cx="{x}" cy="{y}" rx="{r}" '
                        f'ry="{r}" fill="{rs[0]["color"]}" stroke="{stroke}" stroke-width="1.5"/></g>')
        self.items[gid] = {"id": gid, "type": "svg-ext-gauge_semaphore", "name": self.tags[tag]["name"], "label": "HtmlSemaphore",
                           "property": {"variableId": tag, "events": [], "actions": [], "ranges": rs}}

    def _known(self, tag):
        if tag not in self.tags:
            raise ValueError(f"unknown tag id {tag!r}: use the value returned by tag()")

    def project(self):
        content = (f'<svg width="{self.w}" height="{self.h}" xmlns="http://www.w3.org/2000/svg" '
                   'xmlns:svg="http://www.w3.org/2000/svg" xmlns:html="http://www.w3.org/1999/xhtml">'
                   '<g><title>Layer 1</title>' + "".join(self.svg) + "</g></svg>")
        return {
            "version": "1.01", "name": self.name,
            "server": {"id": "0", "name": "FUXA Server", "type": "FuxaServer", "property": {}, "tags": {}, "polling": 1000},
            "devices": {"d_mqtt": {"id": "d_mqtt", "name": "MQTT", "enabled": True, "type": "MQTTclient", "polling": 1000,
                                   "property": {"address": self.broker}, "tags": self.tags}},
            "hmi": {"views": [{"id": "v_main", "name": self.name, "items": self.items, "variables": {}, "svgcontent": content,
                               "profile": {"width": self.w, "height": self.h, "bkcolor": self.bg}}],
                    "layout": {"navigation": {"mode": "void", "type": "block", "bkcolor": "#263238", "fgcolor": "#ffffff", "items": []},
                               "header": {"title": self.title, "alarms": "hide", "infos": "hide", "bkcolor": "#263238",
                                          "fgcolor": "#ffffff", "height": 46, "dateTimeDisplay": ""},
                               "start": "v_main", "loginonstart": False, "loginoverlaycolor": "none", "showdev": False,
                               "inputdialog": "no", "hidenavigation": True}},
            "charts": [], "alarms": [], "scripts": [], "texts": [], "recipes": [], "ar": {"enabled": False, "markers": []},
        }

    def save(self, path):
        with open(path, "w", encoding="ascii") as f:
            json.dump(self.project(), f)                        # ascii: non-ASCII as \u escapes, safe through the transfer
        return path

    def stats(self):
        return {"tags": len(self.tags), "live items": len(self.items), "svg elements": len(self.svg)}
