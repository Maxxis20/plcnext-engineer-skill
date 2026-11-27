# spot-price: electricity spot price in a controller program

AXC F 2152 (firmware 2026.0) gets day-ahead electricity prices from a small bridge on another machine, runs one
load by them (a simulated storage tank heater) and shows them on a page: the price now, the upcoming 24 hours
as bars, the plan and its settings. Proven on a controller with fixed test prices and with live prices.

![page](shot-live.png)

## How the price gets in

The controller does not reach the internet. `bridge/spotd.py` runs on a machine that does: it fetches the
prices, works out rank, the upcoming hours and the cheapest blocks, and serves plain numbers as a Modbus TCP
server (and as MQTT messages for other systems). The controller's own Modbus TCP client reads them: nothing to
program for the protocol. Bridge: `bridge/README.md`; every register and topic: `bridge/CONTRACT.md`.

- **32 registers** are read: the client refuses more per server ("The Modbus server has too many function
  codes (32)"). 8 status registers (valid, beat, hour, price with tax, rank, tomorrow published, age, number of
  known hours) and the 24 upcoming hours (500..523, 500 = the running hour), signed, price x 100.
- **Area** (FI, SE3, NO1, ...) = the unit id in `gen.py` = position of the area in the bridge's list. Not
  changeable at run time on this road.
- **Price usable** = connection up (`STATE`), bridge says valid, its beat moved within the last 60 s. Otherwise
  the price control is off, the heater runs on its thermostat alone, alarm after 10 s.

## How the price is used

- **Cheapest consecutive hours** (setting, 1..12 h, default 5): the cheapest block among the known upcoming
  hours. The block is **frozen once chosen**: a search repeated every hour over a moving window can push the
  start ahead for ever. Planned again when the block has run, when its length is changed, when more hours became
  known before it started (tomorrow's prices arrive in the afternoon), when the clock jumps, and on the button.
  A block that already runs is kept even if tomorrow's prices would give a cheaper one.
- **Cheapest hours of the day** (the other setting): rank of the running hour (from the bridge, per calendar
  day) <= N.
- In both: never above a price limit (an hour above it is blocked even inside the block); always at or below a
  low limit, then with the boost setpoint (negative prices). Tank below its minimum: heats whatever the price.
- The state text names the reason: cheap hour, very cheap (boost), blocked by the limit, waiting, no price data,
  tank cold.

## Files

| File | |
|---|---|
| `gen.py` | writes `program.json` and `src/MAIN` (one WORD port per register, the plan, the load). Bridge address, port, unit id and the controller's address are at its top |
| `hmi.py` | the page; bars with `rect(..., grow=(variable, 0, 100), axis="y")` |
| `bridge/` | the bridge, its agreement, a config example |

```bash
python3 examples/spot-price/gen.py
scripts/pxe.sh build examples/spot-price && scripts/pxe.sh open examples/spot-price/SPOT.plcnx2 && scripts/pxe.sh write
```

The base project must hold the Modbus TCP client with one server and the service must be on:
`../../reference/modbus-tcp.md`.

## Tests on the controller, prices from the bridge's fake source

| Test | Result |
|---|---|
| Normal day, 13:30, tomorrow known | block of 5 h planned at 02:00 (average 4.00 c/kWh), waiting; `shot-waiting.png` |
| Hour 13 -> 14 | plan kept, starts in 12 h |
| Tomorrow missing (11 hours known) | block among today's hours, starts at once |
| Clock inside the block | released, cheap hour; `shot-block.png` |
| Negative price (-1.5) | released, boost setpoint; `shot-negative.png` |
| 25 c/kWh, limit 20 | blocked |
| Source dead (valid 0) | normal operation, alarm; `shot-nodata.png`; price control again when it returns |
| Bridge stopped | connection lost at once, alarm after 10 s, beat watchdog after 60 s; recovers when it is back |

Not tested: a whole day in real time (the tests moved the bridge's clock), the change of the clocks in spring
and autumn, the MQTT road into this controller program (blocks for it: `../mqtt-subscribe`).

## Found on the way

- An initial value goes before the flags: `X : REAL := 1.0 { EHMI };` (the other order: "';' expected").
- One variable per line in `Variables.var`: a second declaration on the same line is dropped without a message.
- A button's step for a REAL variable must be a whole number: 0.5 is refused when the page is built.
