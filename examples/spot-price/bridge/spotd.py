#!/usr/bin/env python3
"""Spot price bridge: fetches day-ahead electricity prices and serves them as retained MQTT messages
and as a Modbus TCP server. What it serves is written down in CONTRACT.md. Standard library only.

    spotd.py config.json            run
    spotd.py config.json --once     fetch, print the 'now' objects, exit (no MQTT, no Modbus)

Config (JSON):
    {"tz": "Europe/Helsinki",
     "source": "spot-hinta",                    # or "fake"
     "areas": [{"area": "FI", "vat_pct": 25.5, "add": 0.0}, {"area": "SE3"}],
     "mqtt": {"host": "broker", "port": 1883, "user": "name", "password_env": "SPOT_MQTT_PASSWORD",
              "prefix": "spot"},               # leave "mqtt" out for none
     "modbus": {"port": 1502},                  # leave out for none
     "fake": "fake.json"}                       # only with source "fake"

Fake file (read again every cycle, so a test changes it while the bridge runs):
    {"clock": "2026-01-15T13:30:00",            # local time the bridge pretends it is when the file is read
     "today": [24 or 96 numbers, c/kWh], "tomorrow": [...] or null,
     "dead": false,                             # true: the source no longer answers (valid falls to 0 after max_age_s)
     "max_age_s": 21600}
"""
import datetime as dt
import json
import os
import socket
import struct
import sys
import threading
import time
import urllib.request
from zoneinfo import ZoneInfo

UTC = dt.timezone.utc
NOVAL = -32768
MAX_AGE = 6 * 3600
UA = "spotd/1.0"


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


# ---------------------------------------------------------------- sources

def fetch_spot_hinta(area):
    """-> {utc epoch of quarter start: c/kWh without tax}"""
    url = "https://api.spot-hinta.fi/TodayAndDayForward?region=%s&priceResolution=15" % area
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.load(r)
    out = {}
    for row in rows:
        t = dt.datetime.fromisoformat(row["DateTime"].replace("Z", "+00:00"))
        out[int(t.timestamp())] = float(row["PriceNoTax"]) * 100.0
    return out


def fetch_porssisahko():
    """Finland only, prices include VAT 25.5 %: taken out again. -> {epoch: c/kWh without tax}"""
    req = urllib.request.Request("https://api.porssisahko.net/v2/latest-prices.json", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        rows = json.load(r)["prices"]
    out = {}
    for row in rows:
        t = dt.datetime.fromisoformat(row["startDate"].replace("Z", "+00:00"))
        p = float(row["price"])
        out[int(t.timestamp())] = p / 1.255 if p > 0 else p
    return out


# ---------------------------------------------------------------- one area

class Area:
    def __init__(self, cfg, tz):
        self.name = cfg["area"]
        self.vat = float(cfg.get("vat_pct", 0.0))
        self.add = float(cfg.get("add", 0.0))
        self.tz = tz
        self.q = {}                 # epoch -> price
        self.fetched = 0.0          # time of the last good answer (bridge clock)
        self.next_try = 0.0
        self.source = ""
        self.max_age = MAX_AGE
        self.lock = threading.Lock()

    def total(self, p):
        if p is None:
            return None
        p = p + self.add
        return p * (1.0 + self.vat / 100.0) if p > 0 else p

    def day(self, date):
        """-> (h[24], q[96]) of a local date; None where no price"""
        hs, qs = [], []
        for h in range(24):
            vals = []
            for fold in (0, 1):
                t0 = dt.datetime(date.year, date.month, date.day, h, tzinfo=self.tz, fold=fold)
                e = int(t0.astimezone(UTC).timestamp())
                vals.append([self.q.get(e + k * 900) for k in range(4)])
            a, b = vals
            quarters = []
            for k in range(4):
                both = [x for x in (a[k], b[k] if b != a else None) if x is not None]
                quarters.append(sum(both) / len(both) if both else None)
            qs += quarters
            have = [x for x in quarters if x is not None]
            hs.append(sum(have) / len(have) if have else None)
        return hs, qs

    def snapshot(self, now, beat):
        """now: aware local datetime -> (now object, today object, tomorrow object)"""
        with self.lock:
            today, tq = self.day(now.date())
            tomo, mq = self.day(now.date() + dt.timedelta(days=1))
            age = time.time() - self.fetched if self.fetched else None
            src = self.source
            max_age = self.max_age
        h, qi = now.hour, now.hour * 4 + now.minute // 15
        today_ok = all(x is not None for x in today)
        tomo_ok = all(x is not None for x in tomo)
        valid = int(today_ok and age is not None and age <= max_age)
        order = sorted(range(24), key=lambda i: (today[i] if today[i] is not None else 1e9, i))
        rank = [0] * 24
        for pos, i in enumerate(order):
            rank[i] = pos + 1 if today[i] is not None else 0
        have = [x for x in today if x is not None]
        ahead = today[h:] + (tomo if tomo_ok else [])
        cheap_in = None
        best = None
        for i in range(len(ahead) - 2):
            blk = ahead[i:i + 3]
            if None in blk:
                continue
            if best is None or sum(blk) < best - 1e-9:
                best, cheap_in = sum(blk), i
        nxt = (ahead[1:4] + [None] * 3)[:3]
        up = []                         # upcoming hours from the running one, as far as known in a row
        for x in ahead[:48]:
            if x is None:
                break
            up.append(x)
        utc_h = now.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        r = lambda x: None if x is None else round(x, 3)
        o_now = {
            "area": self.name, "valid": valid, "beat": beat, "hour": h, "quarter": qi,
            "now": r(today[h]), "now15": r(tq[qi]), "now_total": r(self.total(today[h])),
            "rank": rank[h], "avg": r(sum(have) / len(have)) if have else None,
            "min": r(min(have)) if have else None, "max": r(max(have)) if have else None,
            "next1": r(nxt[0]), "next2": r(nxt[1]), "next3": r(nxt[2]),
            "cheap3_in": -1 if cheap_in is None else cheap_in,
            "tomorrow_ok": int(tomo_ok), "known": len(up), "age_s": None if age is None else int(age),
            "ts": utc_h.strftime("%Y-%m-%dT%H:%M:%SZ"), "unit": "c/kWh", "source": src,
        }
        o_today = {"area": self.name, "date": str(now.date()), "ok": int(today_ok),
                   "h": [r(x) for x in today], "rank": rank, "q": [r(x) for x in tq]}
        if tomo_ok:
            order = sorted(range(24), key=lambda i: (tomo[i], i))
            rk = [0] * 24
            for pos, i in enumerate(order):
                rk[i] = pos + 1
            o_tomo = {"area": self.name, "date": str(now.date() + dt.timedelta(days=1)), "ok": 1,
                      "h": [r(x) for x in tomo], "rank": rk, "q": [r(x) for x in mq]}
        else:
            o_tomo = {"area": self.name, "date": str(now.date() + dt.timedelta(days=1)), "ok": 0,
                      "h": [], "rank": [], "q": []}
        blk = []                        # hours until the cheapest block of n hours among the upcoming ones, n = 1..12
        for nn in range(1, 13):
            sums = [sum(up[i:i + nn]) for i in range(len(up) - nn + 1)]
            blk.append(sums.index(min(sums)) if sums else -1)
        for nn, b in enumerate(blk, 1):
            o_now["blk%d" % nn] = b
        o_now["_up"] = [r(x) for x in up]
        return o_now, o_today, o_tomo


def registers(o_now, o_today, o_tomo):
    """-> {address: signed 16 bit value}"""
    def p(x):
        if x is None:
            return NOVAL
        return max(-32767, min(32767, int(round(x * 100))))
    reg = {0: o_now["valid"], 1: o_now["beat"] % 32768, 2: o_now["hour"], 3: o_now["quarter"],
           4: p(o_now["now"]), 5: p(o_now["now15"]), 6: p(o_now["now_total"]), 7: o_now["rank"],
           8: p(o_now["avg"]), 9: p(o_now["min"]), 10: p(o_now["max"]),
           11: p(o_now["next1"]), 12: p(o_now["next2"]), 13: p(o_now["next3"]),
           14: o_now["cheap3_in"], 15: o_now["tomorrow_ok"],
           16: NOVAL if o_now["age_s"] is None else min(32767, o_now["age_s"] // 60)}
    reg[17] = o_now["known"]
    for nn in range(1, 13):
        reg[599 + nn] = NOVAL if o_now["blk%d" % nn] < 0 else o_now["blk%d" % nn]
    for i in range(48):
        reg[500 + i] = p(o_now["_up"][i]) if i < o_now["known"] else NOVAL
    for i in range(24):
        reg[100 + i] = p(o_today["h"][i])
        reg[130 + i] = o_today["rank"][i]
        reg[200 + i] = p(o_tomo["h"][i]) if o_tomo["ok"] else NOVAL
    for i in range(96):
        reg[300 + i] = p(o_today["q"][i])
        reg[400 + i] = p(o_tomo["q"][i]) if o_tomo["ok"] else NOVAL
    return reg


def points(o_now, o_today, o_tomo, o_up):
    """Everything as one list of {"id", "v"}: for clients that write each item to the point named by id.
    No value = 0 (the valid, tomorrow_ok and known items say what counts)."""
    z = lambda x: 0 if x is None else x
    out = [{"id": "spot." + k, "v": z(v)} for k, v in o_now.items()
           if not k.startswith("_") and (v is None or isinstance(v, (int, float))) and k != "area"]
    out += [{"id": "spot.h%d" % i, "v": z(o_today["h"][i])} for i in range(24)]
    out += [{"id": "spot.r%d" % i, "v": o_today["rank"][i]} for i in range(24)]
    out += [{"id": "spot.t%d" % i, "v": z(o_tomo["h"][i]) if o_tomo["ok"] else 0} for i in range(24)]
    out += [{"id": "spot.u%d" % i, "v": o_up["h"][i] if i < o_up["known"] else 0} for i in range(48)]
    return out


# ---------------------------------------------------------------- MQTT (3.1.1, publish only, QoS 0 retained)

class Mqtt:
    def __init__(self, cfg):
        self.cfg = cfg
        self.sock = None
        self.last = 0.0

    @staticmethod
    def _s(s):
        b = s.encode()
        return struct.pack(">H", len(b)) + b

    @staticmethod
    def _len(n):
        out = b""
        while True:
            d, n = n % 128, n // 128
            out += bytes([d | (0x80 if n else 0)])
            if not n:
                return out

    def connect(self):
        c = self.cfg
        s = socket.create_connection((c["host"], int(c.get("port", 1883))), timeout=10)
        flags, tail = 0x02, self._s("spotd-%d" % os.getpid())
        if c.get("user"):
            flags |= 0x80
            tail += self._s(c["user"])
            pw = os.environ.get(c.get("password_env", ""), "")
            if pw:
                flags |= 0x40
                tail += self._s(pw)
        body = self._s("MQTT") + bytes([4, flags]) + struct.pack(">H", 60) + tail
        s.sendall(b"\x10" + self._len(len(body)) + body)
        ack = s.recv(4)
        if len(ack) < 4 or ack[3] != 0:
            s.close()
            raise OSError("MQTT connect refused, code %s" % (ack[3] if len(ack) > 3 else "?"))
        self.sock = s
        log("MQTT connected to", c["host"])

    def publish(self, topic, obj):
        payload = json.dumps(obj, separators=(",", ":")).encode()
        body = self._s(topic) + payload
        try:
            if self.sock is None:
                self.connect()
            self.sock.sendall(b"\x31" + self._len(len(body)) + body)     # retain, QoS 0
            self.last = time.time()
        except OSError as e:
            log("MQTT:", e)
            try:
                self.sock and self.sock.close()
            finally:
                self.sock = None


# ---------------------------------------------------------------- Modbus TCP server

class Modbus(threading.Thread):
    def __init__(self, port):
        super().__init__(daemon=True)
        self.port = port
        self.units = {}             # unit id -> {address: value}
        self.lock = threading.Lock()

    def run(self):
        srv = socket.socket()
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("", self.port))
        srv.listen(8)
        log("Modbus TCP on port", self.port)
        while True:
            c, _ = srv.accept()
            threading.Thread(target=self.client, args=(c,), daemon=True).start()

    def client(self, c):
        c.settimeout(120)
        try:
            while True:
                head = self._read(c, 7)
                if not head:
                    return
                tid, pid, ln, unit = struct.unpack(">HHHB", head)
                pdu = self._read(c, ln - 1)
                if not pdu:
                    return
                fc = pdu[0]
                if fc in (3, 4) and len(pdu) == 5:
                    addr, n = struct.unpack(">HH", pdu[1:])
                    with self.lock:
                        reg = self.units.get(unit)
                    if reg is None:
                        out = bytes([fc | 0x80, 0x0B])
                    elif not 1 <= n <= 125:
                        out = bytes([fc | 0x80, 3])
                    else:
                        vals = [reg.get(addr + i, 0) for i in range(n)]
                        out = bytes([fc, 2 * n]) + struct.pack(">%dh" % n, *vals)
                else:
                    out = bytes([fc | 0x80, 1])
                c.sendall(struct.pack(">HHHB", tid, pid, len(out) + 1, unit) + out)
        except OSError:
            pass
        finally:
            c.close()

    @staticmethod
    def _read(c, n):
        buf = b""
        while len(buf) < n:
            part = c.recv(n - len(buf))
            if not part:
                return b""
            buf += part
        return buf


# ---------------------------------------------------------------- main

class Bridge:
    def __init__(self, cfg, base):
        self.cfg = cfg
        self.base = base
        self.tz = ZoneInfo(cfg.get("tz", "Europe/Helsinki"))
        self.areas = [Area(a, self.tz) for a in cfg["areas"]]
        self.fake = cfg.get("source") == "fake"
        self.offset = dt.timedelta(0)       # fake clock
        self.fake_seen = None
        self.beat = 0

    def now(self):
        return dt.datetime.now(self.tz) + self.offset

    # -- fake source: the file is the truth, read every cycle
    def load_fake(self):
        path = os.path.join(self.base, self.cfg["fake"])
        try:
            st = os.stat(path).st_mtime
            if st == self.fake_seen:
                return
            with open(path) as f:
                d = json.load(f)
        except (OSError, ValueError) as e:
            log("fake file:", e)
            return
        self.fake_seen = st
        if d.get("clock"):
            want = dt.datetime.fromisoformat(d["clock"]).replace(tzinfo=self.tz)
            self.offset = want - dt.datetime.now(self.tz)
        today = self.now().date()
        q = {}
        for off, key in ((0, "today"), (1, "tomorrow")):
            vals = d.get(key)
            if not vals:
                continue
            if len(vals) == 24:
                vals = [v for v in vals for _ in range(4)]
            day = today + dt.timedelta(days=off)
            for i, v in enumerate(vals[:96]):
                t0 = dt.datetime(day.year, day.month, day.day, i // 4, 15 * (i % 4), tzinfo=self.tz)
                q[int(t0.astimezone(UTC).timestamp())] = float(v)
        for a in self.areas:
            with a.lock:
                a.q, a.source = q, "fake"
                a.max_age = int(d.get("max_age_s", MAX_AGE))
                if not d.get("dead"):
                    a.fetched = time.time()
                elif not a.fetched:
                    a.fetched = time.time()
        log("fake file read: clock", self.now().strftime("%Y-%m-%d %H:%M"), "dead" if d.get("dead") else "")

    def touch_fake(self):
        """a living fake source keeps answering"""
        path = os.path.join(self.base, self.cfg["fake"])
        try:
            with open(path) as f:
                dead = json.load(f).get("dead")
        except (OSError, ValueError):
            return
        if not dead:
            for a in self.areas:
                a.fetched = time.time()

    # -- real sources
    def fetch_due(self):
        """at most one request per 65 s in total (the source allows one per minute per address)"""
        t = time.time()
        due = [a for a in self.areas if a.next_try <= t]
        if not due or t - getattr(self, "last_req", 0) < 65:
            return
        a = min(due, key=lambda x: x.next_try)
        self.last_req = t
        try:
            try:
                q, src = fetch_spot_hinta(a.name), "spot-hinta.fi"
            except Exception as e:
                if a.name != "FI":
                    raise
                log(a.name, "spot-hinta.fi failed (%s), trying porssisahko.net" % e)
                q, src = fetch_porssisahko(), "porssisahko.net"
            if not q:
                raise ValueError("empty answer")
            cut = t - 3 * 86400
            with a.lock:
                a.q.update(q)
                a.q = {k: v for k, v in a.q.items() if k > cut}
                a.fetched, a.source = t, src
            _, _, tomo = a.snapshot(self.now(), self.beat)
            local = self.now()
            # tomorrow missing in the afternoon: ask every 10 min, else once an hour
            a.next_try = t + (600 if (not tomo["ok"] and local.hour >= 13) else 3600)
            log(a.name, "fetched", len(q), "quarters from", src, "tomorrow", "yes" if tomo["ok"] else "no")
        except Exception as e:
            a.next_try = t + 300
            log(a.name, "fetch failed:", e)

    def run(self, once=False):
        mqtt = Mqtt(self.cfg["mqtt"]) if self.cfg.get("mqtt") and not once else None
        prefix = (self.cfg.get("mqtt") or {}).get("prefix", "spot")
        mb = None
        if self.cfg.get("modbus") and not once:
            mb = Modbus(int(self.cfg["modbus"].get("port", 1502)))
            mb.start()
        sent = {}
        while True:
            if self.fake:
                self.load_fake()
                self.touch_fake()
            else:
                self.fetch_due()
            if once and not self.fake and any(not a.fetched and a.next_try < time.time() + 1 for a in self.areas):
                time.sleep(1)
                continue
            self.beat += 1
            now = self.now()
            for unit, a in enumerate(self.areas, 1):
                o_now, o_today, o_tomo = a.snapshot(now, self.beat)
                regs = registers(o_now, o_today, o_tomo)
                o_up = {"area": a.name, "hour": o_now["hour"], "known": o_now["known"], "h": o_now.pop("_up")}
                if once:
                    print(json.dumps(o_now))
                    print(json.dumps({k: o_today[k] for k in ("date", "ok", "h", "rank")}))
                    continue
                if mb:
                    with mb.lock:
                        mb.units[unit] = regs
                if mqtt:
                    mqtt.publish("%s/%s/now" % (prefix, a.name), o_now)
                    mqtt.publish("%s/%s/points" % (prefix, a.name), points(o_now, o_today, o_tomo, o_up))
                    for key, o in (("today", o_today), ("tomorrow", o_tomo), ("upcoming", o_up)):
                        s = json.dumps(o)
                        if sent.get((a.name, key)) != s or self.beat % 360 == 0:
                            mqtt.publish("%s/%s/%s" % (prefix, a.name, key), o)
                            sent[(a.name, key)] = s
            if once:
                return
            time.sleep(10)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    with open(path) as f:
        cfg = json.load(f)
    Bridge(cfg, os.path.dirname(os.path.abspath(path))).run(once="--once" in sys.argv)


if __name__ == "__main__":
    main()
