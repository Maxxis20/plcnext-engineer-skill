(* One number from a JSON text: finds the first "KEY" followed by a colon (spaces allowed around it), then reads
   an optional minus sign, digits and an optional fraction; stops at anything else. No exponent. *)
FOUND := FALSE;

(* the search key as bytes, rebuilt only when KEY changes *)
IF NOT KEY_BUILT OR KEY <> KEY_LAST THEN
    KEY_LAST := KEY;
    KEY_BUILT := TRUE;
    KB[0] := BYTE#16#22;                            (* " *)
    KLEN := 1;
    N := LEN(KEY);
    IF N > 60 THEN N := 60; END_IF;
    (* ---- the one place where STRING characters become bytes (same as in FB_MQTT_SUB) ---- *)
    ASCII_TAB := '()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[(]^_`abcdefghijklmnopqrstuvwxyz{|}~';
    FOR I := 1 TO N DO
        CB := TO_BYTE(FIND(ASCII_TAB, MID(KEY, 1, I)) + 39);     (* <<< CONVERSION LINE: character I of KEY -> BYTE *)
        IF CB > BYTE#31 THEN
            KB[KLEN] := CB;
            KLEN := KLEN + 1;
        END_IF;
    END_FOR;
    (* ---- end of the conversion ---- *)
    KB[KLEN] := BYTE#16#22;
    KLEN := KLEN + 1;
END_IF;

N := BUF_LEN;
IF N > 2048 THEN N := 2048; END_IF;
IF N < 0 THEN N := 0; END_IF;

S := 0;
HIT := FALSE;
WHILE NOT HIT AND S + KLEN <= N DO
    MATCH := TRUE;
    J := 0;
    WHILE MATCH AND J < KLEN DO
        IF BUF[S + J] <> KB[J] THEN
            MATCH := FALSE;
        END_IF;
        J := J + 1;
    END_WHILE;
    IF MATCH THEN
        P := S + KLEN;
        (* spaces, then the colon; without a colon it was a value, not a key: search on *)
        GOING := TRUE;
        WHILE GOING DO
            IF P >= N THEN
                GOING := FALSE;
            ELSIF BUF[P] = BYTE#16#20 OR BUF[P] = BYTE#16#09 OR BUF[P] = BYTE#16#0A OR BUF[P] = BYTE#16#0D THEN
                P := P + 1;
            ELSE
                GOING := FALSE;
            END_IF;
        END_WHILE;
        IF P < N THEN
            IF BUF[P] = BYTE#16#3A THEN             (* : *)
                HIT := TRUE;
                P := P + 1;
            END_IF;
        END_IF;
    END_IF;
    IF NOT HIT THEN
        S := S + 1;
    END_IF;
END_WHILE;

IF HIT THEN
    GOING := TRUE;
    WHILE GOING DO
        IF P >= N THEN
            GOING := FALSE;
        ELSIF BUF[P] = BYTE#16#20 OR BUF[P] = BYTE#16#09 OR BUF[P] = BYTE#16#0A OR BUF[P] = BYTE#16#0D THEN
            P := P + 1;
        ELSE
            GOING := FALSE;
        END_IF;
    END_WHILE;
    IS_NEG := FALSE;
    IF P < N THEN
        IF BUF[P] = BYTE#16#2D THEN                 (* - *)
            IS_NEG := TRUE;
            P := P + 1;
        END_IF;
    END_IF;
    V := 0.0;
    SCALE := 1.0;
    FRAC := FALSE;
    DIGITS := 0;
    GOING := TRUE;
    WHILE GOING DO
        IF P >= N THEN
            GOING := FALSE;
        ELSE
            C := TO_INT(BUF[P]);
            IF C >= 48 AND C <= 57 THEN             (* 0..9 *)
                IF FRAC THEN
                    SCALE := SCALE * 0.1;
                    V := V + TO_REAL(C - 48) * SCALE;
                ELSE
                    V := V * 10.0 + TO_REAL(C - 48);
                END_IF;
                DIGITS := DIGITS + 1;
                P := P + 1;
            ELSIF C = 46 AND NOT FRAC THEN          (* . *)
                FRAC := TRUE;
                P := P + 1;
            ELSE
                GOING := FALSE;
            END_IF;
        END_IF;
    END_WHILE;
    IF DIGITS > 0 THEN
        FOUND := TRUE;
        IF IS_NEG THEN
            VALUE := -V;
        ELSE
            VALUE := V;
        END_IF;
    END_IF;
END_IF;
