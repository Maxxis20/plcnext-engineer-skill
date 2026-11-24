(* Profinet controller side, device plc-b (16 of 512 bytes used, high byte first).
   From B: 0-1 temperature x10, 2-3 humidity x10, 4-5 battery mV, 6-7 B's counter, 8 status (bit 0 Modbus up),
           10-11 our counter sent back.   To B: 0-1 our counter, 2-3 our set value x10. *)
B_TEMP := TO_REAL(TO_INT(SHL(TO_WORD(PN_IN[0]), 8) OR TO_WORD(PN_IN[1]))) / 10.0;
B_HUM := TO_REAL(TO_INT(SHL(TO_WORD(PN_IN[2]), 8) OR TO_WORD(PN_IN[3]))) / 10.0;
B_BAT := TO_INT(SHL(TO_WORD(PN_IN[4]), 8) OR TO_WORD(PN_IN[5]));
B_BEAT := TO_INT(SHL(TO_WORD(PN_IN[6]), 8) OR TO_WORD(PN_IN[7]));
B_MB_OK := (PN_IN[8] AND BYTE#16#01) <> BYTE#0;
B_ECHO := TO_INT(SHL(TO_WORD(PN_IN[10]), 8) OR TO_WORD(PN_IN[11]));
ACC := ACC + TS;
SEEN := SEEN + TS;
IF B_BEAT <> LAST THEN
    LAST := B_BEAT;
    SEEN := 0.0;
END_IF;
B_ALIVE := SEEN < 3.0;
IF ACC >= 1.0 THEN
    ACC := 0.0;
    A_CNT := A_CNT + 1;
    IF A_CNT > 30000 THEN
        A_CNT := 0;
    END_IF;
END_IF;
W := TO_WORD(A_CNT);
PN_OUT[0] := TO_BYTE(SHR(W, 8));
PN_OUT[1] := TO_BYTE(W AND WORD#16#FF);
W := TO_WORD(TO_INT(SP * 10.0));
PN_OUT[2] := TO_BYTE(SHR(W, 8));
PN_OUT[3] := TO_BYTE(W AND WORD#16#FF);
