(* 3.2 Domestic hot water: TV1 keeps TE1 at DHW_SP *)
TE1 := TE1_IN;
TE1_FAULT := (TE1 < -20.0) OR (TE1 > 120.0);
P1_RUN := DHW_ENABLE;
P1_FAULT := P1_FLT_IN;
IF P1_FAULT THEN
    P1_ST := 2;
ELSIF P1_RUN THEN
    P1_ST := 1;
ELSE
    P1_ST := 0;
END_IF;

(* A P1 fault only alarms: tapping still flows through the exchanger, so TV1 keeps controlling. *)
xCtrlEn := P1_RUN AND NOT TE1_FAULT;
fbPI(PV := TE1, SP := DHW_SP, ENABLE := xCtrlEn, PBAND := DHW_PID_P, TI := DHW_PID_I, DZ := 0.5, TS := TS);
TV1 := fbPI.Y;

fbAlm(X := xCtrlEn AND ((TE1 > DHW_HI_LIM) OR (TE1 < DHW_LO_LIM)), DELAY := DHW_ALM_DLY, TS := TS);
DHW_TEMP_ALM := fbAlm.Q;
