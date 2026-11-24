(* Modbus RTU probe: reads 6 registers from START of device SLAVE with function FC (3 holding, 4 input), once a
   second, through an AXL F RS UNI 1H in Modbus/RTU mode (the module adds and checks the CRC and keeps the timing).
   Process data: byte 0 command, byte 1 control / status bits, byte 2 length, bytes 3.. characters. *)
TICKS := TICKS + 1;
IF QUIET < 1000 THEN QUIET := QUIET + 1; END_IF;
ANSWERS := QUIET < 30;
IF FC <> 3 AND FC <> 4 THEN FC := 4; END_IF;
IF SLAVE < 1 THEN SLAVE := 1; END_IF;
IF SLAVE > 247 THEN SLAVE := 247; END_IF;
IF START < 0 THEN START := 0; END_IF;
CASE STEP OF
0:  (* pause, then the request: address, function, start, quantity *)
    CTRL_H := BYTE#0;
    CTRL_L := BYTE#0;
    IF TICKS >= 10 THEN
        TX01 := BYTE#6;
        TX02 := TO_BYTE(SLAVE);
        TX03 := TO_BYTE(FC);
        TX04 := TO_BYTE(START / 256);
        TX05 := TO_BYTE(START MOD 256);
        TX06 := BYTE#0;
        TX07 := BYTE#6;
        TOGGLE := NOT TOGGLE;
        IF TOGGLE THEN SENT := BYTE#16#10; ELSE SENT := BYTE#16#50; END_IF;      (* transmit; toggled to repeat *)
        CTRL_H := SENT;
        TICKS := 0; STEP := 1;
    END_IF;
1:  (* the module has taken the request when it echoes the command *)
    IF (STAT_H AND BYTE#16#80) <> BYTE#0 OR TICKS > 30 THEN
        N_BAD := N_BAD + 1; TICKS := 0; STEP := 4;
    ELSIF (STAT_H AND BYTE#16#70) = (SENT AND BYTE#16#70) THEN
        TICKS := 0; STEP := 2;
    END_IF;
2:  (* the answer: receive buffer not empty; or no answer in 2.5 s (bit 2); or a damaged one (bit 1) *)
    IF (STAT_L AND BYTE#16#04) <> BYTE#0 OR TICKS > 40 THEN
        N_NOANSWER := N_NOANSWER + 1; TICKS := 0; STEP := 4;
    ELSIF (STAT_L AND BYTE#16#02) <> BYTE#0 THEN
        N_BAD := N_BAD + 1; TICKS := 0; STEP := 4;
    ELSIF (STAT_L AND BYTE#16#01) <> BYTE#0 THEN
        IF TOGGLE THEN SENT := BYTE#16#30; ELSE SENT := BYTE#16#70; END_IF;      (* read characters *)
        CTRL_H := SENT;
        TICKS := 0; STEP := 3;
    END_IF;
3:  (* the characters are in the process data when the read command is echoed:
       RX01 length, RX02 address, RX03 function, RX04 byte count, RX05.. data *)
    IF (STAT_H AND BYTE#16#70) = (SENT AND BYTE#16#70) THEN
        QUIET := 0;
        IF TO_INT(RX03) >= 128 THEN
            N_REFUSED := N_REFUSED + 1; EXC := TO_INT(RX04);      (* 2 = no such address, 1 = no such function *)
        ELSIF TO_INT(RX04) = 12 THEN
            N_OK := N_OK + 1; EXC := 0;
            R1 := TO_DINT(RX05) * 256 + TO_DINT(RX06);
            R2 := TO_DINT(RX07) * 256 + TO_DINT(RX08);
            R3 := TO_DINT(RX09) * 256 + TO_DINT(RX10);
            R4 := TO_DINT(RX11) * 256 + TO_DINT(RX12);
            R5 := TO_DINT(RX13) * 256 + TO_DINT(RX14);
            R6 := TO_DINT(RX15) * 256 + TO_DINT(RX16);
        ELSE
            N_BAD := N_BAD + 1;
        END_IF;
        TICKS := 0; STEP := 0;
    ELSIF TICKS > 30 THEN
        N_BAD := N_BAD + 1; TICKS := 0; STEP := 4;
    END_IF;
4:  (* after an error: reset the module's error bits *)
    CTRL_H := BYTE#0;
    CTRL_L := BYTE#16#06;
    IF TICKS > 5 THEN
        CTRL_L := BYTE#0; TICKS := 0; STEP := 0;
    END_IF;
END_CASE;
(* each pair of registers as a float, both word orders: one of them makes sense *)
D := SHL(TO_DWORD(R1), 16) OR TO_DWORD(R2); DEC(D := D); HI1 := DEC.V;
D := SHL(TO_DWORD(R3), 16) OR TO_DWORD(R4); DEC(D := D); HI2 := DEC.V;
D := SHL(TO_DWORD(R5), 16) OR TO_DWORD(R6); DEC(D := D); HI3 := DEC.V;
D := SHL(TO_DWORD(R2), 16) OR TO_DWORD(R1); DEC(D := D); LO1 := DEC.V;
D := SHL(TO_DWORD(R4), 16) OR TO_DWORD(R3); DEC(D := D); LO2 := DEC.V;
D := SHL(TO_DWORD(R6), 16) OR TO_DWORD(R5); DEC(D := D); LO3 := DEC.V;
