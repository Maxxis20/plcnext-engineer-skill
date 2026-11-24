(* Simulated drive and safety chain for the controller's start sequence, over Profinet.
   From the controller: byte 4 bit 0 run, bit 1 reset; bytes 6-7 setpoint 0..1000.
   To the controller: byte 12 bit 0 ready, bit 1 running, bit 2 fault, bit 3 safety chain ok, bit 4 local;
   bytes 14-15 actual speed 0..1000. Without Profinet data the drive takes no commands (stops unless local). *)
PN_OK := PND_S1_VALID_DATA_CYCLE;
IF PN_OK THEN
    RUN_CMD := (PND_S1_INPUTS[4] AND BYTE#16#01) <> BYTE#0;
    DRIVE_RESET := (PND_S1_INPUTS[4] AND BYTE#16#02) <> BYTE#0;
    SPEED_SP := TO_INT(SHL(TO_WORD(PND_S1_INPUTS[6]), 8) OR TO_WORD(PND_S1_INPUTS[7]));
ELSE
    RUN_CMD := FALSE;
    DRIVE_RESET := FALSE;
END_IF;
SIS_OK := NOT SIM_ESTOP;
LOCAL := SIM_LOCAL;
IF SIM_TRIP THEN
    FAULT := TRUE;
ELSIF DRIVE_RESET OR LOCAL_RESET THEN
    FAULT := FALSE;
    LOCAL_RESET := FALSE;
END_IF;
IF LOCAL THEN
    RUN_REQ := LOCAL_RUN;
    SP := LOCAL_SP;
ELSE
    RUN_REQ := RUN_CMD;
    SP := SPEED_SP;
    LOCAL_RUN := FALSE;
END_IF;
IF SP < 0 THEN
    SP := 0;
ELSIF SP > 1000 THEN
    SP := 1000;
END_IF;
READY := NOT FAULT AND SIS_OK;
IF RUN_REQ AND READY THEN
    TARGET := TO_REAL(SP);
ELSE
    TARGET := 0.0;
END_IF;
IF SPF < TARGET THEN
    SPF := SPF + RAMP * TS;
    IF SPF > TARGET THEN
        SPF := TARGET;
    END_IF;
ELSIF SPF > TARGET THEN
    SPF := SPF - RAMP * TS;
    IF SPF < TARGET THEN
        SPF := TARGET;
    END_IF;
END_IF;
SPEED_ACT := TO_INT(SPF);
RUNNING := RUN_REQ AND READY AND NOT SIM_NO_FB AND SP > 0 AND SPEED_ACT * 10 >= SP * 9;
B := BYTE#0;
IF READY THEN
    B := B OR BYTE#16#01;
END_IF;
IF RUNNING THEN
    B := B OR BYTE#16#02;
END_IF;
IF FAULT THEN
    B := B OR BYTE#16#04;
END_IF;
IF SIS_OK THEN
    B := B OR BYTE#16#08;
END_IF;
IF LOCAL THEN
    B := B OR BYTE#16#10;
END_IF;
PND_S1_OUTPUTS[12] := B;
W := TO_WORD(SPEED_ACT);
PND_S1_OUTPUTS[14] := TO_BYTE(SHR(W, 8));
PND_S1_OUTPUTS[15] := TO_BYTE(W AND WORD#16#FF);
