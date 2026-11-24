(* PI controller, heating direction (output rises when PV is below SP).
   Gain = 100 / proportional band. Integral is held inside the output range (anti wind-up). *)
IF NOT ENABLE THEN
    rI := 0.0;
    Y := 0.0;
ELSE
    rErr := SP - PV;
    IF ABS(rErr) < DZ THEN
        rErr := 0.0;
    END_IF;
    IF PBAND > 0.0 THEN
        rKp := 100.0 / PBAND;
    ELSE
        rKp := 0.0;
    END_IF;
    rP := rKp * rErr;
    IF TI > 0.0 THEN
        rI := rI + rKp * rErr * TS / TI;
    ELSE
        rI := 0.0;
    END_IF;
    rU := rP + rI;
    IF rU > 100.0 THEN
        rI := 100.0 - rP;
        rU := 100.0;
    ELSIF rU < 0.0 THEN
        rI := 0.0 - rP;
        rU := 0.0;
    END_IF;
    Y := rU;
END_IF;
