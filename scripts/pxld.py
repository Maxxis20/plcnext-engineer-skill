#!/usr/bin/env python3
"""pxld.py - write a PLCnext Engineer LD/FBD code worksheet (Code.ld) from a description, with layout and wires.

The worksheet is XML close to PLCopen TC6: objects with a position on a grid, pins, and for every input the
wire to its source as a list of points. Nothing is drawn by the tool: this script places the objects in columns
along the signal flow and routes the wires at right angles.

A program's source is src/<POU>/Code.ld.py with one function:

    def code(d):
        d.network("Start with delay")
        a = d.fn("AND", "START", d.neg("STOP"))            # function: inputs in pin order
        t = d.fb("TON1", "TON", IN=a, PT="T#5s")           # function block instance: inputs by pin name
        d.out("RUN", t["Q"])                               # RUN := TON1.Q
        d.rung("START", d.par("A", ["B", "/C"]), coils=["LAMP", "S:LATCH"])     # ladder rung

Inputs: a text is a variable or a constant ("START", "T#5s", "20.0"), d.neg(x) negates at the pin, a block is
its first output, block["Q"] a named output. Contacts: "X" normally open, "/X" normally closed, "P:X" / "N:X"
edges. Coils: "X", "/X", "S:X", "R:X". In a rung a list is a series, d.par(...) branches in parallel, and a
block takes the rung on its first free input and passes it on from its first output.

Pins of user function blocks are read from their Variables.var by pxproj.py; pins of the standard blocks are in
PINS below (add to it, or name every pin: d.fn("X", A=..., B=...) and outs=["Y"]).
"""
import math, re
from xml.sax.saxutils import escape

EXT = {"AND", "OR", "XOR", "ADD", "MUL", "MAX", "MIN"}                     # IN1..INn
PINS = {                                                                   # name: (inputs, outputs)
    "NOT": (["IN"], None), "MOVE": (["IN"], None), "SUB": (["IN1", "IN2"], None), "DIV": (["IN1", "IN2"], None),
    "MOD": (["IN1", "IN2"], None), "GT": (["IN1", "IN2"], None), "GE": (["IN1", "IN2"], None),
    "LT": (["IN1", "IN2"], None), "LE": (["IN1", "IN2"], None), "EQ": (["IN1", "IN2"], None),
    "NE": (["IN1", "IN2"], None), "SEL": (["G", "IN0", "IN1"], None), "LIMIT": (["MN", "IN", "MX"], None),
    "ABS": (["IN"], None),
    "TON": (["IN", "PT"], ["Q", "ET"]), "TOF": (["IN", "PT"], ["Q", "ET"]), "TP": (["IN", "PT"], ["Q", "ET"]),
    "R_TRIG": (["CLK"], ["Q"]), "F_TRIG": (["CLK"], ["Q"]), "SR": (["SET1", "RESET"], ["Q1"]),
    "RS": (["SET", "RESET1"], ["Q1"]), "CTU": (["CU", "RESET", "PV"], ["Q", "CV"]),
    "CTD": (["CD", "LOAD", "PV"], ["Q", "CV"]),
}
CONN = ('<addData><data name="connectionInformation" handleUnknown="preserve"><connectionInformation '
        'useAutoConnector="false" useUserConnector="false" implicitMultiRouted="false" invisible="false" '
        'wasExplicitFeedback="false" /></data></addData>')


def even(v):
    return int(2 * math.ceil(v / 2.0))


class Neg:
    def __init__(self, x): self.x = x


class Par:
    def __init__(self, branches): self.branches = branches


class Node:
    """One object of the sheet. ins: [name, source, negated]; source = text, (node, pin name) or None."""
    def __init__(self, kind, **kw):
        self.kind = kind; self.ins = []; self.outs = []; self.x = self.y = 0; self.col = 0
        self.conns = {}                                   # input index -> [(node, pin name)] (ladder: several = OR)
        self.__dict__.update(kw)

    def __getitem__(self, pin):
        if pin not in self.outs:
            raise KeyError("%s has no output %s (has %s)" % (self.name, pin, self.outs))
        return (self, pin)

    @property
    def out(self):
        return (self, self.outs[0])

    def in_xy(self, i):
        return (self.x, self.y + (2 if self.kind != "block" else 6 + 4 * i))

    def out_xy(self, pin=None):
        i = self.outs.index(pin) if self.kind == "block" else 0
        return (self.x + self.w, self.y + (2 if self.kind != "block" else 6 + 4 * i))


class LD:
    def __init__(self, user_blocks=None):
        self.user = user_blocks or {}                     # type name -> (inputs, outputs)
        self.nets = []; self.cur = None; self.used = set()

    # ---- description -------------------------------------------------------------------------------------
    def network(self, title=None):
        self.cur = {"title": title, "nodes": [], "rung": False}
        self.nets.append(self.cur)
        return self.cur

    def _net(self, rung=False):
        if self.cur is None or self.cur["rung"] or rung:
            self.network()
            self.cur["rung"] = rung
        return self.cur

    def neg(self, x):
        return Neg(x)

    def par(self, *branches):
        return Par(list(branches))

    def _block(self, typ, inst, args, kw, outs):
        if typ in self.user:
            ins, o = self.user[typ]
        elif typ in EXT:
            ins, o = ["IN%d" % (i + 1) for i in range(max(2, len(args)))], None
        elif typ in PINS:
            ins, o = PINS[typ]
        elif not args:
            ins, o = list(kw), None
        else:
            raise ValueError("pins of %s are not known: name them, %s(A=..., B=...)" % (typ, typ))
        o = outs or o or [typ]
        n = Node("block", typ=typ, inst=inst, name=inst or typ, hidden=inst is None)
        vals = dict(zip(ins, args)); vals.update(kw)
        for k in vals:
            if k not in ins:
                raise ValueError("%s has no input %s (has %s)" % (typ, k, ins))
        n.ins = [[k] + self._src(vals.get(k)) for k in ins]
        n.outs = list(o)
        a = max([len(k) for k in ins] + [0]); b = max([len(k) for k in n.outs] + [0])
        n.w = 8 if n.hidden else max(18, even(a + b + 6), even(len(typ) + 6))
        n.h = 4 + 4 * max(len(ins), len(n.outs), 1)
        return n

    def _src(self, v):
        neg = False
        if isinstance(v, Neg):
            neg, v = True, v.x
        if isinstance(v, Node):
            v = v.out
        return [v, neg]

    def fn(self, typ, *args, outs=None, **kw):
        n = self._block(typ, None, args, kw, outs)
        self._net()["nodes"].append(n)
        return n

    def fb(self, inst, typ, *args, outs=None, **kw):
        n = self._block(typ, inst, args, kw, outs)
        self._net()["nodes"].append(n)
        return n

    def out(self, var, src):
        n = Node("out", name=var, w=self._vw(var), h=4)
        n.ins = [["", ] + self._src(src)]
        self._net()["nodes"].append(n)
        return n

    def rung(self, *items, coils=()):
        net = self._net(rung=True)
        net["items"] = list(items); net["coils"] = list(coils)
        for it in self._flat(items):
            if isinstance(it, Node):                      # a block made for this rung: it belongs to the rung
                for other in self.nets:
                    if it in other["nodes"]:
                        other["nodes"].remove(it)
        self.nets[:] = [n for n in self.nets if n["nodes"] or n["rung"]]
        self.cur = None

    def _flat(self, items):
        for it in items:
            if isinstance(it, Par):
                yield from self._flat(it.branches)
            elif isinstance(it, (list, tuple)):
                yield from self._flat(it)
            else:
                yield it

    @staticmethod
    def _vw(text):
        return max(8, even(len(text) * 1.25 + 2))

    # ---- layout: function block part ---------------------------------------------------------------------
    def _layout_fbd(self, net, y0):
        nodes = net["nodes"]
        users = {}
        for n in nodes:
            for i in n.ins:
                if isinstance(i[1], tuple):
                    users.setdefault((id(i[1][0]), i[1][1]), []).append(n)
        for n in nodes:                                   # column = longest path from a source
            src = [i[1][0] for i in n.ins if isinstance(i[1], tuple)]
            n.col = 1 + max([s.col for s in src]) if src else 0
            n.attached = None
            if n.kind == "out" and src and len(users[(id(src[0]), n.ins[0][1][1])]) == 1:
                n.attached = n.ins[0][1]                  # the only user of that pin: sits right at the pin
                n.col = src[0].col
        ncol = 1 + max(n.col for n in nodes)
        blocks = [n for n in nodes if not n.attached]
        inw = [0] * ncol; outw = [0] * ncol; bw = [0] * ncol; nwire = [0] * ncol
        for n in nodes:
            if n.attached:
                outw[n.col] = max(outw[n.col], n.w + 2)
                continue
            bw[n.col] = max(bw[n.col], n.w)
            for i in n.ins:
                if isinstance(i[1], str):
                    inw[n.col] = max(inw[n.col], self._vw(i[1]) + 2)
                elif isinstance(i[1], tuple):
                    nwire[n.col] += 1
        colx = []; x = 4
        for c in range(ncol):
            x += inw[c] + (nwire[c] + 3 if c else 0)
            colx.append(x)
            x += bw[c] + outw[c] + 2
        free = [y0] * ncol
        for n in blocks:
            n.x = colx[n.col]
            y = free[n.col] + (2 if n.kind == "block" and not n.hidden else 0)
            for k, i in enumerate(n.ins):                 # line the first wired input up with its source
                if isinstance(i[1], tuple):
                    s = i[1][0]
                    y = max(y, s.out_xy(i[1][1])[1] - (n.in_xy(k)[1] - n.y))
                    break
            n.y = y
            free[n.col] = y + n.h + 4
        for n in nodes:
            if n.attached:
                s, pin = n.attached
                px, py = s.out_xy(pin)
                n.x, n.y = px + 2, py - 2
        chan = [0] * ncol
        bottom = max(free)
        lane = [0]
        for n in nodes:
            for k, i in enumerate(n.ins):
                if isinstance(i[1], str):
                    v = Node("in", name=i[1], w=self._vw(i[1]), h=4)
                    dx, dy = n.in_xy(k)
                    v.x, v.y = dx - 2 - v.w, dy - 2
                    net.setdefault("vars", []).append(v)
                    n.conns[k] = [((v, None), [(dx, dy), (dx - 2, dy)])]
                elif isinstance(i[1], tuple):
                    s, pin = i[1]
                    sx, sy = s.out_xy(pin); dx, dy = n.in_xy(k)
                    if n.attached or sy == dy and not self._blocked(blocks, s, n, sy):
                        pts = [(dx, dy), (sx, sy)]
                    else:
                        cx = colx[n.col] - inw[n.col] - 2 - chan[n.col]; chan[n.col] += 1
                        if self._blocked(blocks, s, n, sy):       # something in the way: go round below
                            yl = bottom + lane[0]; lane[0] += 1
                            ox = sx + 2 + lane[0]
                            pts = [(dx, dy), (cx, dy), (cx, yl), (ox, yl), (ox, sy), (sx, sy)]
                        else:
                            pts = [(dx, dy), (cx, dy), (cx, sy), (sx, sy)]
                    n.conns[k] = [((s, pin), pts)]
        return bottom + lane[0] + 2

    @staticmethod
    def _blocked(blocks, s, n, y):
        return any(s.col < b.col < n.col and b.y - 3 <= y <= b.y + b.h + 1 for b in blocks)

    # ---- layout: ladder rung -----------------------------------------------------------------------------
    def _layout_rung(self, net, y0):
        nodes = net["nodes"] = []
        rail = Node("left", name="", w=3, h=4, outs=["rail"]); rail.x, rail.y = 4, y0 + 4
        nodes.append(rail)
        rows = [1]

        def wire(n, k, srcs):
            dx, dy = n.in_xy(k)
            n.conns[k] = []
            for s, pin in srcs:
                sx, sy = s.out_xy(pin)
                pts = [(dx, dy), (sx, sy)] if sy == dy else [(dx, dy), (dx - 1, dy), (dx - 1, sy), (sx, sy)]
                n.conns[k].append(((s, pin), pts))

        def place(item, x, y, srcs):                       # -> x after it, rows used, outputs
            if isinstance(item, Par):
                outs = []; xe = x; r = 0
                for b in item.branches:
                    bx, br, bo = place(b, x, y + 8 * r, srcs)
                    outs += bo; xe = max(xe, bx); r += br
                return xe, r, outs
            if isinstance(item, (list, tuple)):
                r = 1
                for it in item:
                    x, ir, srcs = place(it, x, y, srcs)
                    r = max(r, ir)
                return x, r, srcs
            if isinstance(item, Node):                     # a block in the rung
                k = next(i for i, p in enumerate(item.ins) if p[1] is None)
                vw = max([self._vw(p[1]) + 2 for p in item.ins if isinstance(p[1], str)] + [0])
                item.x = x + vw
                item.y = y + 2 - (6 + 4 * k)
                for j, p in enumerate(item.ins):
                    if isinstance(p[1], str):
                        v = Node("in", name=p[1], w=self._vw(p[1]), h=4)
                        dx, dy = item.in_xy(j)
                        v.x, v.y = dx - 2 - v.w, dy - 2
                        net.setdefault("vars", []).append(v)
                        item.conns[j] = [((v, None), [(dx, dy), (dx - 2, dy)])]
                wire(item, k, srcs)
                nodes.append(item)
                return item.x + item.w + 2, int(math.ceil((item.h - 4 * k) / 8.0)) + (1 if k else 0), [item.out]
            m = re.match(r"^(/|P:|N:)?(.+)$", item)
            c = Node("contact", name=m.group(2), mod=m.group(1) or "", w=18, h=4, outs=["out"])
            c.x, c.y = x, y
            wire(c, 0, srcs)
            nodes.append(c)
            return x + 20, 1, [c.out]

        x, r, outs = place(net["items"], rail.x + 5, rail.y, [rail.out])
        coils = []
        for j, text in enumerate(net["coils"]):
            m = re.match(r"^(/|S:|R:)?(.+)$", text)
            c = Node("coil", name=m.group(2), mod=m.group(1) or "", w=18, h=4, outs=["out"])
            c.x, c.y = x, rail.y + 8 * j
            wire(c, 0, outs)
            nodes.append(c); coils.append(c)
        right = Node("right", name="", w=3, h=4); right.ins = [["", None, False]]; right.x, right.y = x + 20, rail.y
        wire(right, 0, [c.out for c in coils])
        nodes.append(right)
        low = max([n.y + n.h for n in nodes])
        return max(rail.y + 8 * max(r, len(coils)), low + 4)

    # ---- XML ---------------------------------------------------------------------------------------------
    def xml(self):
        out = []; lid = [0]; order = [0]; y = 2

        def new():
            lid[0] += 1
            return lid[0]

        ids = {}
        for nid, net in enumerate(self.nets, start=1):
            net["id"] = nid
            y = self._layout_rung(net, y) if net["rung"] else self._layout_fbd(net, y + 2)
            for n in net.get("vars", []) + net["nodes"]:
                n.net = nid; n.lid = new()
                n.pin_ids = [new() for _ in n.ins + n.outs] if n.kind in ("block", "left", "right") else []

        def conn(n, k):
            s = ""
            for (src, pin), pts in n.conns.get(k, []):
                fp = ""
                if src.kind == "block":
                    fp = ' formalParameter="%s"' % pin
                elif src.kind == "left":
                    fp = ' formalParameter="%d"' % src.pin_ids[0]
                s += '<connection refLocalId="%d"%s>%s%s</connection>' % (
                    src.lid, fp, "".join('<position x="%d" y="%d" />' % p for p in pts), CONN)
            return s

        def info(n):
            return ('<data name="objectInformation" handleUnknown="preserve"><objectInformation networkId="%d" '
                    'subNetworkId="0" /></data>' % n.net)

        for net in self.nets:
            for n in net.get("vars", []) + net["nodes"]:
                order[0] += 1
                head = 'localId="%d" height="%d" width="%d" executionOrderId="%d"' % (n.lid, n.h, n.w, order[0])
                pos = '<position x="%d" y="%d" />' % (n.x, n.y)
                if n.kind == "in":
                    out.append('<inVariable %s>%s<connectionPointOut><relPosition x="%d" y="2" /></connectionPointOut>'
                               '<expression>%s</expression><addData>%s</addData></inVariable>'
                               % (head, pos, n.w, escape(n.name), info(n)))
                elif n.kind == "out":
                    out.append('<outVariable %s>%s<connectionPointIn><relPosition x="0" y="2" />%s</connectionPointIn>'
                               '<expression>%s</expression><addData>%s</addData></outVariable>'
                               % (head, pos, conn(n, 0), escape(n.name), info(n)))
                elif n.kind in ("contact", "coil"):
                    a = {"/": ' negated="true"', "P:": ' edge="rising"', "N:": ' edge="falling"',
                         "S:": ' storage="set"', "R:": ' storage="reset"'}.get(n.mod, "")
                    out.append('<%s %s%s>%s<connectionPointIn><relPosition x="0" y="2" />%s</connectionPointIn>'
                               '<connectionPointOut><relPosition x="%d" y="2" /></connectionPointOut>'
                               '<variable>%s</variable><addData>%s</addData></%s>'
                               % (n.kind, head, a, pos, conn(n, 0), n.w, escape(n.name), info(n), n.kind))
                elif n.kind == "left":
                    out.append('<leftPowerRail %s>%s<connectionPointOut formalParameter="%d"><relPosition x="3" y="2" />'
                               '<addData><data name="linkInformation" handleUnknown="preserve"><linkInformation '
                               'executionOrderId="%d" localId="%d" /></data></addData></connectionPointOut>'
                               '<addData>%s</addData></leftPowerRail>'
                               % (head, pos, n.pin_ids[0], order[0], n.pin_ids[0], info(n)))
                elif n.kind == "right":
                    out.append('<rightPowerRail %s>%s<connectionPointIn><relPosition x="0" y="2" />%s'
                               '<addData><data name="linkInformation" handleUnknown="preserve"><linkInformation '
                               'executionOrderId="%d" localId="%d" /></data></addData></connectionPointIn>'
                               '<addData>%s</addData></rightPowerRail>'
                               % (head, pos, conn(n, 0), order[0], n.pin_ids[0], info(n)))
                else:
                    hid = ' hidden="true"' if n.hidden else ""
                    ins = "".join('<variable formalParameter="%s"%s%s><connectionPointIn><relPosition x="0" y="%d" />%s'
                                  '</connectionPointIn></variable>'
                                  % (p[0], ' negated="true"' if p[2] else "", hid, 6 + 4 * k, conn(n, k))
                                  for k, p in enumerate(n.ins))
                    outs = "".join('<variable formalParameter="%s"%s><connectionPointOut><relPosition x="%d" y="%d" />'
                                   '</connectionPointOut></variable>' % (p, hid, n.w, 6 + 4 * k)
                                   for k, p in enumerate(n.outs))
                    pinfo = "".join('<parameterInformation formalParameter="%s" localId="%d" executionOrderId="%d" '
                                    'negatable="true" hidden="false" editorParameter="false" priority="%d" />'
                                    % (name, n.pin_ids[k], order[0], k + 1)
                                    for k, name in enumerate([p[0] for p in n.ins] + n.outs))
                    out.append('<block localId="%d" width="%d" height="%d" typeName="%s"%s executionOrderId="%d">%s'
                               '<inputVariables>%s</inputVariables><inOutVariables /><outputVariables>%s'
                               '</outputVariables><addData>%s<data name="blockInformation" handleUnknown="preserve">'
                               '<blockInformation canEditLabel="%s" extensible="%s" imageWidth="8" imageHeight="0" />'
                               '</data><data name="parameterInformations" handleUnknown="preserve">'
                               '<parameterInformations>%s</parameterInformations></data></addData></block>'
                               % (n.lid, n.w, n.h, n.typ, ' instanceName="%s"' % n.inst if n.inst else "", order[0],
                                  pos, ins, outs, info(n), "true" if n.inst else "false",
                                  "true" if n.typ in EXT else "false", pinfo))
        return ('<?xml version="1.0" encoding="utf-8"?>\n<body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
                'xmlns:xsd="http://www.w3.org/2001/XMLSchema">\n <LD>\n  %s\n </LD>\n <addData>\n  <data '
                'name="docInformation" handleUnknown="preserve">\n   <docInformation gridActive="true" pageWidth="-1">\n'
                '    <version>2.9.4.230.0:A2.0</version>\n    <multilineOptions maximumContactWidth="18" '
                'minimumContactWidth="18" maximumContactLines="7" contactEllipse="true" maximumInstanceNameWidth="32" '
                'maximumInstanceNameLines="5" instanceNameEllipse="true" maximumVariableWidth="2147483647" '
                'variableEllipse="false" />\n   </docInformation>\n  </data>\n </addData>\n</body>'
                % "\n  ".join(out))


def pins_from_var(text):
    """(inputs, outputs) of a function block from its Variables.var text."""
    ins, outs = [], []
    for kind, body in re.findall(r"\b(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT)\b(.*?)\bEND_VAR\b", text, re.S):
        for name in re.findall(r"^\s*([A-Za-z_]\w*)\s*:", re.sub(r"\(\*.*?\*\)", "", body, flags=re.S), re.M):
            (outs if kind == "VAR_OUTPUT" else ins).append(name)
    return ins, outs
