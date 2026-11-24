(* FB_CH on its own: one value that counts up, stored every second, sent every 10 s; the query counts its rows
   once a minute. Server, user and table: README.md. *)
RAMP := RAMP + 0.1;
TG[1] := 'RAMP';
VL[1] := RAMP;
CH(ENABLE := CH_ON, HOST := '192.168.1.60', USER := 'plc_writer', KEY := '%%ENV:CLICKHOUSE_PASSWORD%%', N_TAGS := 1,
   TAGS := TG, VALS := VL, QUERY := 'SELECT count() FROM plc.samples WHERE tag = @RAMP@', TS := 0.1);
CH_STATE := CH.STATE;
CH_ROWS := CH.N_ROWS;
CH_ERR := CH.N_ERR;
CH_CODE := CH.HTTP_CODE;
Q1 := CH.Q_VALS[1];
QN := CH.Q_N;
