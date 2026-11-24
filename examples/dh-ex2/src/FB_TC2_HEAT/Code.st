(* 3.3 Heating: TV2 keeps TE2A on a curve from the outdoor temperature *)

(* Summer stop: set after TE2B_F has been above SUM_STOP for SUM_DLY, reset at once below SUM_START.
   Reset dominant; overlapping limits give heating. *)
fbSumDly(X := TE2B_F > SUM_STOP, DELAY := SUM_DLY, TS := TS);
xReset := TE2B_F < SUM_START;
IF xReset THEN
    SUMMER := FALSE;
ELSIF fbSumDly.Q THEN
    SUMMER := TRUE;
END_IF;

P2_RUN := HEAT_ENABLE AND NOT SUMMER;
P2_FAULT := P2_FLT_IN;
IF P2_FAULT THEN
    P2_ST := 2;
ELSIF P2_RUN THEN
    P2_ST := 1;
ELSE
    P2_ST := 0;
END_IF;

TE2A := TE2A_IN;
TE2A_FAULT := (TE2A < -20.0) OR (TE2A > 120.0);

(* Three-point curve at -20 / 0 / +20 degC outdoor, end values held outside, then TS_MIN...TS_MAX *)
IF TE2B_F <= -20.0 THEN
    rCrv := CRV_N20;
ELSIF TE2B_F <= 0.0 THEN
    rCrv := CRV_N20 + (CRV_0 - CRV_N20) * (TE2B_F + 20.0) / 20.0;
ELSIF TE2B_F <= 20.0 THEN
    rCrv := CRV_0 + (CRV_P20 - CRV_0) * TE2B_F / 20.0;
ELSE
    rCrv := CRV_P20;
END_IF;
IF rCrv < TS_MIN THEN
    rCrv := TS_MIN;
END_IF;
IF rCrv > TS_MAX THEN
    rCrv := TS_MAX;
END_IF;
HEAT_SP := rCrv;

(* No flow without P2: close TV2, do not send district heat back unused. *)
xCtrlEn := P2_RUN AND NOT TE2A_FAULT AND NOT P2_FAULT;
fbPI(PV := TE2A, SP := HEAT_SP, ENABLE := xCtrlEn, PBAND := HEAT_PID_P, TI := HEAT_PID_I, DZ := 0.5, TS := TS);
TV2 := fbPI.Y;

fbAlm(X := (TE2A > HEAT_HI_LIM) OR (TE2A < HEAT_LO_LIM), DELAY := HEAT_ALM_DLY, TS := TS);
HEAT_TEMP_ALM := fbAlm.Q;
