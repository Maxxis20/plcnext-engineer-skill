# DH-ex2 — District heating substation, heating and domestic hot water

Description of operation. Source drawing: Finnish Energy, District Heating Substation Group, *Example connection 2: small
house connection to old one-family house without DHW circulation pipe* (publication K1/2013, p. 63). Controller: one Ouman Ouflex A base
unit, no expansion module. Generated plan: `plan.json` from `make_plan.py` (do not edit the JSON by hand). Page layout:
`layout.json` (hand layout, see `ouflex/ouflayout.py`, `layout_manual`).

## 1. Purpose

Two control loops, as in the drawing:

- **TC1, domestic hot water.** Control valve TV1 keeps the hot water temperature TE1 at the set value, 58 °C.
- **TC2, heating.** Control valve TV2 keeps the heating network supply temperature TE2A at a set value that follows the
  outdoor temperature TE2B (heating curve).

The pumps P1 (hot water) and P2 (heating network) are started by the controller, and the alarms (HS in the drawing) are
collected on one relay.

Four applications, run in this order:

| Order | Application | Content |
|---|---|---|
| 1 | `OUTDOOR` | TE2B range check, fallback value, slow filter |
| 2 | `TC1_DHW` | TE1 check, P1, PID → TV1, high / low temperature alarm |
| 3 | `TC2_HEAT` | summer stop, P2, TE2A check, heating curve, PID → TV2, high / low temperature alarm |
| 4 | `ALARM` | common alarm relay |

Every signal between applications is read by a later application, so it is from the same cycle.

## 2. I/O list

| Point | Signal | Type | Meaning |
|---|---|---|---|
| UI 1 | `TE2B_IN` outdoor temperature | NTC10 | °C; plausible −45…+50 °C |
| UI 2 | `TE1_IN` domestic hot water temperature | NTC10 | °C; plausible −20…+120 °C |
| UI 3 | `TE2A_IN` heating supply temperature | NTC10 | °C; plausible −20…+120 °C |
| AO 1 | `TV1_OUT` hot water control valve | 0–10 V | 0…100 % (0 % = closed) |
| AO 2 | `TV2_OUT` heating control valve | 0–10 V | 0…100 % (0 % = closed) |
| R1 | `P1_OUT` hot water pump | relay | 1 = run |
| R2 | `P2_OUT` heating network pump | relay | 1 = run |
| R3 | `ALARM_OUT` common alarm (HS) | relay | 1 = alarm |

## 3. Control functions

### 3.1 Outdoor temperature (OUTDOOR)

- TE2B is a fault when it reads below −45 °C or above +50 °C (`TE2B_FAULT`, at once).
- During a fault the set value `TOUT_FALLBACK` replaces the reading.
- The value goes through a first-order low-pass filter (`TOUT_FILT_T`); the result `TE2B_F` drives the heating curve and
  the summer stop.

### 3.2 Domestic hot water (TC1_DHW)

- TE1 is a fault below −20 °C or above +120 °C (`TE1_FAULT`).
- P1 runs while `DHW_ENABLE` = 1.
- The PID controller (`Pid` 5.1, heating direction) is enabled while P1 runs and TE1 is plausible. It keeps TE1 at
  `DHW_SP`. Disabled, its output is 0 %, so TV1 closes on a sensor fault.
- `DHW_TEMP_ALM`: TE1 above `DHW_HI_LIM` or below `DHW_LO_LIM` for `DHW_ALM_DLY` seconds, only while the controller is
  enabled.

### 3.3 Heating (TC2_HEAT)

- **Summer stop.** Heating stops when `TE2B_F` has been above `SUM_STOP` for `SUM_DLY` seconds and resumes at once when it
  is below `SUM_START`. A reset-dominant RS latch holds the state between the limits; overlapping limits give heating.
- P2 runs while `HEAT_ENABLE` = 1 and summer stop is not active.
- TE2A is a fault below −20 °C or above +120 °C (`TE2A_FAULT`).
- **Set value.** A three-point curve (`Curve_3p`) gives the supply set value `HEAT_SP` from `TE2B_F`: `CRV_N20`, `CRV_0`,
  `CRV_P20` at −20, 0, +20 °C outdoor, cut by `TS_MIN` and `TS_MAX` inside the block.
- The PID controller is enabled while P2 runs and TE2A is plausible. It keeps TE2A at `HEAT_SP`. Disabled, TV2 closes.
- `HEAT_TEMP_ALM`: TE2A above `HEAT_HI_LIM` or below `HEAT_LO_LIM` for `HEAT_ALM_DLY` seconds (always armed).

### 3.4 Common alarm (ALARM)

`ALARM_SUM` = OR of `TE2B_FAULT`, `TE1_FAULT`, `DHW_TEMP_ALM`, `TE2A_FAULT`, `HEAT_TEMP_ALM`; it drives R3. Alarms do not
latch and there is no acknowledgement.

## 4. Set values

| Name | Unit | Default | Min | Max | Meaning |
|---|---|---|---|---|---|
| `TOUT_FALLBACK` | °C | 0.0 | −30 | 20 | Outdoor value used while TE2B is faulty |
| `TOUT_FILT_T` | s | 900 | 10 | 21600 | Outdoor filter time constant |
| `DHW_ENABLE` | – | 1 | 0 | 1 | Domestic hot water in use |
| `DHW_SP` | °C | 58.0 | 50 | 65 | Hot water set value |
| `DHW_PID_P` | °C | 60.0 | 2 | 500 | TC1 proportional band |
| `DHW_PID_I` | s | 15 | 5 | 300 | TC1 integral time |
| `DHW_HI_LIM` | °C | 65.0 | 55 | 90 | Hot water high alarm limit |
| `DHW_LO_LIM` | °C | 50.0 | 30 | 58 | Hot water low alarm limit |
| `DHW_ALM_DLY` | s | 300 | 10 | 3600 | Hot water alarm delay |
| `SUM_START` | °C | 16.0 | 0 | 30 | Heating resumes below this outdoor temperature |
| `SUM_STOP` | °C | 18.0 | 5 | 30 | Summer stop above this outdoor temperature |
| `SUM_DLY` | s | 3600 | 0 | 86400 | Summer stop delay |
| `HEAT_ENABLE` | – | 1 | 0 | 1 | Heating in use |
| `CRV_N20` / `CRV_0` / `CRV_P20` | °C | 58 / 41 / 20 | 10 | 95 | Supply set value at −20 / 0 / +20 °C outdoor |
| `TS_MIN` | °C | 18.0 | 10 | 50 | Minimum supply set value |
| `TS_MAX` | °C | 70.0 | 20 | 90 | Maximum supply set value |
| `HEAT_PID_P` | °C | 40.0 | 2 | 500 | TC2 proportional band |
| `HEAT_PID_I` | s | 60 | 5 | 300 | TC2 integral time |
| `HEAT_HI_LIM` | °C | 80.0 | 40 | 110 | Heating supply high alarm limit |
| `HEAT_LO_LIM` | °C | 8.0 | 2 | 30 | Heating supply low alarm limit |
| `HEAT_ALM_DLY` | s | 600 | 10 | 3600 | Heating supply alarm delay |

Fixed constants: sensor ranges above; PID dead band 0.5 °C, D = 0, control interval 1 s, output 0…100 %, Balance 0 %.
The PID tuning defaults are starting points only: the vendor text does not state the algorithm form.

## 5. Measurements and status points

| Name | Unit | Meaning |
|---|---|---|
| `TE2B`, `TE2B_F` | °C | Outdoor temperature, raw / filtered |
| `TE1` | °C | Hot water temperature |
| `TE2A` | °C | Heating supply temperature |
| `HEAT_SP` | °C | Heating supply set value |
| `TV1`, `TV2` | % | Valve commands |
| `P1_RUN`, `P2_RUN` | – | Pump commands |
| `SUMMER` | – | Summer stop active |
| `TE2B_FAULT`, `TE1_FAULT`, `TE2A_FAULT`, `DHW_TEMP_ALM`, `HEAT_TEMP_ALM`, `ALARM_SUM` | – | Alarms |

## 6. Modbus map rule

All points are Holding registers: set values 1000 + n, analog measurements 1100 + n, binary status 1150 + n
(n = declaration order). The exported document shows each number + 1.

## 7. Deliberately left out

- Pump exercise in summer stop, valve fault position, set value consistency checks, set value offset, sensor fault delay
  (all in `examples/dh2`).
- Supply deviation alarm (replaced by high / low limits).
- Time programs, night setback, room compensation.
- Alarm objects, acknowledgement, latching.
- Pressure switch PS, PI / TI gauges and the energy meter of the drawing: local instruments, not wired to the controller.
- Hot water anticipation (flow or primary feed-forward): plain PI on TE1.

## 8. What rests on documentation only

Block choices cite the vendor sentence in `make_plan.py` (`why=`). Nothing here is bench-tested on a real Ouflex A. Open points are the same as in `examples/dh2/DESCRIPTION.md` section 11: NTC reading on an open or
short circuit, `Curve_3p` outside −20…+20 °C, `Pid` algorithm form, `SignalFilter` first-scan value, `RS_FlipFlop` state
after power-up, AO scaling 0…100 % = 0…10 V.
