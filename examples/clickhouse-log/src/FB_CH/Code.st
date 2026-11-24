(* ClickHouse over its HTTP interface (plain TCP, HTTP/1.0: one request per connection, the server closes it).
   Every SAMPLE_S the N_TAGS values are kept with the time they were taken; every SEND_S they go out as
   INSERT INTO <TABLE> (tag, value, ago_ms) FORMAT JSONEachRow, one row per value, ago_ms = how old the value is
   when sent (the table makes the time stamp: ts DEFAULT now64(3) - ago_ms). Every QUERY_S the QUERY runs and the
   numbers of its answer (one per line, FORMAT TSV is added) land in Q_VALS.
   A failed insert keeps its samples for the next try; 60 samples at most, newer ones are dropped and counted. *)
FAIL := FALSE;

(* ---- the clock and the samples ---- *)
CLK := CLK + TO_DINT(TS * 1000.0);
IF N_TAGS < 0 THEN N := 0; ELSIF N_TAGS > 16 THEN N := 16; ELSE N := N_TAGS; END_IF;
SACC := SACC + TS;
IF ENABLE AND N > 0 AND SACC >= SAMPLE_S THEN
    SACC := SACC - SAMPLE_S;
    IF SACC > SAMPLE_S THEN SACC := 0.0; END_IF;
    IF NSMP < 60 THEN
        FOR K := 1 TO N DO
            SMP[NSMP * 16 + K - 1] := VALS[K];
        END_FOR;
        SMP_T[NSMP] := CLK;
        NSMP := NSMP + 1;
    ELSE
        N_DROP := N_DROP + TO_UDINT(N);
    END_IF;
END_IF;
PENDING := NSMP;
PACC := PACC + TS;
QACC := QACC + TS;
OK_AGE := OK_AGE + TS;
IF OK_AGE > 100000.0 THEN OK_AGE := 100000.0; END_IF;
Q_AGE := Q_AGE + TS;
IF Q_AGE > 100000.0 THEN Q_AGE := 100000.0; END_IF;

(* ---- names into bytes, once ---- *)
IF NOT INIT_DONE THEN
    FOR K := 1 TO 16 DO
        TT(CMD := 0);
        TT(CMD := 5, S := TAGS[K]);
        TAGN[K] := TT.NB;
        IF TAGN[K] > 32 THEN TAGN[K] := 32; END_IF;
        FOR J := 0 TO TAGN[K] - 1 DO
            TAGB[(K - 1) * 32 + J] := TT.BUF[J];
        END_FOR;
    END_FOR;
    TT(CMD := 0); TT(CMD := 1, S := '{`tag`:`');
    P1N := TT.NB; FOR J := 0 TO P1N - 1 DO P1[J] := TT.BUF[J]; END_FOR;
    TT(CMD := 0); TT(CMD := 1, S := '`,`value`:');
    P2N := TT.NB; FOR J := 0 TO P2N - 1 DO P2[J] := TT.BUF[J]; END_FOR;
    TT(CMD := 0); TT(CMD := 1, S := ',`ago_ms`:');
    P3N := TT.NB; FOR J := 0 TO P3N - 1 DO P3[J] := TT.BUF[J]; END_FOR;
    TT(CMD := 0); TT(CMD := 1, S := '}|');
    P4N := TT.NB; FOR J := 0 TO P4N - 1 DO P4[J] := TT.BUF[J]; END_FOR;
    INIT_DONE := TRUE;
END_IF;

(* ---- the socket blocks, with what the code below asked for in the last cycle ---- *)
SOCK(ACTIVATE := SOCK_ACT, IS_SRV := FALSE, BIND_PORT := 0, DEST_IP := HOST, DEST_PORT := PORT);
SND(REQ := TX_REQ, HANDLE := SOCK.HANDLE, DATA_CNT := TO_UDINT(TX_LEN), DATA := TXBUF);
TX_LAST := TX_REQ;
IF SND.DONE OR SND.ERROR THEN
    TX_REQ := FALSE;
END_IF;
RCV(EN_R := RX_EN, HANDLE := SOCK.HANDLE, EXP_DATA_CNT := 0, DATA := RXCHUNK);
IF RX_EN AND RCV.NDR THEN
    J := TO_INT(RCV.DATA_CNT);
    IF J > 1024 THEN J := 1024; END_IF;
    IF RXFILL + J > 2048 THEN J := 2048 - RXFILL; END_IF;
    FOR I := 0 TO J - 1 DO
        RXBUF[RXFILL + I] := RXCHUNK[I];
    END_FOR;
    RXFILL := RXFILL + J;
END_IF;

ACC := ACC + TS;
IF ACC > 1000.0 THEN ACC := 1000.0; END_IF;
IF NOT ENABLE AND STATE <> 0 AND STATE <> 9 THEN
    FAIL := TRUE; FAIL_ST := WORD#16#0000;
END_IF;
CASE STATE OF
0:  (* idle; the socket has been closed for at least 1 s *)
    IF ENABLE AND ACC >= 1.0 AND NOT SOCK.ACTIVE AND NOT SOCK.BUSY THEN
        IF NSMP > 0 AND PACC >= SEND_S THEN
            KIND := 1;
            BB(CMD := 0);
            BB(CMD := 1, S := 'INSERT INTO ');
            BB(CMD := 5, S := TABLE);
            BB(CMD := 1, S := ' (tag, value, ago_ms) FORMAT JSONEachRow|');
            R_S := 0;
            ROWS := 0;
            STATE := 5;
        ELSIF QUERY_S > 0.0 AND LEN(QUERY) > 0 AND QACC >= QUERY_S THEN
            KIND := 2;
            BB(CMD := 0);
            BB(CMD := 1, S := QUERY);
            BB(CMD := 1, S := ' FORMAT TSV|');
            STATE := 6;
        END_IF;
    END_IF;
5:  (* rows, at most 4 samples a cycle, whole samples only, while they fit (about 25 samples of 10 values) *)
    FOR I := 1 TO 4 DO
        IF R_S < NSMP AND BB.NB < 12000 - N * 70 THEN
            FOR K := 1 TO N DO
                BB(CMD := 6, A := P1, AN := P1N);
                FOR J := 0 TO TAGN[K] - 1 DO
                    TMP[J] := TAGB[(K - 1) * 32 + J];
                END_FOR;
                BB(CMD := 6, A := TMP, AN := TAGN[K]);
                BB(CMD := 6, A := P2, AN := P2N);
                BB(CMD := 2, R := SMP[R_S * 16 + K - 1]);
                BB(CMD := 6, A := P3, AN := P3N);
                BB(CMD := 3, D := CLK - SMP_T[R_S]);
                BB(CMD := 6, A := P4, AN := P4N);
                ROWS := ROWS + 1;
            END_FOR;
            R_S := R_S + 1;
        END_IF;
    END_FOR;
    IF R_S >= NSMP OR BB.NB >= 12000 - N * 70 THEN
        USED := R_S;
        STATE := 6;
    END_IF;
6:  (* the header, then header and body into TXBUF, then open *)
    HB(CMD := 0);
    HB(CMD := 1, S := 'POST / HTTP/1.0^Host: ');
    HB(CMD := 5, S := HOST);
    HB(CMD := 1, S := '^X-ClickHouse-User: ');
    HB(CMD := 5, S := USER);
    HB(CMD := 1, S := '^X-ClickHouse-Key: ');
    HB(CMD := 5, S := KEY);
    HB(CMD := 1, S := '^Content-Type: text/plain^Content-Length: ');
    HB(CMD := 3, D := TO_DINT(BB.NB));
    HB(CMD := 1, S := '^^');
    IF HB.NB + BB.NB > 12800 OR BB.OVER OR HB.OVER THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0004;
    ELSE
        FOR I := 0 TO HB.NB - 1 DO
            TXBUF[I] := HB.BUF[I];
        END_FOR;
        FOR I := 0 TO BB.NB - 1 DO
            TXBUF[HB.NB + I] := BB.BUF[I];
        END_FOR;
        TX_LEN := HB.NB + BB.NB;
        RXFILL := 0;
        HTTP_CODE := 0;
        SOCK_ACT := TRUE;
        ACC := 0.0;
        STATE := 1;
    END_IF;
1:  (* opening *)
    IF SOCK.ERROR THEN
        FAIL := TRUE; FAIL_ST := SOCK.STATUS;
    ELSIF SOCK.ACTIVE THEN
        RX_EN := TRUE;
        TX_REQ := TRUE;
        ACC := 0.0;
        STATE := 2;
    ELSIF ACC > 10.0 THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0002;
    END_IF;
2:  (* sending *)
    IF SND.ERROR THEN
        FAIL := TRUE; FAIL_ST := SND.STATUS;
    ELSIF SND.DONE THEN
        ACC := 0.0;
        STATE := 3;
    ELSIF ACC > 10.0 THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0002;
    END_IF;
3:  (* waiting: the answer is complete when the server has closed the connection *)
    IF NOT SOCK.ACTIVE OR SOCK.ERROR OR RCV.ERROR THEN
        IF RXFILL >= 12 THEN
            DONE_RX := TRUE;
        ELSE
            FAIL := TRUE; FAIL_ST := WORD#16#0003;
        END_IF;
    ELSIF ACC > 15.0 THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0002;
    END_IF;
9:  (* after an error: closed, wait 10 s *)
    IF ACC >= 10.0 THEN
        ACC := 0.0;
        STATE := 0;
    END_IF;
END_CASE;

(* ---- a complete answer: "HTTP/1.x NNN ...", empty line, body ---- *)
IF DONE_RX THEN
    DONE_RX := FALSE;
    HTTP_CODE := (TO_INT(RXBUF[9]) - 48) * 100 + (TO_INT(RXBUF[10]) - 48) * 10 + (TO_INT(RXBUF[11]) - 48);
    BODY := RXFILL;
    FOR I := 0 TO RXFILL - 4 DO
        IF BODY = RXFILL AND RXBUF[I] = BYTE#13 AND RXBUF[I + 1] = BYTE#10 AND RXBUF[I + 2] = BYTE#13 AND RXBUF[I + 3] = BYTE#10 THEN
            BODY := I + 4;
        END_IF;
    END_FOR;
    IF HTTP_CODE = 200 THEN
        N_POST := N_POST + 1;
        IF KIND = 1 THEN
            N_ROWS := N_ROWS + TO_UDINT(ROWS);
            OK_AGE := 0.0;
            (* drop the samples that were stored *)
            FOR I := USED TO NSMP - 1 DO
                SMP_T[I - USED] := SMP_T[I];
                FOR K := 0 TO 15 DO
                    SMP[(I - USED) * 16 + K] := SMP[I * 16 + K];
                END_FOR;
            END_FOR;
            NSMP := NSMP - USED;
            IF NSMP >= 5 THEN
                PACC := SEND_S;                (* a backlog: send the next batch right away *)
            ELSE
                PACC := 0.0;
            END_IF;
        ELSE
            (* numbers, one per line (also tab separated); lines that are not numbers are skipped *)
            Q_N := 0;
            V := 0.0; DV := 0.0; HAS := FALSE; IS_NEG := FALSE; FRAC := FALSE;
            FOR I := BODY TO RXFILL DO
                IF I < RXFILL THEN B := RXBUF[I]; ELSE B := BYTE#10; END_IF;
                IF B >= BYTE#48 AND B <= BYTE#57 THEN
                    IF FRAC THEN
                        DV := DV * 10.0;
                        V := V + TO_REAL(TO_INT(B) - 48) / DV;
                    ELSE
                        V := V * 10.0 + TO_REAL(TO_INT(B) - 48);
                    END_IF;
                    HAS := TRUE;
                ELSIF B = BYTE#45 THEN
                    IS_NEG := TRUE;
                ELSIF B = BYTE#46 THEN
                    FRAC := TRUE; DV := 1.0;
                ELSIF B = BYTE#10 OR B = BYTE#9 THEN
                    IF HAS AND Q_N < 48 THEN
                        Q_N := Q_N + 1;
                        IF IS_NEG THEN Q_VALS[Q_N] := -V; ELSE Q_VALS[Q_N] := V; END_IF;
                    END_IF;
                    V := 0.0; DV := 0.0; HAS := FALSE; IS_NEG := FALSE; FRAC := FALSE;
                END_IF;
            END_FOR;
            Q_AGE := 0.0;
            QACC := 0.0;
        END_IF;
    ELSE
        N_ERR := N_ERR + 1;
        IF KIND = 1 THEN PACC := 0.0; ELSE QACC := 0.0; END_IF;
    END_IF;
    SOCK_ACT := FALSE;
    RX_EN := FALSE;
    TX_REQ := FALSE;
    ACC := 0.0;
    STATE := 0;
END_IF;

IF FAIL THEN
    ERR_STATUS := FAIL_ST;
    N_ERR := N_ERR + 1;
    IF KIND = 1 THEN PACC := 0.0; ELSE QACC := 0.0; END_IF;
    SOCK_ACT := FALSE;
    RX_EN := FALSE;
    TX_REQ := FALSE;
    ACC := 0.0;
    IF ENABLE THEN STATE := 9; ELSE STATE := 0; END_IF;
END_IF;
