(* First-order low-pass. The first cycle takes the input as it is. *)
IF NOT xInit THEN
    Y := X;
    xInit := TRUE;
END_IF;
IF TAU <= TS THEN
    Y := X;
ELSE
    Y := Y + (X - Y) * TS / TAU;
END_IF;
