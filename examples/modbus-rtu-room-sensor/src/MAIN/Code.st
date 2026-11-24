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
