#!/usr/bin/env python3
"""Writes program.json and src/MAIN for the spot price project: one WORD port per register of the price bridge
(../bridge/spotd.py, ../bridge/CONTRACT.md), the conversion to c/kWh, the plan (cheapest consecutive hours) and one
price-controlled load. Run after changing the bridge address or the unit id (= area):  python3 gen.py"""
import json
import os

BRIDGE_IP, BRIDGE_PORT, UNIT = "192.168.1.50", 1502, 1      # unit id = position of the area in the bridge's list
HERE = os.path.dirname(os.path.abspath(__file__))

# The firmware's client takes 32 registers per server ("too many function codes (32)" above that):
# 8 status registers and the 24 upcoming hours (500 = the running hour).
HEAD = [("VALID", 0), ("BEAT", 1), ("HOUR", 2), ("TOTAL", 6), ("RANK", 7), ("TOMO_OK", 15), ("AGE", 16), ("KNOWN", 17)]
regs = [("R_" + n, a) for n, a in HEAD] + [("U%02d" % h, 500 + h) for h in range(24)]

prog = {
    "name": "SPOT", "base": "AXCF2152-2026.0-MBTCP",
    "pous": [{"name": "MAIN", "kind": "Program"}],
    "tasks": [{"name": "Cyclic100", "interval_ms": 100, "instances": [{"name": "M", "program": "MAIN"}]}],
    "target": {"ip": "192.168.1.10"},
    "hmi": "hmi.py", "hmi_server": {"login": False, "rest": True},
    "modbus_tcp": {"ip": BRIDGE_IP, "unit": UNIT, "port": BRIDGE_PORT,
                   "registers": [{"name": n, "fc": 3, "address": a} for n, a in regs]},
    "io": dict([("M." + n, n + "_input") for n, _ in regs] +
               [("M.MB_STATE", "STATE"), ("M.MB_OFFLINE", "OFFLINE_CNT"), ("M.MB_EXC", "EXCEPTION_CNT")]),
}
json.dump(prog, open(os.path.join(HERE, "program.json"), "w"), indent=1)

H = range(24)
var = ["VAR", "    (* registers of the price bridge, signed, price x 100 *)"]
var += ["    %s : WORD { InputPort };" % n for n, _ in regs]
var += ["""    MB_STATE : UDINT { InputPort, EHMI };
    MB_OFFLINE : UDINT { InputPort, EHMI };
    MB_EXC : UDINT { InputPort, EHMI };
    TS : REAL := 0.1;
    I : INT;
    J : INT;
    X : REAL;
    SUM : REAL;
    BEST : REAL;
    BI : INT;
    A : ARRAY[0..23] OF INT;              (* upcoming hours, raw; 0 = the running hour *)
    PLA : ARRAY[0..23] OF BOOL;           (* the load may run in this hour *)
    SEC_T : REAL;
    (* price data *)
    VALID : BOOL { EHMI };                (* prices usable: link up, bridge says valid, beat moves *)
    LINK : BOOL { EHMI };
    SRC_VALID : BOOL { EHMI };
    BEAT : INT { EHMI };
    BEAT_OLD : INT;
    BEAT_T : REAL { EHMI };               (* s since the beat last moved *)
    BEAT_OK : BOOL { EHMI };
    HOUR : INT { EHMI };
    HOUR_OLD : INT := -1;
    HCNT : DINT { EHMI };                 (* hours counted since start: the plan's clock *)
    KNOWN : INT { EHMI };                 (* upcoming hours with a price, at most 24 here *)
    PRICE : REAL { EHMI };                (* c/kWh without VAT, running hour *)
    PRICE_TOTAL : REAL { EHMI };
    RANK : INT { EHMI };                  (* 1 = cheapest hour of the day *)
    P_AVG : REAL { EHMI };                (* of the upcoming hours *)
    P_MIN : REAL { EHMI };
    P_MAX : REAL { EHMI };
    TOMO_OK : BOOL { EHMI };
    AGE_MIN : INT { EHMI };
    SCALE : REAL := 10.0 { EHMI };        (* top of the bars *)
    (* operator *)
    MODE : INT := 2 { EHMI };             (* 0 off, 1 on (thermostat only), 2 price control *)
    STRAT : INT := 0 { EHMI };            (* 0 cheapest consecutive N_BLOCK hours, 1 the N_CHEAP cheapest hours of the day *)
    N_BLOCK : INT := 5 { EHMI };
    N_CHEAP : INT := 6 { EHMI };
    LIM_HIGH : REAL := 20.0 { EHMI };     (* never above this price *)
    LIM_LOW : REAL := 1.0 { EHMI };       (* always at or below this price, with the boost setpoint *)
    SP : REAL := 60.0 { EHMI };
    SP_BOOST : REAL := 75.0 { EHMI };
    T_MIN : REAL := 45.0 { EHMI };        (* below this the tank heats whatever the price *)
    REPLAN : BOOL { EHMI };               (* button: plan again now *)
    (* plan: one block, frozen until it has run *)
    PLAN_OK : BOOL { EHMI };
    PS : DINT;                            (* start of the block, in HCNT hours *)
    PN : INT { EHMI };                    (* its length *)
    PEND : DINT;                          (* end of the known hours when the plan was made *)
    P_BLOCK : REAL { EHMI };              (* average price of the block *)
    START_IN : INT { EHMI };              (* hours until the block starts; 0 = it runs *)
    START_AT : INT { EHMI };              (* hour of the day it starts *)
    LEFT_H : INT { EHMI };                (* hours of the block left, the running one included *)
    IN_BLOCK : BOOL { EHMI };
    NEED : BOOL;
    (* load *)
    RELEASE : BOOL { EHMI };
    REASON : INT { EHMI };                (* 0 off, 1 on by hand, 2 cheap hour, 3 very cheap: boost, 4 blocked: price above limit,
                                             5 waiting for a cheaper hour, 6 no price data: normal operation, 7 tank cold *)
    SP_ACT : REAL { EHMI };
    TH : BOOL;
    HEAT : BOOL { EHMI };
    TANK : REAL := 55.0 { EHMI };         (* simulated *)
    AL_NOPRICE : BOOL { EHMI };
    AL_T : REAL;
    SIM_FAST : BOOL { EHMI };             (* test: tank 20 x faster *)
    SIMK : REAL;"""]
for h in H:
    var += ["    PT%02d : REAL { EHMI };" % h, "    BT%02d : REAL { EHMI };" % h, "    PL%02d : BOOL { EHMI };" % h, "    HL%02d : INT { EHMI };" % h]
var += ["END_VAR", ""]

code = ["(* generated by gen.py; the firmware's Modbus TCP client fills the WORD ports *)"]
code += ["A[%d] := TO_INT(U%02d);" % (h, h) for h in H]
code.append("""
(* is the price usable? *)
LINK := MB_STATE = 1;
SRC_VALID := TO_INT(R_VALID) = 1;
BEAT := TO_INT(R_BEAT);
IF BEAT <> BEAT_OLD THEN BEAT_T := 0.0; BEAT_OLD := BEAT; ELSIF BEAT_T < 9999.0 THEN BEAT_T := BEAT_T + TS; END_IF;
BEAT_OK := BEAT_T < 60.0;
VALID := LINK AND SRC_VALID AND BEAT_OK AND A[0] <> -32768;

HOUR := TO_INT(R_HOUR);
IF HOUR < 0 OR HOUR > 23 THEN HOUR := 0; VALID := FALSE; END_IF;
PRICE_TOTAL := TO_REAL(TO_INT(R_TOTAL)) / 100.0;
RANK := TO_INT(R_RANK);
TOMO_OK := TO_INT(R_TOMO_OK) = 1;
AGE_MIN := TO_INT(R_AGE);
IF A[0] = -32768 THEN PRICE := 0.0; ELSE PRICE := TO_REAL(A[0]) / 100.0; END_IF;

N_BLOCK := LIMIT(1, N_BLOCK, 12);
N_CHEAP := LIMIT(0, N_CHEAP, 24);
IF MODE < 0 OR MODE > 2 THEN MODE := 0; END_IF;
IF STRAT < 0 OR STRAT > 1 THEN STRAT := 0; END_IF;

(* the plan's clock: one step per hour. A jump of the clock (not the next hour) throws the plan away. *)
IF VALID AND HOUR <> HOUR_OLD THEN
    IF HOUR_OLD >= 0 AND HOUR <> (HOUR_OLD + 1) MOD 24 THEN PLAN_OK := FALSE; END_IF;
    HCNT := HCNT + 1;
    HOUR_OLD := HOUR;
END_IF;

SEC_T := SEC_T + TS;
IF SEC_T >= 1.0 THEN
    SEC_T := 0.0;
    (* known hours in a row, and their figures *)
    KNOWN := 0; SUM := 0.0; P_MIN := 999.0; P_MAX := -999.0; SCALE := 10.0;
    FOR I := 0 TO 23 DO
        IF A[I] <> -32768 AND KNOWN = I AND I < TO_INT(R_KNOWN) THEN
            KNOWN := I + 1;
            X := TO_REAL(A[I]) / 100.0;
            SUM := SUM + X;
            IF X > SCALE THEN SCALE := X; END_IF;
            IF X < P_MIN THEN P_MIN := X; END_IF;
            IF X > P_MAX THEN P_MAX := X; END_IF;
        END_IF;
    END_FOR;
    IF KNOWN > 0 THEN P_AVG := SUM / TO_REAL(KNOWN); ELSE P_AVG := 0.0; P_MIN := 0.0; P_MAX := 0.0; END_IF;

    (* Cheapest consecutive N_BLOCK hours among the known ones. The block is frozen once chosen, or the search
       would push it ahead for ever. Planned again: when it has run, when its length is changed, when more hours
       became known before it started (tomorrow's prices arrived), on the button. *)
    IF VALID THEN
        NEED := REPLAN OR NOT PLAN_OK OR PN <> N_BLOCK;
        IF PLAN_OK THEN
            IF HCNT >= PS + TO_DINT(PN) THEN NEED := TRUE; END_IF;
            IF HCNT < PS AND HCNT + TO_DINT(KNOWN) > PEND THEN NEED := TRUE; END_IF;
        END_IF;
        IF NEED THEN
            REPLAN := FALSE;
            PLAN_OK := FALSE;
            IF KNOWN >= N_BLOCK THEN
                BEST := 1.0E9; BI := 0;
                FOR I := 0 TO KNOWN - N_BLOCK DO
                    SUM := 0.0;
                    FOR J := I TO I + N_BLOCK - 1 DO SUM := SUM + TO_REAL(A[J]); END_FOR;
                    IF SUM < BEST THEN BEST := SUM; BI := I; END_IF;
                END_FOR;
                PS := HCNT + TO_DINT(BI);
                PN := N_BLOCK;
                PEND := HCNT + TO_DINT(KNOWN);
                P_BLOCK := BEST / TO_REAL(N_BLOCK) / 100.0;
                START_AT := (HOUR + BI) MOD 24;
                PLAN_OK := TRUE;
            END_IF;
        END_IF;
    END_IF;
    IF PLAN_OK THEN
        START_IN := MAX(0, TO_INT(PS - HCNT));
        IN_BLOCK := HCNT >= PS AND HCNT < PS + TO_DINT(PN);
        IF IN_BLOCK THEN LEFT_H := TO_INT(PS + TO_DINT(PN) - HCNT); ELSE LEFT_H := PN; END_IF;
    ELSE
        START_IN := 0; IN_BLOCK := FALSE; LEFT_H := 0;
    END_IF;

    (* which of the upcoming hours the load may run in (for the graph) *)
    FOR I := 0 TO 23 DO
        X := TO_REAL(A[I]) / 100.0;
        PLA[I] := FALSE;
        IF I < KNOWN THEN
            IF STRAT = 0 AND PLAN_OK THEN
                PLA[I] := HCNT + TO_DINT(I) >= PS AND HCNT + TO_DINT(I) < PS + TO_DINT(PN) AND X <= LIM_HIGH;
            END_IF;
            IF X <= LIM_LOW THEN PLA[I] := TRUE; END_IF;
        END_IF;
    END_FOR;
    IF STRAT = 1 AND KNOWN > 0 THEN
        PLA[0] := (RANK >= 1 AND RANK <= N_CHEAP AND PRICE <= LIM_HIGH) OR PRICE <= LIM_LOW;
    END_IF;
END_IF;
""")
for h in H:
    code.append("IF %d < KNOWN THEN PT%02d := TO_REAL(A[%d]) / 100.0; ELSE PT%02d := 0.0; END_IF; "
                "BT%02d := LIMIT(0.0, PT%02d / SCALE * 100.0, 100.0); PL%02d := PLA[%d]; HL%02d := (HOUR + %d) MOD 24;"
                % (h, h, h, h, h, h, h, h, h, h))
code.append("""
(* the load: a storage tank heater. Without usable prices it runs as if there were no price control. *)
SP_ACT := SP;
IF MODE = 0 THEN
    RELEASE := FALSE; REASON := 0;
ELSIF MODE = 1 THEN
    RELEASE := TRUE; REASON := 1;
ELSIF NOT VALID THEN
    RELEASE := TRUE; REASON := 6;
ELSIF PRICE <= LIM_LOW THEN
    RELEASE := TRUE; REASON := 3; SP_ACT := SP_BOOST;
ELSIF PRICE > LIM_HIGH THEN
    RELEASE := FALSE; REASON := 4;
ELSIF (STRAT = 0 AND IN_BLOCK) OR (STRAT = 1 AND RANK >= 1 AND RANK <= N_CHEAP) THEN
    RELEASE := TRUE; REASON := 2;
ELSE
    RELEASE := FALSE; REASON := 5;
END_IF;
IF MODE = 2 AND NOT RELEASE AND TANK < T_MIN THEN RELEASE := TRUE; REASON := 7; END_IF;

IF TANK < SP_ACT - 3.0 THEN TH := TRUE; END_IF;
IF TANK >= SP_ACT THEN TH := FALSE; END_IF;
HEAT := RELEASE AND TH;

(* simulated tank: heats 0.6 K/min, loses 0.15 K/min *)
IF SIM_FAST THEN SIMK := 20.0; ELSE SIMK := 1.0; END_IF;
IF HEAT THEN TANK := TANK + 0.01 * TS * SIMK; END_IF;
TANK := TANK - 0.0025 * TS * SIMK;
IF TANK < 10.0 THEN TANK := 10.0; END_IF;

(* alarm: no usable price for 10 s (the beat watchdog itself takes 60 s) *)
IF VALID THEN AL_T := 0.0; ELSIF AL_T < 100.0 THEN AL_T := AL_T + TS; END_IF;
AL_NOPRICE := AL_T >= 10.0;
""")
os.makedirs(os.path.join(HERE, "src", "MAIN"), exist_ok=True)
open(os.path.join(HERE, "src", "MAIN", "Variables.var"), "w").write("\n".join(var))
open(os.path.join(HERE, "src", "MAIN", "Code.st"), "w").write("\n".join(code))
print(len(regs), "registers")
