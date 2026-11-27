#!/usr/bin/env python3
"""Writes program.json and src/MAIN for the spot price project (MQTT road): subscribes to the price bridge's flat
topic (bridge/CONTRACT.md: spot/<AREA>/flat60 or flat15), takes the numbers out of the JSON, plans the cheapest
consecutive hours and runs one price-controlled load. Area and resolution (1 h / 15 min) are chosen on the page.
Run after changing the broker address or the controller's:  python3 gen.py"""
import json
import os

BROKER_IP, BROKER_PORT, PLC_IP, NAME = "192.168.1.50", 1883, "192.168.1.10", "SPOT"
AREAS = ["FI", "EE", "LV", "LT", "SE1", "SE2", "SE3", "SE4", "NO1", "NO2", "NO3", "NO4", "NO5", "DK1", "DK2"]
NS = 96                                   # slots kept: 96 quarters = 24 h, or 48 hours
HEAD = ["valid", "beat", "slot", "hour", "now_total", "rank", "tomorrow_ok", "known"]
HERE = os.path.dirname(os.path.abspath(__file__))

prog = {
    "name": NAME, "base": "AXCF2152-2026.0",
    "pous": [{"name": "FB_JSON_NUM", "kind": "FunctionBlock"}, {"name": "FB_MQTT_SUB", "kind": "FunctionBlock"},
             {"name": "MAIN", "kind": "Program"}],
    "tasks": [{"name": "Cyclic100", "interval_ms": 100, "instances": [{"name": "M", "program": "MAIN"}]}],
    "target": {"ip": PLC_IP},
    "hmi": "hmi.py", "hmi_server": {"login": False, "rest": True},
}
json.dump(prog, open(os.path.join(HERE, "program.json"), "w"), indent=1)

var = """VAR
    TS : REAL := 0.1;
    MQ : FB_MQTT_SUB;
    JN : FB_JSON_NUM;
    BUF : ARRAY[0..2047] OF BYTE;         (* the message being read *)
    BLEN : INT;
    PARSING : BOOL;
    PK : INT;                             (* key being read: 0..7 head, 8.. = p0.. *)
    PKN : INT;
    KEY : STRING;
    DIG : STRING := '0123456789';
    HV : ARRAY[0..7] OF REAL;             (* head values of the message being read *)
    HF : ARRAY[0..7] OF BOOL;
    TA : ARRAY[0..95] OF REAL;            (* prices of the message being read *)
    TKNOWN : INT;
    A : ARRAY[0..95] OF REAL;             (* prices in use: 0 = the running slot *)
    PLA : ARRAY[0..95] OF BOOL;           (* the load may run in this slot *)
    I : INT;
    J : INT;
    X : REAL;
    SUM : REAL;
    BEST : REAL;
    BI : INT;
    NB : INT;                             (* block length in slots *)
    SPH : INT;                            (* slots per hour: 1 or 4 *)
    SPD : INT;                            (* slots per day: 24 or 96 *)
    SEC_T : REAL;
    (* selection *)
    AREA : INT := 0 { EHMI };             (* index into the area list, see gen.py *)
    AREA_OLD : INT := -1;
    AREA_S : STRING;
    RES15 : BOOL { EHMI };                (* FALSE: hourly prices, TRUE: 15 minute prices *)
    RES_OLD : BOOL;
    TOPIC : STRING[120];
    SUB_OFF : REAL;                       (* s the subscription is still held off after a change *)
    (* connection and data *)
    MQ_CONNECTED : BOOL { EHMI };
    MQ_STATE : INT { EHMI };
    MQ_MSGS : UDINT { EHMI };
    MQ_RECONN : UDINT { EHMI };
    MQ_LEN : INT { EHMI };
    DATA_OK : BOOL { EHMI };              (* a complete message of the chosen topic has been read *)
    SRC_VALID : BOOL { EHMI };
    VALID : BOOL { EHMI };                (* prices usable: connected, bridge says valid, beat moves *)
    BEAT : INT { EHMI };
    BEAT_OLD : INT;
    BEAT_T : REAL { EHMI };
    BEAT_OK : BOOL { EHMI };
    SLOT : INT { EHMI };                  (* running slot of the day *)
    SLOT_OLD : INT := -1;
    SCNT : DINT;                          (* slots counted since start: the plan's clock *)
    HOUR : INT { EHMI };
    KNOWN : INT { EHMI };                 (* slots with a price, the running one included *)
    KNOWN_H : REAL { EHMI };
    PRICE : REAL { EHMI };                (* c/kWh without VAT, running slot *)
    PRICE_TOTAL : REAL { EHMI };
    RANK : INT { EHMI };                  (* hourly rank of the day, 1 = cheapest *)
    P_AVG : REAL { EHMI };
    P_MIN : REAL { EHMI };
    P_MAX : REAL { EHMI };
    TOMO_OK : BOOL { EHMI };
    SCALE : REAL := 10.0 { EHMI };
    UNIT_MWH : BOOL { EHMI };             (* page shows EUR/MWh instead of c/kWh (1 c/kWh = 10 EUR/MWh) *)
    UK : REAL;
    D_PRICE : REAL { EHMI };              (* the D_ values are for the page, in the chosen unit *)
    D_TOTAL : REAL { EHMI };
    D_AVG : REAL { EHMI };
    D_MIN : REAL { EHMI };
    D_MAX : REAL { EHMI };
    D_BLOCK : REAL { EHMI };
    D_SCALE : REAL { EHMI };
    D_HIGH : REAL { EHMI };
    D_LOW : REAL { EHMI };
    (* operator *)
    MODE : INT := 2 { EHMI };             (* 0 off, 1 on (thermostat only), 2 price control *)
    STRAT : INT := 0 { EHMI };            (* 0 cheapest consecutive N_BLOCK hours, 1 the N_CHEAP cheapest hours of the day *)
    N_BLOCK : INT := 5 { EHMI };          (* hours *)
    N_CHEAP : INT := 6 { EHMI };
    LIM_HIGH : REAL := 20.0 { EHMI };
    LIM_LOW : REAL := 1.0 { EHMI };
    SP : REAL := 60.0 { EHMI };
    SP_BOOST : REAL := 75.0 { EHMI };
    T_MIN : REAL := 45.0 { EHMI };
    REPLAN : BOOL { EHMI };
    (* plan: one block, frozen until it has run *)
    PLAN_OK : BOOL { EHMI };
    PS : DINT;
    PN : INT;
    PEND : DINT;
    P_BLOCK : REAL { EHMI };
    START_IN : REAL { EHMI };             (* hours until the block starts *)
    START_AT_H : INT { EHMI };
    START_AT_M : INT { EHMI };
    LEFT_H : REAL { EHMI };
    IN_BLOCK : BOOL { EHMI };
    NEED : BOOL;
    (* load *)
    RELEASE : BOOL { EHMI };
    REASON : INT { EHMI };
    SP_ACT : REAL { EHMI };
    TH : BOOL;
    HEAT : BOOL { EHMI };
    TANK : REAL := 55.0 { EHMI };
    AL_NOPRICE : BOOL { EHMI };
    AL_T : REAL;
    SIM_FAST : BOOL { EHMI };
    SIMK : REAL;
""".split("\n")
for i in range(NS):
    var += ["    BT%02d : REAL { EHMI };" % i, "    PL%02d : BOOL { EHMI };" % i,
            "    NG%02d : BOOL { EHMI };" % i, "    HL%02d : INT { EHMI };" % i]
var += ["END_VAR", ""]

code = ["(* generated by gen.py *)", "CASE AREA OF"]
code += ["    %d: AREA_S := '%s';" % (i, a) for i, a in enumerate(AREAS)]
code += ["ELSE", "    AREA := 0; AREA_S := '%s';" % AREAS[0], "END_CASE;"]
code.append("""
(* area or resolution changed: drop the data and the plan, subscribe again to the other topic *)
IF AREA <> AREA_OLD OR RES15 <> RES_OLD THEN
    AREA_OLD := AREA; RES_OLD := RES15;
    SUB_OFF := 1.0;
    DATA_OK := FALSE; PLAN_OK := FALSE; PARSING := FALSE; KNOWN := 0; SLOT_OLD := -1;
END_IF;
IF RES15 THEN
    TOPIC := CONCAT(CONCAT('spot/', AREA_S), '/flat15'); SPH := 4; SPD := 96;
ELSE
    TOPIC := CONCAT(CONCAT('spot/', AREA_S), '/flat60'); SPH := 1; SPD := 24;
END_IF;
IF SUB_OFF > 0.0 THEN SUB_OFF := SUB_OFF - TS; END_IF;

MQ(ENABLE := SUB_OFF <= 0.0, BROKER_IP := '%s', BROKER_PORT := %d, CLIENT_ID := 'plc-spot-1', TOPIC := TOPIC, TS := TS);
MQ_CONNECTED := MQ.CONNECTED;
MQ_STATE := MQ.STATE;
MQ_MSGS := MQ.MSG_CNT;
MQ_RECONN := MQ.RECONNECTS;

(* A message is read over several cycles, 6 numbers per cycle, from a copy; one that arrives meanwhile is
   skipped (the next comes 10 s later). *)
IF MQ.NEW_MSG AND NOT PARSING AND SUB_OFF <= 0.0 THEN
    BUF := MQ.PAYLOAD;
    BLEN := MQ.PAYLOAD_LEN;
    MQ_LEN := BLEN;
    PARSING := TRUE;
    PK := 0;
    TKNOWN := 0;
END_IF;
IF PARSING THEN
    FOR PKN := 1 TO 6 DO
        IF PARSING THEN
            IF PK <= 7 THEN
                CASE PK OF
%s
                END_CASE;
                JN(BUF := BUF, BUF_LEN := BLEN, KEY := KEY);
                HF[PK] := JN.FOUND;
                HV[PK] := JN.VALUE;
                IF PK = 7 THEN
                    IF JN.FOUND THEN TKNOWN := LIMIT(0, TO_INT(JN.VALUE), %d); END_IF;
                END_IF;
                PK := PK + 1;
            ELSIF PK - 8 < TKNOWN THEN
                I := PK - 8;
                IF I < 10 THEN
                    KEY := CONCAT('p', MID(DIG, 1, I + 1));
                ELSE
                    KEY := CONCAT(CONCAT('p', MID(DIG, 1, I / 10 + 1)), MID(DIG, 1, I MOD 10 + 1));
                END_IF;
                JN(BUF := BUF, BUF_LEN := BLEN, KEY := KEY);
                IF JN.FOUND THEN TA[I] := JN.VALUE; ELSE TKNOWN := I; END_IF;
                PK := PK + 1;
            ELSE
                (* complete: take it over in one step *)
                PARSING := FALSE;
                IF HF[0] AND HF[1] AND HF[2] AND TKNOWN > 0 THEN
                    SRC_VALID := HV[0] > 0.5;
                    BEAT := TO_INT(HV[1]);
                    SLOT := TO_INT(HV[2]);
                    HOUR := TO_INT(HV[3]);
                    PRICE_TOTAL := HV[4];
                    RANK := TO_INT(HV[5]);
                    TOMO_OK := HV[6] > 0.5;
                    KNOWN := TKNOWN;
                    FOR J := 0 TO %d DO
                        IF J < TKNOWN THEN A[J] := TA[J]; ELSE A[J] := 0.0; END_IF;
                    END_FOR;
                    DATA_OK := TRUE;
                END_IF;
            END_IF;
        END_IF;
    END_FOR;
END_IF;

(* is the price usable? *)
IF BEAT <> BEAT_OLD THEN BEAT_T := 0.0; BEAT_OLD := BEAT; ELSIF BEAT_T < 9999.0 THEN BEAT_T := BEAT_T + TS; END_IF;
BEAT_OK := BEAT_T < 60.0;
VALID := MQ_CONNECTED AND DATA_OK AND SRC_VALID AND BEAT_OK AND KNOWN > 0;
IF SLOT < 0 OR SLOT >= SPD THEN VALID := FALSE; END_IF;
IF KNOWN > 0 THEN PRICE := A[0]; ELSE PRICE := 0.0; END_IF;
KNOWN_H := TO_REAL(KNOWN) / TO_REAL(SPH);

N_BLOCK := LIMIT(1, N_BLOCK, 12);
N_CHEAP := LIMIT(0, N_CHEAP, 24);
IF MODE < 0 OR MODE > 2 THEN MODE := 0; END_IF;
IF STRAT < 0 OR STRAT > 1 THEN STRAT := 0; END_IF;
NB := N_BLOCK * SPH;

(* the plan's clock: one step per slot. A jump of the clock (not the next slot) throws the plan away. *)
IF VALID AND SLOT <> SLOT_OLD THEN
    IF SLOT_OLD >= 0 AND SLOT <> (SLOT_OLD + 1) MOD SPD THEN PLAN_OK := FALSE; END_IF;
    SCNT := SCNT + 1;
    SLOT_OLD := SLOT;
END_IF;

SEC_T := SEC_T + TS;
IF SEC_T >= 1.0 THEN
    SEC_T := 0.0;
    SUM := 0.0; P_MIN := 999.0; P_MAX := -999.0; SCALE := 10.0;
    FOR I := 0 TO KNOWN - 1 DO
        X := A[I];
        SUM := SUM + X;
        IF X > SCALE THEN SCALE := X; END_IF;
        IF X < P_MIN THEN P_MIN := X; END_IF;
        IF X > P_MAX THEN P_MAX := X; END_IF;
    END_FOR;
    IF KNOWN > 0 THEN P_AVG := SUM / TO_REAL(KNOWN); ELSE P_AVG := 0.0; P_MIN := 0.0; P_MAX := 0.0; END_IF;

    (* Cheapest consecutive N_BLOCK hours among the known slots. The block is frozen once chosen, or the search
       would push it ahead for ever. Planned again: when it has run, when its length is changed, when more slots
       became known before it started (tomorrow's prices arrived), on the button. *)
    IF VALID THEN
        NEED := REPLAN OR NOT PLAN_OK OR PN <> NB;
        IF PLAN_OK THEN
            IF SCNT >= PS + TO_DINT(PN) THEN NEED := TRUE; END_IF;
            IF SCNT < PS AND SCNT + TO_DINT(KNOWN) > PEND THEN NEED := TRUE; END_IF;
        END_IF;
        IF NEED THEN
            REPLAN := FALSE;
            PLAN_OK := FALSE;
            IF KNOWN >= NB THEN
                BEST := 1.0E9; BI := 0;
                SUM := 0.0;
                FOR J := 0 TO NB - 1 DO SUM := SUM + A[J]; END_FOR;
                FOR I := 0 TO KNOWN - NB DO
                    IF I > 0 THEN SUM := SUM - A[I - 1] + A[I + NB - 1]; END_IF;
                    IF SUM < BEST - 0.0001 THEN BEST := SUM; BI := I; END_IF;
                END_FOR;
                PS := SCNT + TO_DINT(BI);
                PN := NB;
                PEND := SCNT + TO_DINT(KNOWN);
                P_BLOCK := BEST / TO_REAL(NB);
                J := (SLOT + BI) MOD SPD;
                START_AT_H := J / SPH;
                START_AT_M := (J MOD SPH) * 15;
                PLAN_OK := TRUE;
            END_IF;
        END_IF;
    END_IF;
    IF PLAN_OK THEN
        START_IN := TO_REAL(MAX(0, TO_INT(PS - SCNT))) / TO_REAL(SPH);
        IN_BLOCK := SCNT >= PS AND SCNT < PS + TO_DINT(PN);
        IF IN_BLOCK THEN LEFT_H := TO_REAL(TO_INT(PS + TO_DINT(PN) - SCNT)) / TO_REAL(SPH); ELSE LEFT_H := TO_REAL(PN) / TO_REAL(SPH); END_IF;
    ELSE
        START_IN := 0.0; IN_BLOCK := FALSE; LEFT_H := 0.0;
    END_IF;

    FOR I := 0 TO %d DO
        PLA[I] := FALSE;
        IF I < KNOWN THEN
            IF STRAT = 0 AND PLAN_OK THEN
                PLA[I] := SCNT + TO_DINT(I) >= PS AND SCNT + TO_DINT(I) < PS + TO_DINT(PN) AND A[I] <= LIM_HIGH;
            END_IF;
            IF A[I] <= LIM_LOW THEN PLA[I] := TRUE; END_IF;
        END_IF;
    END_FOR;
    IF STRAT = 1 AND KNOWN > 0 THEN
        PLA[0] := (RANK >= 1 AND RANK <= N_CHEAP AND PRICE <= LIM_HIGH) OR PRICE <= LIM_LOW;
    END_IF;
END_IF;
""" % (BROKER_IP, BROKER_PORT,
       "\n".join("                    %d: KEY := '%s';" % (i, k) for i, k in enumerate(HEAD)), NS, NS - 1, NS - 1))
code.append("(* per bar: height in %, in the plan, negative, label (hour of the day; -1 = none) *)")
for i in range(NS):
    code.append("IF %d < KNOWN THEN BT%02d := LIMIT(0.0, A[%d] / SCALE * 100.0, 100.0); NG%02d := A[%d] < 0.0; ELSE BT%02d := 0.0; NG%02d := FALSE; END_IF; "
                "PL%02d := PLA[%d]; IF (SLOT + %d) MOD SPH = 0 THEN HL%02d := ((SLOT + %d) / SPH) MOD 24; ELSE HL%02d := -1; END_IF;"
                % (i, i, i, i, i, i, i, i, i, i, i, i, i))
code.append("""
(* page values in the chosen unit; inside, everything stays c/kWh without VAT *)
IF UNIT_MWH THEN UK := 10.0; ELSE UK := 1.0; END_IF;
D_PRICE := PRICE * UK; D_TOTAL := PRICE_TOTAL * UK; D_AVG := P_AVG * UK; D_MIN := P_MIN * UK; D_MAX := P_MAX * UK;
D_BLOCK := P_BLOCK * UK; D_SCALE := SCALE * UK; D_HIGH := LIM_HIGH * UK; D_LOW := LIM_LOW * UK;

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
open(os.path.join(HERE, "areas.json"), "w").write(json.dumps(AREAS))
print(len(AREAS), "areas,", NS, "slots")
