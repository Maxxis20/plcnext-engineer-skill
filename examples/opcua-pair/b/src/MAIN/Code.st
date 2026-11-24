(* the firmware's OPC UA client copies A_TEMP from A and TO_A_VALUE, TO_A_BEAT to A; the program only uses them *)
TO_A_VALUE := A_TEMP + 100.0;             (* something A can recognise as coming back from B *)
BEAT_ACC := BEAT_ACC + TS;
IF BEAT_ACC >= 1.0 THEN
    BEAT_ACC := 0.0;
    TO_A_BEAT := TO_A_BEAT + 1;
    IF TO_A_BEAT > 9999 THEN
        TO_A_BEAT := 0;
    END_IF;
END_IF;
