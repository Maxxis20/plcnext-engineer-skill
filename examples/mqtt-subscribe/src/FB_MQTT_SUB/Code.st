(* Minimal MQTT 3.1.1 subscriber over plain TCP: one topic filter, QoS 0, clean session, keep alive 60 s.
   STATE: 0 closed, 1 opening the socket, 2 CONNECT out / wait CONNACK, 3 SUBSCRIBE out / wait SUBACK,
   4 connected (PINGREQ every 30 s), 9 closed after an error, wait 5 s.
   The socket blocks are called once at the top with what the code below asked for in the last cycle. *)
NEW_MSG := FALSE;
FAIL := FALSE;
GO_CLOSE := FALSE;

SOCK(ACTIVATE := SOCK_ACT, IS_SRV := FALSE, BIND_PORT := 0, DEST_IP := BROKER_IP, DEST_PORT := BROKER_PORT);
SND(REQ := TX_REQ, HANDLE := SOCK.HANDLE, DATA_CNT := TO_UDINT(TX_LEN), DATA := TXBUF);
TX_LAST := TX_REQ;
IF SND.DONE OR SND.ERROR THEN
    TX_REQ := FALSE;
END_IF;
RCV(EN_R := RX_EN, HANDLE := SOCK.HANDLE, EXP_DATA_CNT := 0, DATA := RXCHUNK);

(* errors of the socket blocks; ERROR is TRUE for one cycle, STATUS is valid in that cycle *)
IF STATE >= 1 AND STATE <= 4 THEN
    IF SOCK.ERROR THEN FAIL := TRUE; FAIL_ST := SOCK.STATUS; END_IF;
    IF SND.ERROR THEN FAIL := TRUE; FAIL_ST := SND.STATUS; END_IF;
    IF RCV.ERROR THEN FAIL := TRUE; FAIL_ST := RCV.STATUS; END_IF;
    IF STATE >= 2 AND NOT SOCK.ACTIVE AND NOT FAIL THEN
        FAIL := TRUE; FAIL_ST := SOCK.STATUS;          (* connection lost *)
    END_IF;
END_IF;

(* append what TCP_RECEIVE delivered (EXP_DATA_CNT 0: all bytes since the last call, NDR when there are any) *)
IF RX_EN AND RCV.NDR AND NOT FAIL THEN
    N := TO_INT(RCV.DATA_CNT);
    IF N > 1024 THEN N := 1024; END_IF;
    IF RXFILL + N > 4096 THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0001;
    ELSE
        FOR I := 0 TO N - 1 DO
            RXBUF[RXFILL + I] := RXCHUNK[I];
        END_FOR;
        RXFILL := RXFILL + N;
    END_IF;
END_IF;

(* take complete MQTT packets from the front of RXBUF; at most one PUBLISH per cycle *)
CONNACK_OK := FALSE;
SUBACK_OK := FALSE;
PKT_BAD := FALSE;
MORE := (STATE >= 2) AND (STATE <= 4) AND NOT FAIL;
FOR K := 1 TO 8 DO
    IF MORE AND RXFILL >= 2 THEN
        (* remaining length: 1 to 3 bytes, 7 bits each, bit 7 = another byte follows *)
        RL := 0;
        MULT := 1;
        P := 1;
        LEN_DONE := FALSE;
        FOR J := 1 TO 3 DO
            IF NOT LEN_DONE AND P < RXFILL THEN
                B := RXBUF[P];
                RL := RL + TO_DINT(TO_INT(B AND BYTE#16#7F)) * MULT;
                MULT := MULT * 128;
                P := P + 1;
                LEN_DONE := (B AND BYTE#16#80) = BYTE#0;
            END_IF;
        END_FOR;
        IF NOT LEN_DONE THEN
            IF P >= 4 THEN
                PKT_BAD := TRUE;                       (* longer than 3 length bytes: not for us *)
            END_IF;
            MORE := FALSE;                             (* else: length bytes not all here yet *)
        ELSIF RL > TO_DINT(4096 - P) THEN
            PKT_BAD := TRUE;                           (* would never fit the buffer *)
            MORE := FALSE;
        ELSE
            TOT := P + TO_INT(RL);                     (* whole packet: fixed header + remaining length *)
            IF RXFILL < TOT THEN
                MORE := FALSE;                         (* rest of the packet not here yet *)
            ELSE
                IDLE_ACC := 0.0;
                PKT := RXBUF[0] AND BYTE#16#F0;
                IF PKT = BYTE#16#20 THEN               (* CONNACK: flags, return code *)
                    IF RL >= 2 AND RXBUF[P + 1] = BYTE#0 THEN
                        CONNACK_OK := TRUE;
                    ELSE
                        PKT_BAD := TRUE;
                    END_IF;
                ELSIF PKT = BYTE#16#90 THEN            (* SUBACK: packet id, return code (16#80 = refused) *)
                    IF RL >= 3 AND RXBUF[P + 2] <> BYTE#16#80 THEN
                        SUBACK_OK := TRUE;
                    ELSE
                        PKT_BAD := TRUE;
                    END_IF;
                ELSIF PKT = BYTE#16#30 THEN            (* PUBLISH: topic length, topic, [packet id if QoS > 0], payload *)
                    TL := TO_INT(RXBUF[P]) * 256 + TO_INT(RXBUF[P + 1]);
                    PS := P + 2 + TL;
                    IF (RXBUF[0] AND BYTE#16#06) <> BYTE#0 THEN
                        PS := PS + 2;
                    END_IF;
                    PL := TOT - PS;
                    IF RL < 2 OR PL < 0 THEN
                        PKT_BAD := TRUE;
                    ELSE
                        IF PL > 2048 THEN PL := 2048; END_IF;
                        FOR I := 0 TO PL - 1 DO
                            PAYLOAD[I] := RXBUF[PS + I];
                        END_FOR;
                        PAYLOAD_LEN := PL;
                        NEW_MSG := TRUE;
                        MSG_CNT := MSG_CNT + 1;
                        MORE := FALSE;                 (* next one in the next cycle *)
                    END_IF;
                END_IF;                                (* PINGRESP 16#D0 and others: only IDLE_ACC *)
                (* drop the packet: shift the rest down *)
                FOR I := TOT TO RXFILL - 1 DO
                    RXBUF[I - TOT] := RXBUF[I];
                END_FOR;
                RXFILL := RXFILL - TOT;
            END_IF;
        END_IF;
        IF PKT_BAD THEN
            FAIL := TRUE; FAIL_ST := WORD#16#0003; MORE := FALSE;
        END_IF;
    END_IF;
END_FOR;

(* sequence *)
ACC := ACC + TS;
IF ACC > 1000.0 THEN ACC := 1000.0; END_IF;
IF STATE >= 1 AND STATE <= 4 AND NOT ENABLE THEN
    STATE := 0;
    GO_CLOSE := TRUE;
END_IF;
CASE STATE OF
0:  (* closed; ACTIVATE has been FALSE for at least 1 s before the next rising edge *)
    IF ENABLE AND ACC >= 1.0 AND NOT SOCK.ACTIVE AND NOT SOCK.BUSY THEN
        SOCK_ACT := TRUE;
        ACC := 0.0; STATE := 1;
    END_IF;
1:  (* opening *)
    IF SOCK.ACTIVE THEN
        RXFILL := 0;
        RX_EN := TRUE;
        TX_WANT := 1;
        ACC := 0.0; STATE := 2;
    ELSIF ACC > 10.0 THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0002;
    END_IF;
2:  (* CONNECT out, wait CONNACK *)
    IF CONNACK_OK THEN
        TX_WANT := 2;
        ACC := 0.0; STATE := 3;
    ELSIF ACC > 10.0 THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0002;
    END_IF;
3:  (* SUBSCRIBE out, wait SUBACK *)
    IF SUBACK_OK THEN
        PING_ACC := 0.0;
        IDLE_ACC := 0.0;
        ACC := 0.0; STATE := 4;
    ELSIF ACC > 10.0 THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0002;
    END_IF;
4:  (* connected *)
    PING_ACC := PING_ACC + TS;
    IDLE_ACC := IDLE_ACC + TS;
    IF PING_ACC >= 30.0 THEN
        PING_ACC := 0.0;
        TX_WANT := 3;
    END_IF;
    IF IDLE_ACC > 90.0 THEN
        FAIL := TRUE; FAIL_ST := WORD#16#0002;
    END_IF;
9:  (* after an error: closed, wait 5 s; state 0 opens again *)
    IF ACC >= 5.0 THEN
        STATE := 0;
    END_IF;
END_CASE;
IF FAIL AND STATE >= 1 AND STATE <= 4 THEN
    ERR_STATUS := FAIL_ST;
    RECONNECTS := RECONNECTS + 1;
    STATE := 9;
    GO_CLOSE := TRUE;
END_IF;
IF GO_CLOSE THEN
    SOCK_ACT := FALSE;
    RX_EN := FALSE;
    TX_REQ := FALSE;
    TX_WANT := 0;
    RXFILL := 0;
    ACC := 0.0;
END_IF;
CONNECTED := (STATE = 4);

(* build and start a waiting packet once SND is free; REQ needs a rising edge, so it must have been FALSE last call *)
IF TX_WANT <> 0 AND NOT TX_REQ AND NOT TX_LAST AND NOT SND.BUSY THEN
    S_N := 0;
    IF TX_WANT = 1 THEN
        S_WORK := CLIENT_ID; S_MAX := 23; S_POS := 14;
    ELSIF TX_WANT = 2 THEN
        S_WORK := TOPIC; S_MAX := 120; S_POS := 6;
    ELSE
        S_WORK := ''; S_MAX := 0; S_POS := 0;
    END_IF;
    (* ---- the one place where STRING characters become bytes ----
       ASCII_TAB holds the characters 40..126 in order, the backslash replaced by an opening bracket (a literal
       must not hold a backslash, and the dollar sign starts an escape), so the position of a character in it + 39
       is its code. Characters not in the table (32..39: space, quotes, hash, dollar, percent, ampersand; and the
       backslash) come out wrong: FIND gives 0, which becomes byte 39. *)
    ASCII_TAB := '()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[(]^_`abcdefghijklmnopqrstuvwxyz{|}~';
    S_LEN := LEN(S_WORK);
    IF S_LEN > S_MAX THEN S_LEN := S_MAX; END_IF;
    FOR I := 1 TO S_LEN DO
        CB := TO_BYTE(FIND(ASCII_TAB, MID(S_WORK, 1, I)) + 39);     (* <<< CONVERSION LINE: character I of S_WORK -> BYTE *)
        IF CB > BYTE#31 THEN
            TXBUF[S_POS + S_N] := CB;
            S_N := S_N + 1;
        END_IF;
    END_FOR;
    (* ---- end of the conversion ---- *)
    CASE TX_WANT OF
    1:  (* CONNECT: protocol name MQTT, level 4, clean session, keep alive 60 s, client id *)
        TXBUF[0] := BYTE#16#10;
        TXBUF[1] := TO_BYTE(12 + S_N);
        TXBUF[2] := BYTE#0;
        TXBUF[3] := BYTE#4;
        TXBUF[4] := BYTE#16#4D;                    (* M *)
        TXBUF[5] := BYTE#16#51;                    (* Q *)
        TXBUF[6] := BYTE#16#54;                    (* T *)
        TXBUF[7] := BYTE#16#54;                    (* T *)
        TXBUF[8] := BYTE#4;
        TXBUF[9] := BYTE#16#02;
        TXBUF[10] := BYTE#0;
        TXBUF[11] := BYTE#60;
        TXBUF[12] := BYTE#0;
        TXBUF[13] := TO_BYTE(S_N);
        TX_LEN := 14 + S_N;
    2:  (* SUBSCRIBE: packet id 1, topic filter, QoS 0 *)
        TXBUF[0] := BYTE#16#82;
        TXBUF[1] := TO_BYTE(5 + S_N);
        TXBUF[2] := BYTE#0;
        TXBUF[3] := BYTE#1;
        TXBUF[4] := BYTE#0;
        TXBUF[5] := TO_BYTE(S_N);
        TXBUF[6 + S_N] := BYTE#0;
        TX_LEN := 7 + S_N;
    3:  (* PINGREQ *)
        TXBUF[0] := BYTE#16#C0;
        TXBUF[1] := BYTE#0;
        TX_LEN := 2;
    END_CASE;
    TX_REQ := TRUE;
    TX_WANT := 0;
END_IF;
