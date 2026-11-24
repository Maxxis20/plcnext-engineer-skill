(* Modbus RTU room sensor (AXL F RS UNI 1H in Modbus/RTU mode, which adds and checks
   the CRC). Wire address = printed register number - 1; a float is two registers, low word first.
   KIND: 0..5 polling requests, 10 write temperature setpoint, 11 write occupancy coil, 12 write fan speed. *)
TICKS := TICKS + 1;
IF QUIET < 1000 THEN QUIET := QUIET + 1; END_IF;
COMM_OK := QUIET < 50;
CASE STEP OF
0:  CTRL_H := BYTE#0;
    CTRL_L := BYTE#0;
    IF TICKS >= 2 THEN
        (* what to send: a pending write first, else the next polling request *)
        IF SYNCED AND SP_REQ10 <> SP_SHADOW10 THEN
            KIND := 10;
        ELSIF SYNCED AND UNOCC_REQ <> UNOCC_SHADOW THEN
            KIND := 11;
        ELSIF SYNCED AND FAN_REQ <> FAN_SHADOW THEN
            IF FAN_REQ < 1 THEN FAN_REQ := 1; END_IF;
            IF FAN_REQ > 5 THEN FAN_REQ := 5; END_IF;
            KIND := 12;
        ELSE
            KIND := REQ;
            REQ := REQ + 1;
            IF REQ > 5 THEN REQ := 0; END_IF;
        END_IF;
        FC := 4; QTY := 2;
        CASE KIND OF
        0:  ADDR := 0; QTY := 6;             (* temperature, humidity, CO2 *)
        1:  ADDR := 6;                       (* VOC *)
        2:  ADDR := 0; QTY := 6;             (* (the printed dew point registers 54-55 only repeat other values) *)
        3:  FC := 3; ADDR := 0; QTY := 4;    (* setpoints temperature, humidity *)
        4:  FC := 3; ADDR := 39; QTY := 6;   (* fan speed, CO2 yellow, CO2 red *)
        5:  FC := 1; ADDR := 0; QTY := 16;   (* coils 1..16 *)
        10: FC := 16; ADDR := 0;
        11: FC := 5; ADDR := 5;              (* coil 6: on = room not occupied *)
        12: FC := 16; ADDR := 39;            (* fan speed, a whole number in two registers, low word first *)
        END_CASE;
        TX02 := TO_BYTE(SLAVE);
        TX03 := TO_BYTE(FC);
        TX04 := TO_BYTE(ADDR / 256);
        TX05 := TO_BYTE(ADDR MOD 256);
        TX06 := BYTE#0;
        TX07 := TO_BYTE(QTY);
        TX01 := BYTE#6;
        IF KIND = 10 THEN
            ENC(V := TO_REAL(SP_REQ10) / 10.0);
            TX08 := BYTE#4;
            TX09 := TO_BYTE(SHR(ENC.D, 8) AND DWORD#16#FF);
            TX10 := TO_BYTE(ENC.D AND DWORD#16#FF);
            TX11 := TO_BYTE(SHR(ENC.D, 24) AND DWORD#16#FF);
            TX12 := TO_BYTE(SHR(ENC.D, 16) AND DWORD#16#FF);
            TX01 := BYTE#11;
        ELSIF KIND = 12 THEN
            TX08 := BYTE#4;
            TX09 := BYTE#0;
            TX10 := BYTE#0;
            TX11 := BYTE#0;
            TX12 := TO_BYTE(FAN_REQ);
            TX01 := BYTE#11;
        ELSIF KIND = 11 THEN
            IF UNOCC_REQ THEN TX06 := BYTE#16#FF; ELSE TX06 := BYTE#0; END_IF;
            TX07 := BYTE#0;
        END_IF;
        TOGGLE := NOT TOGGLE;
        IF TOGGLE THEN SENT := BYTE#16#10; ELSE SENT := BYTE#16#50; END_IF;
        CTRL_H := SENT;
        TICKS := 0; STEP := 1;
    END_IF;
1:  (* the module has taken the request when it echoes the command *)
    IF (STAT_H AND BYTE#16#80) <> BYTE#0 OR TICKS > 30 THEN
        N_ERR := N_ERR + 1; TICKS := 0; STEP := 4;
    ELSIF (STAT_H AND BYTE#16#70) = (SENT AND BYTE#16#70) THEN
        TICKS := 0; STEP := 2;
    END_IF;
2:  (* wait for the answer *)
    IF (STAT_L AND BYTE#16#06) <> BYTE#0 OR TICKS > 40 THEN
        N_ERR := N_ERR + 1; TICKS := 0; STEP := 4;
    ELSIF (STAT_L AND BYTE#16#01) <> BYTE#0 THEN
        IF TOGGLE THEN SENT := BYTE#16#30; ELSE SENT := BYTE#16#70; END_IF;
        CTRL_H := SENT;
        TICKS := 0; STEP := 3;
    END_IF;
3:  (* the characters are there when the read command is echoed: RX02 address, RX03 function, RX04.. data *)
    IF (STAT_H AND BYTE#16#70) = (SENT AND BYTE#16#70) THEN
        RLEN := TO_INT(RX01 AND BYTE#16#7F);
        R_FC := TO_INT(RX03);
        IF R_FC >= 128 THEN
            N_EXC := N_EXC + 1;
            IF KIND = 10 THEN SP_SHADOW10 := SP_REQ10; END_IF;      (* refused: do not repeat for ever *)
            IF KIND = 11 THEN UNOCC_SHADOW := UNOCC_REQ; END_IF;
            IF KIND = 12 THEN FAN_SHADOW := FAN_REQ; END_IF;
        ELSIF R_FC = FC THEN
            N_OK := N_OK + 1; QUIET := 0;
            CASE KIND OF
            0, 2:
                D := SHL(TO_DWORD(RX07), 24) OR SHL(TO_DWORD(RX08), 16) OR SHL(TO_DWORD(RX05), 8) OR TO_DWORD(RX06);
                DEC(D := D); TEMP := DEC.V;
                D := SHL(TO_DWORD(RX11), 24) OR SHL(TO_DWORD(RX12), 16) OR SHL(TO_DWORD(RX09), 8) OR TO_DWORD(RX10);
                DEC(D := D); HUM := DEC.V;
                D := SHL(TO_DWORD(RX15), 24) OR SHL(TO_DWORD(RX16), 16) OR SHL(TO_DWORD(RX13), 8) OR TO_DWORD(RX14);
                DEC(D := D); CO2 := DEC.V;
            1:  D := SHL(TO_DWORD(RX07), 24) OR SHL(TO_DWORD(RX08), 16) OR SHL(TO_DWORD(RX05), 8) OR TO_DWORD(RX06);
                DEC(D := D); VOC := DEC.V;
            3:  D := SHL(TO_DWORD(RX07), 24) OR SHL(TO_DWORD(RX08), 16) OR SHL(TO_DWORD(RX05), 8) OR TO_DWORD(RX06);
                DEC(D := D); TSP := DEC.V;
                D := SHL(TO_DWORD(RX11), 24) OR SHL(TO_DWORD(RX12), 16) OR SHL(TO_DWORD(RX09), 8) OR TO_DWORD(RX10);
                DEC(D := D); HSP := DEC.V;
                (* a setpoint changed on the sensor's own screen comes in here, unless a change of ours is waiting *)
                SPV10 := TO_INT(TSP * 10.0);
                IF SP_REQ10 = SP_SHADOW10 THEN SP_REQ10 := SPV10; SP_SHADOW10 := SPV10; END_IF;
                SYNCED := TRUE;
            4:  FAN := TO_INT(RX07) * 256 + TO_INT(RX08);       (* whole number: high word first, unlike the floats *)
                IF FAN_REQ = FAN_SHADOW THEN FAN_REQ := FAN; FAN_SHADOW := FAN; END_IF;
                D := SHL(TO_DWORD(RX11), 24) OR SHL(TO_DWORD(RX12), 16) OR SHL(TO_DWORD(RX09), 8) OR TO_DWORD(RX10);
                DEC(D := D); CO2_Y := DEC.V;
                D := SHL(TO_DWORD(RX15), 24) OR SHL(TO_DWORD(RX16), 16) OR SHL(TO_DWORD(RX13), 8) OR TO_DWORD(RX14);
                DEC(D := D); CO2_R := DEC.V;
            5:  COILS := SHL(TO_WORD(RX06), 8) OR TO_WORD(RX05);
                UNOCC := (RX05 AND BYTE#16#20) <> BYTE#0;
                IF UNOCC_REQ = UNOCC_SHADOW THEN UNOCC_REQ := UNOCC; UNOCC_SHADOW := UNOCC; END_IF;
            10: SP_SHADOW10 := SP_REQ10; N_WRITE := N_WRITE + 1; REQ := 3;
            11: UNOCC_SHADOW := UNOCC_REQ; N_WRITE := N_WRITE + 1; REQ := 5;
            12: FAN_SHADOW := FAN_REQ; N_WRITE := N_WRITE + 1; REQ := 4;
            END_CASE;
        ELSE
            N_ERR := N_ERR + 1;
        END_IF;
        TICKS := 0; STEP := 0;
    ELSIF TICKS > 30 THEN
        N_ERR := N_ERR + 1; TICKS := 0; STEP := 4;
    END_IF;
4:  (* after an error: reset the module's error bits *)
    CTRL_H := BYTE#0;
    CTRL_L := BYTE#16#06;
    IF TICKS > 5 THEN
        CTRL_L := BYTE#0; TICKS := 0; STEP := 0;
    END_IF;
END_CASE;
SP_REQ := TO_REAL(SP_REQ10) / 10.0;
(* dew point by the Magnus formula *)
IF HUM > 1.0 THEN
    G := LN(HUM / 100.0) + 17.62 * TEMP / (243.12 + TEMP);
    DEW := 243.12 * G / (17.62 - G);
END_IF;
IF CO2 >= CO2_R AND CO2_R > 0.0 THEN
    CO2_LEVEL := 2;
ELSIF CO2 >= CO2_Y AND CO2_Y > 0.0 THEN
    CO2_LEVEL := 1;
ELSE
    CO2_LEVEL := 0;
END_IF;

(* Profinet controller side, device plc-b (16 of 512 bytes used, big endian).
   from B: 0-1 temperature x10, 2-3 humidity x10, 4-5 battery mV, 6-7 B's counter, 8 status (bit 0 Modbus up),
           10-11 our counter sent back.   to B: 0-1 our counter, 2-3 our room temperature x10 *)
B_TEMP := TO_REAL(TO_INT(SHL(TO_WORD(PN_IN[0]), 8) OR TO_WORD(PN_IN[1]))) / 10.0;
B_HUM := TO_REAL(TO_INT(SHL(TO_WORD(PN_IN[2]), 8) OR TO_WORD(PN_IN[3]))) / 10.0;
B_VDD := TO_INT(SHL(TO_WORD(PN_IN[4]), 8) OR TO_WORD(PN_IN[5]));
B_BEAT := TO_INT(SHL(TO_WORD(PN_IN[6]), 8) OR TO_WORD(PN_IN[7]));
B_MB_OK := (PN_IN[8] AND BYTE#16#01) <> BYTE#0;
B_ECHO := TO_INT(SHL(TO_WORD(PN_IN[10]), 8) OR TO_WORD(PN_IN[11]));
PN_ACC := PN_ACC + 0.1;
PN_SEEN := PN_SEEN + 0.1;
IF B_BEAT <> PN_LAST THEN
    PN_LAST := B_BEAT;
    PN_SEEN := 0.0;
END_IF;
B_ALIVE := PN_SEEN < 3.0;
IF PN_ACC >= 1.0 THEN
    PN_ACC := 0.0;
    A_CNT := A_CNT + 1;
    IF A_CNT > 30000 THEN
        A_CNT := 0;
    END_IF;
END_IF;
PN_W := TO_WORD(A_CNT);
PN_OUT[0] := TO_BYTE(SHR(PN_W, 8));
PN_OUT[1] := TO_BYTE(PN_W AND WORD#16#FF);
PN_W := TO_WORD(TO_INT(TEMP * 10.0));
PN_OUT[2] := TO_BYTE(SHR(PN_W, 8));
PN_OUT[3] := TO_BYTE(PN_W AND WORD#16#FF);

(* ---- drive at plc-b over Profinet ---- *)
DRV_READY := (PN_IN[12] AND BYTE#16#01) <> BYTE#0;
DRV_RUNNING := (PN_IN[12] AND BYTE#16#02) <> BYTE#0;
DRV_FAULT := (PN_IN[12] AND BYTE#16#04) <> BYTE#0;
DRV_SIS_OK := (PN_IN[12] AND BYTE#16#08) <> BYTE#0;
DRV_LOCAL := (PN_IN[12] AND BYTE#16#10) <> BYTE#0;
SPEED_ACT := TO_INT(SHL(TO_WORD(PN_IN[14]), 8) OR TO_WORD(PN_IN[15]));

(* ---- interlocks ---- *)
IL_PN := B_ALIVE;
IL_SIS := DRV_SIS_OK AND B_ALIVE;
IL_DRVF := NOT DRV_FAULT;
FS_OK := IL_PN AND IL_SIS AND IL_DRVF;
IL_RDY := DRV_READY;
IL_REM := NOT DRV_LOCAL;
TEMP_MAX := TO_REAL(TEMP_MAX10) / 10.0;
IL_TEMP := COMM_OK AND TEMP < TEMP_MAX;
PERM_OK := FS_OK AND IL_RDY AND IL_REM AND IL_TEMP;
IL_ACTIVE := 0;
IF NOT IL_PN THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
IF NOT IL_SIS THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
IF NOT IL_DRVF THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
IF NOT IL_RDY THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
IF NOT IL_REM THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
IF NOT IL_TEMP THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;

(* ---- drive mode: Local comes from the drive; Auto <-> Manual without a bump ---- *)
IF DRV_LOCAL THEN
    DRV_MODE := 2;
ELSIF DRV_MODE_REQ = 1 THEN
    DRV_MODE := 1;
ELSE
    DRV_MODE := 0;
END_IF;
IF DRV_MODE <> MODE_PREV THEN
    IF DRV_MODE = 1 THEN
        MAN_RUN := RUN_CMD;
        MAN_SP := SPEED_OUT;
        MAN_RPM := TO_INT(TO_DINT(SPEED_OUT) * TO_DINT(RPM_NOM) / 1000);
    ELSE
        MAN_RUN := FALSE;
    END_IF;
    MODE_PREV := DRV_MODE;
END_IF;

(* ---- sequence commands from the page ---- *)
IF SQ_CMD = 1 THEN                                  (* Start *)
    IF SQ_STEP = 0 AND NOT SQ_ALARM AND DRV_MODE = 0 THEN
        SQ_STEP := 1;
    END_IF;
ELSIF SQ_CMD = 2 THEN                               (* Stop: orderly *)
    IF SQ_STEP >= 1 AND SQ_STEP <= 3 THEN
        SQ_STEP := 4;
    END_IF;
ELSIF SQ_CMD = 3 THEN                               (* Continue: acknowledge, retry the step, back to Auto *)
    SQ_ALARM := FALSE;
    SQ_MODE := 0;
    SUP_T := 0.0;
ELSIF SQ_CMD = 4 AND SQ_MODE = 1 THEN               (* Next: force the transition *)
    IF SQ_STEP >= 4 THEN
        SQ_STEP := 0;
    ELSE
        SQ_STEP := SQ_STEP + 1;
    END_IF;
    OV_CNT := OV_CNT + 1;
    OV_LAST := 4;
ELSIF SQ_CMD = 5 AND SQ_MODE = 1 THEN               (* Selected: jump *)
    IF SQ_SEL >= 0 AND SQ_SEL <= 4 THEN
        SQ_STEP := SQ_SEL;
        OV_CNT := OV_CNT + 1;
        OV_LAST := 5;
    END_IF;
ELSIF SQ_CMD = 6 THEN                               (* Reset: alarm off, back to idle, reset the drive *)
    SQ_ALARM := FALSE;
    SQ_STEP := 0;
    RST_T := 1.0;
END_IF;
SQ_CMD := 0;

IF SQ_STEP <> SQ_PREV THEN                          (* a new step *)
    SQ_T := 0.0;
    SUP_T := 0.0;
    SETTLE_T := 0.0;
    RQ_AT := 1;
    TICK := 0.0;
    SQ_PREV := SQ_STEP;
END_IF;
SQ_T := SQ_T + TS;

(* ---- the steps: requirements, settle time, supervision time ---- *)
RQ1 := FALSE; RQ2 := FALSE; RQ3 := FALSE; RQ4 := FALSE; RQ5 := FALSE;
CASE SQ_STEP OF
1:  (* PRECHECK *)
    SQ_N := 5; SETTLE := 3.0; TMAX := 15.0;
    RQ1 := IL_PN; RQ2 := IL_SIS; RQ3 := IL_RDY; RQ4 := IL_REM; RQ5 := IL_TEMP;
2:  (* START DRIVE *)
    SQ_N := 3; SETTLE := 1.0; TMAX := 10.0;
    RQ1 := FS_OK; RQ2 := SPEED_ACT > 0; RQ3 := DRV_RUNNING;
3:  (* RUNNING: stays until Stop; feedback lost longer than TMAX = alarm *)
    SQ_N := 2; SETTLE := 0.0; TMAX := 3.0;
    RQ1 := FS_OK; RQ2 := DRV_RUNNING;
4:  (* STOP *)
    SQ_N := 2; SETTLE := 1.0; TMAX := 15.0;
    RQ1 := NOT DRV_RUNNING; RQ2 := SPEED_ACT = 0;
ELSE
    SQ_N := 0; SETTLE := 0.0; TMAX := 0.0;
END_CASE;
(* the first requirement not met; SQ_N + 1 = all met *)
IF SQ_N >= 1 AND NOT RQ1 THEN FBAD := 1;
ELSIF SQ_N >= 2 AND NOT RQ2 THEN FBAD := 2;
ELSIF SQ_N >= 3 AND NOT RQ3 THEN FBAD := 3;
ELSIF SQ_N >= 4 AND NOT RQ4 THEN FBAD := 4;
ELSIF SQ_N >= 5 AND NOT RQ5 THEN FBAD := 5;
ELSE FBAD := SQ_N + 1;
END_IF;
(* the cursor walks the list one row per half second, and falls back to a row that is lost *)
TICK := TICK + TS;
IF RQ_AT > FBAD THEN
    RQ_AT := FBAD;
ELSIF RQ_AT < FBAD AND TICK >= 0.5 THEN
    RQ_AT := RQ_AT + 1;
    TICK := 0.0;
END_IF;

(* forced stop: in START DRIVE and RUNNING, at once, in every mode *)
IF (SQ_STEP = 2 OR SQ_STEP = 3) AND NOT FS_OK AND NOT SQ_ALARM THEN
    SQ_ALARM := TRUE;
    AL_STEP := SQ_STEP;
    IF NOT IL_PN THEN AL_REQ := 11; ELSIF NOT IL_SIS THEN AL_REQ := 12; ELSE AL_REQ := 13; END_IF;
END_IF;

IF SQ_MODE = 0 AND DRV_MODE = 0 AND NOT SQ_ALARM THEN
    (* supervision: steps 1, 2, 4 from entry while not all met; RUNNING only while something is lost *)
    IF FBAD <= SQ_N THEN
        SUP_T := SUP_T + TS;
    ELSIF SQ_STEP = 3 THEN
        SUP_T := 0.0;
    END_IF;
    IF TMAX > 0.0 AND SUP_T >= TMAX THEN
        SQ_ALARM := TRUE;
        AL_STEP := SQ_STEP;
        AL_REQ := FBAD;
    END_IF;
    (* settle time once the cursor is through the list, then the next step *)
    IF RQ_AT > SQ_N AND SQ_N > 0 AND SQ_STEP <> 3 AND NOT SQ_ALARM THEN
        SETTLE_T := SETTLE_T + TS;
        IF SETTLE_T >= SETTLE THEN
            IF SQ_STEP >= 4 THEN
                SQ_STEP := 0;
            ELSE
                SQ_STEP := SQ_STEP + 1;
            END_IF;
        END_IF;
    ELSE
        SETTLE_T := 0.0;
    END_IF;
END_IF;

IF SQ_ALARM THEN SQ_STATE := 3;
ELSIF SQ_MODE = 1 OR (DRV_MODE <> 0 AND SQ_STEP <> 0) THEN SQ_STATE := 2;
ELSIF SQ_STEP = 4 THEN SQ_STATE := 4;
ELSIF SQ_STEP >= 1 THEN SQ_STATE := 1;
ELSE SQ_STATE := 0;
END_IF;

(* ---- manual speed is set in rpm; the drive takes per mille of the nominal speed ---- *)
IF MAN_RPM < 0 THEN MAN_RPM := 0; ELSIF MAN_RPM > RPM_NOM THEN MAN_RPM := RPM_NOM; END_IF;
IF RPM_NOM > 0 THEN
    MAN_SP := TO_INT(TO_DINT(MAN_RPM) * 1000 / TO_DINT(RPM_NOM));
END_IF;

(* ---- commands to the drive ---- *)
IF DRV_MODE = 1 THEN
    IF NOT FS_OK THEN
        MAN_RUN := FALSE;
    END_IF;
    RUN_CMD := MAN_RUN AND FS_OK;
    SPEED_OUT := MAN_SP;
ELSIF DRV_MODE = 0 THEN
    RUN_CMD := (SQ_STEP = 2 OR SQ_STEP = 3) AND FS_OK AND NOT SQ_ALARM;
    SPEED_OUT := SPEED_SP;
ELSE
    RUN_CMD := FALSE;
END_IF;
IF SPEED_OUT < 0 THEN SPEED_OUT := 0; ELSIF SPEED_OUT > 1000 THEN SPEED_OUT := 1000; END_IF;
DRV_RESET := RST_T > 0.0;
IF RST_T > 0.0 THEN
    RST_T := RST_T - TS;
END_IF;
IF DRV_FAULT OR NOT DRV_SIS_OK OR NOT B_ALIVE THEN
    DRV_STATE := 2;
ELSIF DRV_RUNNING THEN
    DRV_STATE := 1;
ELSIF RUN_CMD OR SPEED_ACT > 0 THEN
    DRV_STATE := 3;
ELSE
    DRV_STATE := 0;
END_IF;
DB := BYTE#0;
IF RUN_CMD THEN DB := DB OR BYTE#16#01; END_IF;
IF DRV_RESET THEN DB := DB OR BYTE#16#02; END_IF;
PN_OUT[4] := DB;
DW := TO_WORD(SPEED_OUT);
PN_OUT[6] := TO_BYTE(SHR(DW, 8));
PN_OUT[7] := TO_BYTE(DW AND WORD#16#FF);
ACT_RPM := TO_REAL(SPEED_ACT) * TO_REAL(RPM_NOM) / 1000.0;
OUT_RPM := TO_REAL(SPEED_OUT) * TO_REAL(RPM_NOM) / 1000.0;
IF SETTLE > 0.0 THEN SETTLE_PCT := SETTLE_T / SETTLE * 100.0; ELSE SETTLE_PCT := 0.0; END_IF;
IF TMAX > 0.0 THEN SUP_PCT := SUP_T / TMAX * 100.0; ELSE SUP_PCT := 0.0; END_IF;
(* ---- trend pens (DataLogger sessions Speed and Room) ---- *)
P1_SP_RPM := TO_INT(OUT_RPM);
P1_ACT_RPM := TO_INT(ACT_RPM);
TR_TEMP := TEMP;
TR_TEMP_MAX := TEMP_MAX;

(* ---- ClickHouse: store 10 signals every second, read the speed history back (display only) ---- *)
CH_TAGS[1] := 'SPEED_SP_RPM';  CH_VALS[1] := OUT_RPM;
CH_TAGS[2] := 'SPEED_ACT_RPM'; CH_VALS[2] := ACT_RPM;
CH_TAGS[3] := 'TEMP';      CH_VALS[3] := TEMP;
CH_TAGS[4] := 'TEMP_MAX';  CH_VALS[4] := TEMP_MAX;
CH_TAGS[5] := 'HUM';       CH_VALS[5] := HUM;
CH_TAGS[6] := 'CO2';       CH_VALS[6] := CO2;
CH_TAGS[7] := 'SQ_STEP';   CH_VALS[7] := TO_REAL(SQ_STEP);
CH_TAGS[8] := 'DRV_STATE'; CH_VALS[8] := TO_REAL(DRV_STATE);
CH_TAGS[9] := 'RUN_CMD';   IF RUN_CMD THEN CH_VALS[9] := 1.0; ELSE CH_VALS[9] := 0.0; END_IF;
CH_TAGS[10] := 'IL_ACTIVE'; CH_VALS[10] := TO_REAL(IL_ACTIVE);
CH(ENABLE := CH_ON, HOST := '192.168.1.60', PORT := 8123, USER := 'plc_writer',
   KEY := '%%ENV:CLICKHOUSE_PASSWORD%%', TABLE := 'plc.samples',
   N_TAGS := 10, TAGS := CH_TAGS, VALS := CH_VALS, SAMPLE_S := 1.0, SEND_S := 10.0,
   QUERY := 'SELECT v, toHour(m) * 100 + toMinute(m) FROM (SELECT toStartOfMinute(ts) AS m, round(avg(value), 1) AS v FROM plc.samples WHERE tag = @SPEED_ACT_RPM@ AND ts > now() - INTERVAL 24 MINUTE GROUP BY m ORDER BY m WITH FILL FROM toStartOfMinute(now() - INTERVAL 23 MINUTE) TO toStartOfMinute(now()) + 60 STEP 60) ORDER BY m',
   QUERY_S := 60.0, TS := TS);
CH_STATE := CH.STATE; CH_CODE := CH.HTTP_CODE; CH_ROWS := CH.N_ROWS; CH_ERR := CH.N_ERR; CH_DROP := CH.N_DROP;
CH_PEND := CH.PENDING; CH_AGE := CH.OK_AGE; CH_QAGE := CH.Q_AGE; CH_QN := CH.Q_N;
H01 := CH.Q_VALS[1]; H02 := CH.Q_VALS[3]; H03 := CH.Q_VALS[5]; H04 := CH.Q_VALS[7]; H05 := CH.Q_VALS[9]; H06 := CH.Q_VALS[11];
H07 := CH.Q_VALS[13]; H08 := CH.Q_VALS[15]; H09 := CH.Q_VALS[17]; H10 := CH.Q_VALS[19]; H11 := CH.Q_VALS[21]; H12 := CH.Q_VALS[23];
H13 := CH.Q_VALS[25]; H14 := CH.Q_VALS[27]; H15 := CH.Q_VALS[29]; H16 := CH.Q_VALS[31]; H17 := CH.Q_VALS[33]; H18 := CH.Q_VALS[35];
H19 := CH.Q_VALS[37]; H20 := CH.Q_VALS[39]; H21 := CH.Q_VALS[41]; H22 := CH.Q_VALS[43]; H23 := CH.Q_VALS[45]; H24 := CH.Q_VALS[47];
(* wall-clock labels under the bars: the query gives each minute as HHMM after its value (in the ClickHouse
   server's time zone; use toTimeZone(m, 'Area/City') in the query for another one) *)
FOR LI := 1 TO 7 DO
    CASE LI OF 1: LB := 1; 2: LB := 5; 3: LB := 9; 4: LB := 13; 5: LB := 17; 6: LB := 21; ELSE LB := 24; END_CASE;
    HHMM := TO_INT(CH.Q_VALS[2 * LB]);
    IF CH.Q_N >= 2 * LB THEN
        LTXT := CONCAT(CONCAT(TO_STRING(HHMM / 100, '{0}'), ':'), TO_STRING(HHMM MOD 100, '{0:D2}'));
    ELSE
        LTXT := '';
    END_IF;
    CASE LI OF 1: L01 := LTXT; 2: L05 := LTXT; 3: L09 := LTXT; 4: L13 := LTXT; 5: L17 := LTXT; 6: L21 := LTXT; ELSE L24 := LTXT; END_CASE;
END_FOR;
