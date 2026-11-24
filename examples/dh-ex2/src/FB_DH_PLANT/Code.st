(* Teaching model of the substation, not calibrated.
   Hot water exchanger: TE1 -> 8 + 82 * v / (v + 3.66 * (1 + tap)), cold water 8, primary 90 degC, lag 8 s.
   Heating exchanger:   TE2A -> 25 + 70 * v / (v + 60), return 25, primary 95 degC, lag 30 s.
   P1 is the circulation pump: the hot water exchanger works without it. P2 stopped: TE2A settles at 20 degC. *)
TE2B := TOUT;
IF TE2B < -50.0 THEN TE2B := -50.0; END_IF;
IF TE2B > 50.0 THEN TE2B := 50.0; END_IF;

rTap := DHW_TAP;
IF rTap < 0.0 THEN rTap := 0.0; END_IF;
IF rTap > 30.0 THEN rTap := 30.0; END_IF;

TV1_POS := TV1_CMD;
IF TV1_POS < 0.0 THEN TV1_POS := 0.0; END_IF;
IF TV1_POS > 100.0 THEN TV1_POS := 100.0; END_IF;
TV2_POS := TV2_CMD;
IF TV2_POS < 0.0 THEN TV2_POS := 0.0; END_IF;
IF TV2_POS > 100.0 THEN TV2_POS := 100.0; END_IF;

P1_ON := P1_CMD AND NOT P1_TRIP;
P2_ON := P2_CMD AND NOT P2_TRIP;

rTe1s := 8.0 + 82.0 * TV1_POS / (TV1_POS + 3.66 * (1.0 + rTap));
fbTe1(X := rTe1s, TAU := 8.0, TS := TS);
TE1 := fbTe1.Y;

IF P2_ON THEN
    rTe2s := 25.0 + 70.0 * TV2_POS / (TV2_POS + 60.0);
ELSE
    rTe2s := 20.0;
END_IF;
fbTe2(X := rTe2s, TAU := 30.0, TS := TS);
TE2A := fbTe2.Y;
