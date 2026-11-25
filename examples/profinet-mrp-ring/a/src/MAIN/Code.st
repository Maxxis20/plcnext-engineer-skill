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

(* ---- Profinet state of the devices (process data of their DAPs) and of the controller ---- *)
NB_AR := B_AR_VALID;
NB_DIAG := NOT B_NO_DIAG;
NB_RUN := B_APPL_RUN;
NX_AR := X_AR_VALID;
NX_DIAG := NOT X_NO_DIAG;
NX_RUN := X_APPL_RUN;
PN_BF := PNIO_SYSTEM_BF;
PN_SF := PNIO_SYSTEM_SF;
PN_DIAG := PNIO_DIAG_AVAILABLE;
PN_MAINT := PNIO_MAINTENANCE_REQUIRED OR PNIO_MAINTENANCE_DEMANDED;
PN_CFG := TO_INT(PNIO_CONFIG_STATUS);
PN_CFG_OK := PNIO_CONFIG_STATUS_READY AND NOT PNIO_CONFIG_STATUS_CFG_FAULT;

(* ---- drive at plc-b over Profinet. Profinet link = B's AR valid AND B's heartbeat moving; without it B's bits
   mean nothing (the bytes fall to 0 when the AR goes): they are taken as unknown, not as "safety chain open" ---- *)
IL_PN := B_AR_VALID AND B_ALIVE;
B_UNK := NOT IL_PN;
IF B_AR_VALID THEN
    DRV_READY := (PN_IN[12] AND BYTE#16#01) <> BYTE#0;
    DRV_RUNNING := (PN_IN[12] AND BYTE#16#02) <> BYTE#0;
    DRV_FAULT := (PN_IN[12] AND BYTE#16#04) <> BYTE#0;
    DRV_SIS_OK := (PN_IN[12] AND BYTE#16#08) <> BYTE#0;
    DRV_LOCAL := (PN_IN[12] AND BYTE#16#10) <> BYTE#0;
    SPEED_ACT := TO_INT(SHL(TO_WORD(PN_IN[14]), 8) OR TO_WORD(PN_IN[15]));
ELSE
    DRV_READY := FALSE;
    DRV_RUNNING := FALSE;
    DRV_FAULT := FALSE;
    DRV_SIS_OK := FALSE;
    DRV_LOCAL := FALSE;
    SPEED_ACT := 0;
END_IF;

(* ---- interlocks: unknown (no link) counts as not fulfilled; the page shows those rows as unknown ---- *)
IL_SIS := DRV_SIS_OK AND NOT B_UNK;
IL_DRVF := NOT DRV_FAULT AND NOT B_UNK;
FS_OK := IL_PN AND IL_SIS AND IL_DRVF;
IL_RDY := DRV_READY AND NOT B_UNK;
IL_REM := NOT DRV_LOCAL AND NOT B_UNK;
TEMP_MAX := TO_REAL(TEMP_MAX10) / 10.0;
IL_TEMP := COMM_OK AND TEMP < TEMP_MAX;
PERM_OK := FS_OK AND IL_RDY AND IL_REM AND IL_TEMP;
IL_ACTIVE := 0;
IF NOT IL_PN THEN
    IL_ACTIVE := IL_ACTIVE + 1;                     (* the four of B are unknown, not counted *)
ELSE
    IF NOT IL_SIS THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
    IF NOT IL_DRVF THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
    IF NOT IL_RDY THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
    IF NOT IL_REM THEN IL_ACTIVE := IL_ACTIVE + 1; END_IF;
END_IF;
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
    AL_AGE := 0.0;
END_IF;
(* the root cause: when B's AR drops within 1 s of a forced stop for safety chain or drive fault, the bytes fell
   with the link (they go to 0 before or with PN_AR_VALID): name the Profinet loss instead *)
IF SQ_ALARM AND AL_AGE < 1.0 THEN
    AL_AGE := AL_AGE + TS;
    IF (AL_REQ = 12 OR AL_REQ = 13) AND NOT B_AR_VALID THEN AL_REQ := 11; END_IF;
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
IF DRV_FAULT OR NOT DRV_SIS_OK OR NOT IL_PN THEN
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

(* ---- MRP ring state, from the XC216's two ring ports: record 0x802A PDPortDataReal of Port 1 (Node ID 31,
   subslot 0x8001, cable 1 to A) and Port 2 (Node ID 32, subslot 0x8002, cable 3 to B), read with RDREC in turn,
   one a second. Its LinkState (2 bytes, 8 bytes before the end: MediaType 4 and padding 2 follow) is the port
   state (high byte: 2 blocking, 5 forwarding) and the link (low byte: 1 up, 2 down). The manager blocks one ring
   port while the ring is closed and forwards on both when it is open (IEC 62439-2). Record 0x8050
   PDInterfaceMrpDataReal, the direct ring state, is refused by the XC216 (STATUS 16#DE80B900: invalid type). ---- *)
NOW_T := NOW_T + 1;                                 (* 100 ms ticks since the start *)
HEXT := CONCAT('01234567', '89ABCDEF');            (* hex digits for the dumps below *)
RR_T := RR_T + TS;
XP1_AGE := XP1_AGE + TS;
XP2_AGE := XP2_AGE + TS;
CASE RR_PH OF
0:  RR_REQ := FALSE;
    IF RR_T >= 0.5 THEN
        RR_T := 0.0;
        IF NX_AR THEN
            RR_PORT := 3 - RR_PORT;                 (* 1, 2, 1, ... *)
            RR_REQ := TRUE; RR_PH := 1;
        END_IF;
    END_IF;
1:  IF NOT RR.BUSY AND RR.VALID THEN
        RR_N := RR_N + 1; RR_LEN := RR.LEN;
        IF RR_LEN >= 40 AND RR_LEN <= 128 AND TO_INT(RR_BUF[0]) * 256 + TO_INT(RR_BUF[1]) = 16#020F THEN
            HB := TO_INT(RR_BUF[RR_LEN - 8]);       (* port state *)
            HI := TO_INT(RR_BUF[RR_LEN - 7]);       (* link *)
            IF RR_PORT = 1 THEN XP1_ST := HB; XP1_LINK := HI = 1; XP1_AGE := 0.0;
            ELSE XP2_ST := HB; XP2_LINK := HI = 1; XP2_AGE := 0.0; END_IF;
        END_IF;
        RR_REQ := FALSE; RR_PH := 0;
    ELSIF NOT RR.BUSY AND RR.ERROR THEN
        RR_NERR := RR_NERR + 1; RR_ST := TO_DINT(RR.STATUS);
        RR_REQ := FALSE; RR_PH := 0;
    ELSIF RR_T > 20.0 THEN
        RR_NERR := RR_NERR + 1;
        RR_REQ := FALSE; RR_PH := 0;
    END_IF;
END_CASE;
(* INDEX is an INT: 0x802A - 0x10000 = -32726 *)
RR(REQ := RR_REQ, ID := TO_DWORD(30 + RR_PORT), INDEX := -32726, MLEN := 128, RECORD := RR_BUF);
(* -1 unknown (no fresh answer of both ports within 5 s), 0 open, 1 closed *)
RR_OK := NX_AR AND XP1_AGE < 5.0 AND XP2_AGE < 5.0;
IF NOT RR_OK THEN
    RING_STATE := -1;
ELSIF XP1_LINK AND XP2_LINK AND (XP1_ST = 2 OR XP2_ST = 2) THEN
    RING_STATE := 1;
ELSE
    RING_STATE := 0;
END_IF;
IF RING_SIM THEN RING_STATE := 0; END_IF;          (* bench test input: the ring as if cable 2 were pulled *)
(* the three cables: 1 good, 0 broken, -1 unknown. Cables 1 and 3 end at the switch (its link state); cable 2
   (A port 2 - B port 1) is taken as the broken one when the ring is open while both switch ports have a link *)
IF RR_OK THEN
    IF XP1_LINK THEN SEG1 := 1; ELSE SEG1 := 0; END_IF;
    IF XP2_LINK THEN SEG3 := 1; ELSE SEG3 := 0; END_IF;
    IF RING_STATE = 0 AND XP1_LINK AND XP2_LINK THEN SEG2 := 0; ELSE SEG2 := 1; END_IF;
    IF RING_SIM THEN SEG2 := 0; END_IF;
ELSE
    SEG1 := -1; SEG2 := -1; SEG3 := -1;
END_IF;

(* ---- record probe: any record of any submodule, set PRB_ID (Node ID), PRB_IDX (0..65535), then PRB_GO ---- *)
CASE PRB_PH OF
0:  PRB_REQ := FALSE;
    IF PRB_GO THEN
        PRB_GO := FALSE;
        IF PRB_IDX > 32767 THEN PRB_I := TO_INT(PRB_IDX - 65536); ELSE PRB_I := TO_INT(PRB_IDX); END_IF;
        PRB_REQ := TRUE; PRB_PH := 1; PRB_T := 0.0;
    END_IF;
1:  PRB_T := PRB_T + TS;
    IF NOT PRB.BUSY AND (PRB.VALID OR PRB.ERROR) OR PRB_T > 20.0 THEN
        PRB_LEN := PRB.LEN; PRB_ST := TO_DINT(PRB.STATUS); PRB_VALID := PRB.VALID;
        PRB_HEX1 := ''; PRB_HEX2 := '';
        FOR HI := 0 TO 127 DO
            HB := TO_INT(PRB_BUF[HI]);
            HX := CONCAT(MID(HEXT, 1, HB / 16 + 1), MID(HEXT, 1, HB MOD 16 + 1));
            IF HI < 64 THEN PRB_HEX1 := CONCAT(PRB_HEX1, HX); ELSE PRB_HEX2 := CONCAT(PRB_HEX2, HX); END_IF;
        END_FOR;
        PRB_REQ := FALSE; PRB_PH := 0;
    END_IF;
END_CASE;
PRB(REQ := PRB_REQ, ID := TO_DWORD(PRB_ID), INDEX := PRB_I, MLEN := 128, RECORD := PRB_BUF);

(* ---- ring warning: latched when the ring opens; Ack while open marks it seen, it goes when the ring is
   closed and it was acknowledged. RING_WS: 0 none, 1 open, 2 closed again (not acknowledged), 3 open, acknowledged *)
NQ := 0;
IF RING_STATE <> RING_PREV THEN
    IF RING_STATE = 0 THEN
        RING_OPEN_CNT := RING_OPEN_CNT + 1;
        RING_LATCH := TRUE; RING_ACKD := FALSE;
        NQ := NQ + 1; EVQ[NQ] := 1;
    ELSIF RING_STATE = 1 AND RING_PREV = 0 THEN
        NQ := NQ + 1; EVQ[NQ] := 2;
    ELSIF RING_STATE = -1 AND RING_PREV >= 0 THEN
        NQ := NQ + 1; EVQ[NQ] := 7;
    END_IF;
    RING_PREV := RING_STATE;
END_IF;
IF RING_ACK THEN
    RING_ACK := FALSE;
    RING_ACKD := TRUE;
END_IF;
IF RING_LATCH AND RING_ACKD AND RING_STATE <> 0 THEN
    RING_LATCH := FALSE;
END_IF;
IF NOT RING_LATCH THEN RING_WS := 0;
ELSIF RING_STATE <> 0 THEN RING_WS := 2;
ELSIF RING_ACKD THEN RING_WS := 3;
ELSE RING_WS := 1;
END_IF;
(* link events of the two devices (not at the start) *)
IF NOW_T > 50 THEN
    IF NB_AR <> NB_PREV THEN
        NQ := NQ + 1; IF NB_AR THEN EVQ[NQ] := 4; ELSE EVQ[NQ] := 3; END_IF;
    END_IF;
    IF NX_AR <> NX_PREV THEN
        NQ := NQ + 1; IF NX_AR THEN EVQ[NQ] := 6; ELSE EVQ[NQ] := 5; END_IF;
    END_IF;
END_IF;
NB_PREV := NB_AR; NX_PREV := NX_AR;
(* event list, newest first: 1 ring open, 2 ring closed, 3 plc-b lost, 4 plc-b back, 5 xc216 lost, 6 xc216 back,
   7 ring state unknown *)
FOR QI := 1 TO NQ DO
    FOR HI := 5 TO 2 BY -1 DO
        EVC[HI] := EVC[HI - 1]; EVT[HI] := EVT[HI - 1];
    END_FOR;
    EVC[1] := EVQ[QI]; EVT[1] := NOW_T;
    EV_N := EV_N + 1;
END_FOR;
EV1 := EVC[1]; EV2 := EVC[2]; EV3 := EVC[3]; EV4 := EVC[4]; EV5 := EVC[5];
EA1 := TO_REAL(NOW_T - EVT[1]) / 10.0; EA2 := TO_REAL(NOW_T - EVT[2]) / 10.0; EA3 := TO_REAL(NOW_T - EVT[3]) / 10.0;
EA4 := TO_REAL(NOW_T - EVT[4]) / 10.0; EA5 := TO_REAL(NOW_T - EVT[5]) / 10.0;

(* ---- the XC216's diagnosis: record 0xE00C (all diagnosis data of the AR) through its DAP (Node ID 29), every
   5 s while it reports diagnosis. First DiagnosisData block (0x0010): API 4, slot 2 (offset 10), subslot 2 (12),
   ChannelNumber 2, ChannelProperties 2, UserStructureIdentifier 2 (18); then entries: 0x8000 channel diagnosis
   (ChannelNumber, ChannelProperties, ChannelErrorType: 6 bytes), 0x8002 extended (+ ExtChannelErrorType,
   ExtChannelAddValue: 12 bytes) *)
XD_T := XD_T + TS;
CASE XD_PH OF
0:  XD_REQ := FALSE;
    IF XD_T >= 5.0 THEN
        XD_T := 0.0;
        IF NX_AR THEN XD_REQ := TRUE; XD_PH := 1; END_IF;
    END_IF;
1:  IF NOT XD.BUSY AND (XD.VALID OR XD.ERROR) OR XD_T > 20.0 THEN
        XD_OK := XD.VALID AND NOT XD.ERROR;
        XD_LEN := XD.LEN; XD_ST := TO_DINT(XD.STATUS);
        IF NOT XD_OK THEN XD_LEN := 0; END_IF;
        XD_BT := 0; XD_SLOT := 0; XD_SUB := 0; XD_USI := 0; XD_CH := 0; XD_CET := 0; XD_EXT := 0; XD_RIDX := 0; XD_ROFF := 0; XD_NB := 0;
        IF XD_LEN >= 26 THEN
            XD_BT := TO_INT(XD_BUF[0]) * 256 + TO_INT(XD_BUF[1]);
            XD_SLOT := TO_INT(XD_BUF[10]) * 256 + TO_INT(XD_BUF[11]);
            XD_SUB := TO_DINT(XD_BUF[12]) * 256 + TO_DINT(XD_BUF[13]);
            XD_USI := TO_DINT(XD_BUF[18]) * 256 + TO_DINT(XD_BUF[19]);
            XD_CH := TO_DINT(XD_BUF[20]) * 256 + TO_DINT(XD_BUF[21]);
            XD_CET := TO_DINT(XD_BUF[24]) * 256 + TO_DINT(XD_BUF[25]);
            IF XD_USI = 32770 AND XD_LEN >= 32 THEN        (* 0x8002 extended channel diagnosis *)
                XD_EXT := TO_DINT(XD_BUF[26]) * 256 + TO_DINT(XD_BUF[27]);
                XD_RIDX := TO_DINT(XD_BUF[28]) * 256 + TO_DINT(XD_BUF[29]);
                XD_ROFF := TO_DINT(XD_BUF[30]) * 256 + TO_DINT(XD_BUF[31]);
            END_IF;
            (* number of DiagnosisData blocks: walk the block lengths *)
            RP := 0;
            FOR HI := 1 TO 8 DO
                IF RP + 4 <= XD_LEN AND RP + 3 <= 127 THEN
                    SBL := TO_INT(XD_BUF[RP + 2]) * 256 + TO_INT(XD_BUF[RP + 3]);
                    IF SBL >= 2 THEN XD_NB := XD_NB + 1; RP := RP + 4 + SBL; ELSE RP := 1000; END_IF;
                END_IF;
            END_FOR;
        END_IF;
        XD_HEX1 := ''; XD_HEX2 := '';
        FOR HI := 0 TO 127 DO
            HB := TO_INT(XD_BUF[HI]);
            HX := CONCAT(MID(HEXT, 1, HB / 16 + 1), MID(HEXT, 1, HB MOD 16 + 1));
            IF HI < 64 THEN XD_HEX1 := CONCAT(XD_HEX1, HX); ELSE XD_HEX2 := CONCAT(XD_HEX2, HX); END_IF;
        END_FOR;
        XD_N := XD_N + 1;
        XD_REQ := FALSE; XD_PH := 0;
    END_IF;
END_CASE;
XD(REQ := XD_REQ, ID := DWORD#29, INDEX := XD_IDX, MLEN := 128, RECORD := XD_BUF);

(* ---- Raspberry Pi "pnpi" (p-net sample app): demo device, not used by the pump sequence or its interlocks ---- *)
PI_AR_OK := PI_AR_VALID;
PI_DIAG := PI_AR_VALID AND NOT PI_NO_DIAG;
PI_CNT := TO_INT(PI_IN AND BYTE#16#7F);
PI_BTN1 := (PI_IN AND BYTE#16#80) <> BYTE#0;
IF PI_CNT <> PI_CNT_PREV THEN PI_CNT_T := 0.0; ELSIF PI_CNT_T < 99.0 THEN PI_CNT_T := PI_CNT_T + TS; END_IF;
PI_CNT_PREV := PI_CNT;
PI_ALIVE := PI_AR_VALID AND PI_CNT_T < 1.0;
IF PI_LED THEN PI_OUT := BYTE#16#80; ELSE PI_OUT := BYTE#0; END_IF;
(* echo: new values every 2 s, compared 1.5 s later (the round trip takes a few update cycles of 32 ms) *)
PI_ET := PI_ET + 1;
IF PI_ET >= 20 THEN
    PI_ET := 0;
    PI_TX_I := PI_TX_I + 1;
    PI_TX_F := TEMP;
END_IF;
PI_EF_OUT := PI_TX_F;
PI_EI_OUT := PI_TX_I;
PI_RX_F := PI_EF_IN;
PI_RX_I := PI_EI_IN;
IF PI_ET = 15 THEN
    IF PI_AR_VALID THEN
        PI_ECHO_OK := (PI_RX_I = PI_TX_I * PI_GAIN) AND (ABS(PI_RX_F - PI_TX_F * TO_REAL(PI_GAIN)) < 0.001);
        PI_ECHO_N := PI_ECHO_N + 1;
        IF NOT PI_ECHO_OK THEN PI_ECHO_BAD := PI_ECHO_BAD + 1; END_IF;
    ELSE
        PI_ECHO_OK := FALSE;
    END_IF;
END_IF;
IF NOT PI_AR_VALID THEN PI_ECHO_OK := FALSE; END_IF;
