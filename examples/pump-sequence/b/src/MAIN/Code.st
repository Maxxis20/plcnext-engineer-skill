(* Modbus TCP to Profinet: three registers of a Modbus TCP server go to the Profinet controller, 16 bytes each way,
   big endian. To the controller: 0-1 temperature x10, 2-3 humidity x10, 4-5 battery mV (the registers as they are),
   6-7 our counter, 8 status (bit 0 Modbus server answers), 10-11 the controller's counter sent back.
   From the controller: 0-1 its counter, 2-3 its room temperature x10. *)
TEMP := TO_REAL(TO_INT(T10)) / 10.0;
HUM := TO_REAL(TO_INT(H10)) / 10.0;
ACC := ACC + TS;
IF ACC >= 1.0 THEN
    ACC := 0.0;
    BEAT := BEAT + 1;
    IF BEAT > 30000 THEN
        BEAT := 0;
    END_IF;
END_IF;
PND_S1_OUTPUTS[0] := TO_BYTE(SHR(T10, 8));
PND_S1_OUTPUTS[1] := TO_BYTE(T10 AND WORD#16#FF);
PND_S1_OUTPUTS[2] := TO_BYTE(SHR(H10, 8));
PND_S1_OUTPUTS[3] := TO_BYTE(H10 AND WORD#16#FF);
PND_S1_OUTPUTS[4] := TO_BYTE(SHR(VDD, 8));
PND_S1_OUTPUTS[5] := TO_BYTE(VDD AND WORD#16#FF);
W := TO_WORD(BEAT);
PND_S1_OUTPUTS[6] := TO_BYTE(SHR(W, 8));
PND_S1_OUTPUTS[7] := TO_BYTE(W AND WORD#16#FF);
IF MB_STATE = 1 THEN
    PND_S1_OUTPUTS[8] := BYTE#16#01;
ELSE
    PND_S1_OUTPUTS[8] := BYTE#0;
END_IF;
PND_S1_OUTPUTS[10] := PND_S1_INPUTS[0];
PND_S1_OUTPUTS[11] := PND_S1_INPUTS[1];
PN_VALID := PND_S1_VALID_DATA_CYCLE;
FROM_A_CNT := TO_INT(SHL(TO_WORD(PND_S1_INPUTS[0]), 8) OR TO_WORD(PND_S1_INPUTS[1]));
FROM_A_TEMP := TO_REAL(TO_INT(SHL(TO_WORD(PND_S1_INPUTS[2]), 8) OR TO_WORD(PND_S1_INPUTS[3]))) / 10.0;
