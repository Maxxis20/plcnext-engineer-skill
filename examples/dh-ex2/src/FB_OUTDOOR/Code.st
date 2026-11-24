(* 3.1 Outdoor temperature: range check, fallback value, slow filter *)
TE2B := TE2B_IN;
TE2B_FAULT := (TE2B < -45.0) OR (TE2B > 50.0);
IF TE2B_FAULT THEN
    rSel := TOUT_FALLBACK;
ELSE
    rSel := TE2B;
END_IF;
fbFilt(X := rSel, TAU := TOUT_FILT_T, TS := TS);
TE2B_F := fbFilt.Y;
