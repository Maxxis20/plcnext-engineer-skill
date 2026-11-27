# Spot price bridge: what it serves

One small service fetches day-ahead electricity prices and serves them in two forms that every controller here can
read: retained MQTT messages and a Modbus TCP server. A controller project selects the area by the topic or by the
Modbus unit id. The bridge itself is `spotd.py` in this folder; this file is the agreement.

## Sources

| Source | Areas | Notes |
|---|---|---|
| `api.spot-hinta.fi` (default) | DK1 DK2 EE FI LT LV NO1-NO5 SE1-SE4 | open, no key; 15 min or 60 min; 1 request per minute per address; EUR/kWh without and with tax |
| `api.porssisahko.net` | FI | open, no key; c/kWh **with** Finnish VAT; fallback for FI |
| ENTSO-E Transparency Platform | every European bidding zone | official source; needs a free token (registration); **not built** |
| nordpool.cc | - | a web site, no interface; not affiliated with Nord Pool; not read by programs |
| `fake` | any | prices from a file, clock can be set: for tests |

## Values

- Price unit: **c/kWh, without VAT**. The bridge can add `vat_pct` and a fixed `add` (margin, transfer) per area; the
  `*_total` values then carry the result. Prices can be negative.
- Hourly values are the control basis (average of the four quarters). Quarter values are served too.
- Hours are the **local time of the site** (bridge setting `tz`, e.g. `Europe/Helsinki`), index 0 = 00:00-01:00.
  On the day the clocks change the missing hour repeats its neighbour, the double hour is averaged.
- `rank`: 1 = cheapest hour of the local day, 24 = dearest. "Run in the N cheapest hours" = `rank <= N`.
- Tomorrow's prices arrive in the afternoon (about 14:00 Finnish time). Before that `tomorrow_ok` = 0.
- The bridge asks the source once at start, then every day at 14:15 Finnish time, and every 10 minutes after
  that until tomorrow's prices are there (and every 5 minutes while today's prices are missing).
- `valid` = 1 only when today's prices are present and the source answered within the last 30 hours. `beat` counts up
  by one every 10 s. **A controller must treat `valid` = 0 or a `beat` that stands still for 60 s as "no price"
  and fall back to normal operation** (no blocking, no boosting).

## MQTT (retained, QoS 0)

Topic prefix `spot/<AREA>/`, e.g. `spot/FI/`.

`spot/<AREA>/now`, every 10 s, a flat object (easy to pick numbers from by key):

```json
{"area":"FI","valid":1,"beat":1234,"hour":14,"quarter":58,
 "now":12.34,"now15":11.90,"now_total":15.49,
 "rank":17,"avg":9.87,"min":0.52,"max":31.10,
 "next1":13.01,"next2":14.20,"next3":10.00,
 "cheap3_in":5,"tomorrow_ok":1,"known":34,"age_s":812,
 "ts":"2026-11-27T12:00:00Z","unit":"c/kWh","source":"spot-hinta.fi"}
```

- `hour` 0..23 and `quarter` 0..95: the running local hour and quarter of the day.
- `blk1`..`blk12` (not in the example above): hours until the start of the cheapest block of N consecutive hours
  among the upcoming ones; -1 = fewer than N hours known. The value moves when new prices arrive and can push the
  block ahead for ever: **the controller freezes its block** (latch the start once chosen, run N hours, then look
  again).
- `next1..3`: the next three hours. `cheap3_in`: hours until the start of the cheapest 3-hour block that still
  lies ahead in the known prices (0 = it runs now).

`spot/<AREA>/today` and `spot/<AREA>/tomorrow`, on change:

```json
{"area":"FI","date":"2026-11-27","ok":1,"h":[24 numbers],"rank":[24 numbers],"q":[96 numbers]}
```

`tomorrow` with `"ok":0` and empty lists until the prices exist.

`spot/<AREA>/upcoming`, on change (every hour): the hours from the running one onward, as far as they are known
without a gap (to the end of today, or of tomorrow once published). `known` (also in `now`) = their number, 1..48.

```json
{"area":"FI","hour":14,"known":34,"h":[34 numbers]}
```

`spot/<AREA>/points`, every 10 s with `now`: everything as one list of `{"id", "v"}`, for clients that take one
value pointer and write each item to the point named by its id. Ids carry no area: the topic selects it. No value = 0.

```json
[{"id":"spot.valid","v":1},{"id":"spot.beat","v":1234},{"id":"spot.now","v":12.34}, ...]
```

- `spot.<key>` for every numeric key of `now` (valid, beat, hour, quarter, now, now15, now_total, rank, avg, min,
  max, next1..3, cheap3_in, tomorrow_ok, known, age_s, blk1..blk12).
- `spot.h0`..`spot.h23` today's hours, `spot.r0`..`spot.r23` their rank, `spot.t0`..`spot.t23` tomorrow's hours
  (0 while `tomorrow_ok` = 0), `spot.u0`..`spot.u47` the upcoming hours (`u0` = the running hour; 0 beyond `known`).
- `spot.q0`..`spot.q95` the running quarter and the upcoming ones (0 beyond `spot.known15`, their number).

`spot/<AREA>/flat60` and `spot/<AREA>/flat15`, every 10 s with `now`: one flat object each, for programs that
pick a number by its key but cannot walk a list (a PLC program with a simple JSON search). The same keys in both;
the topic chooses hourly or 15 minute prices. A "slot" is an hour (`flat60`) or a quarter (`flat15`).

```json
{"valid":1,"beat":1234,"res":15,"slot":58,"hour":14,"now":11.9,"now_total":14.93,"rank":17,
 "tomorrow_ok":1,"age_s":812,"known":96,"p0":11.9,"p1":12.4, ...}
```

- `res` 60 or 15; `slot` = the running slot of the local day (0..23 or 0..95); `now` = its price.
- `p0`..: the running slot and the upcoming ones as far as known, at most 48 hours (`flat60`) or 96 quarters =
  24 hours (`flat15`); `known` = their number; keys beyond it are left out.
- `rank` is the hourly rank of the day in both. About 0.9 KB (`flat60`) and 1.5 KB (`flat15`).

## Modbus TCP (port 1502)

Unit id = position of the area in the bridge's list (1 = first area). Holding registers (function 3), also readable
as input registers (function 4). All values **signed 16 bit, price × 100** (0.01 c/kWh). `-32768` = no value.
Addresses are zero-based.

| Register | Value |
|---|---|
| 0 | valid (0 / 1) |
| 1 | beat (0..32767, wraps) |
| 2 | hour 0..23 |
| 3 | quarter 0..95 |
| 4 | now (hour price) |
| 5 | now15 (quarter price) |
| 6 | now_total |
| 7 | rank 1..24 |
| 8 | avg of today |
| 9 | min of today |
| 10 | max of today |
| 11..13 | next1..next3 |
| 14 | cheap3_in (hours) |
| 15 | tomorrow_ok (0 / 1) |
| 16 | age of the source data, minutes |
| 17 | known: number of upcoming hours with a price, counted from the running hour (1..48) |
| 18 | known15: number of upcoming quarters with a price, counted from the running quarter (1..96) |
| 19, 20 | lowest and highest price of the upcoming 24 hours (500..523), known ones only; `-32768` if none |
| 21, 22 | lowest and highest price of the upcoming 24 quarters (700..723), known ones only; `-32768` if none |
| 100..123 | today, hours 0..23 |
| 130..153 | rank of today's hours 0..23 |
| 200..223 | tomorrow, hours 0..23 |
| 300..395 | today, quarters 0..95 |
| 400..495 | tomorrow, quarters 0..95 |
| 500..547 | upcoming hours: 500 = the running hour, 501 = the next, ... ; `-32768` beyond `known` |
| 700..795 | upcoming quarters: 700 = the running quarter, 701 = the next, ... ; `-32768` beyond `known15` |
| 600..611 | hours until the start of the cheapest block of N consecutive hours among the upcoming ones, N = 1..12 (600 = N 1); 0 = it starts in the running hour; `-32768` = fewer than N hours known |

## Tests the bridge supports

`fake` source with a price file and a settable clock, so a consumer can be tested on fixed numbers: a normal day, a
day with negative prices, tomorrow missing, source dead (`valid` drops to 0), bridge stopped (`beat` stands still).
