(* a value that moves slowly between 20 and 24, so the other side sees it change *)
PHASE := PHASE + TS;
IF PHASE >= 120.0 THEN
    PHASE := 0.0;
END_IF;
IF PHASE < 60.0 THEN
    TEMP := 20.0 + PHASE / 15.0;
ELSE
    TEMP := 28.0 - PHASE / 15.0;
END_IF;

(* the link from B is alive while its counter moves *)
IF REMOTE_BEAT <> BEAT_LAST THEN
    BEAT_LAST := REMOTE_BEAT;
    BEAT_AGE := 0.0;
ELSE
    BEAT_AGE := BEAT_AGE + TS;
    IF BEAT_AGE > 1000.0 THEN BEAT_AGE := 1000.0; END_IF;
END_IF;
LINK_OK := BEAT_AGE < 5.0;
