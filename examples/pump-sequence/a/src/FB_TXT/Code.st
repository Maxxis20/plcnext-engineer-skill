(* Text into bytes, appended to BUF, one call per piece.
   CMD 1 (template): every character, with stand-ins for what a literal cannot hold or the table lacks:
         ` double quote   @ single quote   ^ CR LF   | LF   (~ is a space too)
   CMD 5 (raw): the characters as they are (names, user, key).
   Both: spaces come out right; the other characters below 40 (! # $ % & and the quotes) come out as spaces.
   CMD 2: R as text with 3 decimals (|R| < 2000000).  CMD 3: D as a whole number.  CMD 6: bytes A[0..AN-1].  CMD 0: empty BUF.
   Turning characters into bytes costs a FIND each: for text sent often, turn it into bytes once and use CMD 6. *)
ASCII_TAB := '()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[(]^_`abcdefghijklmnopqrstuvwxyz{|}~';
IF CMD = 0 THEN
    NB := 0;
    OVER := FALSE;
ELSIF CMD = 1 OR CMD = 5 THEN
    N := LEN(S);
    FOR I := 1 TO N DO
        C := FIND(ASCII_TAB, MID(S, 1, I)) + 39;
        IF C = 39 THEN
            C := 32;                        (* not in the table: almost always a space; also ! # $ % & come out as spaces *)
        END_IF;
        IF CMD = 1 THEN
            IF C = 126 THEN C := 32;
            ELSIF C = 96 THEN C := 34;
            ELSIF C = 64 THEN C := 39;
            ELSIF C = 124 THEN C := 10;
            END_IF;
        END_IF;
        IF CMD = 1 AND C = 94 THEN
            IF NB < 12286 THEN
                BUF[NB] := BYTE#13;
                BUF[NB + 1] := BYTE#10;
                NB := NB + 2;
            ELSE
                OVER := TRUE;
            END_IF;
        ELSE
            IF NB < 12288 THEN
                BUF[NB] := TO_BYTE(C);
                NB := NB + 1;
            ELSE
                OVER := TRUE;
            END_IF;
        END_IF;
    END_FOR;
ELSIF CMD = 2 OR CMD = 3 THEN
    IF CMD = 2 THEN
        IS_NEG := R < 0.0;
        IF IS_NEG THEN M := TO_DINT(-R * 1000.0); ELSE M := TO_DINT(R * 1000.0); END_IF;
        IP := M / 1000;
        FR := M MOD 1000;
    ELSE
        IS_NEG := D < 0;
        IF IS_NEG THEN IP := -D; ELSE IP := D; END_IF;
        FR := 0;
    END_IF;
    (* digits of IP, last first *)
    ND := 0;
    REPEAT
        DIG[ND] := TO_BYTE(48 + TO_INT(IP MOD 10));
        IP := IP / 10;
        ND := ND + 1;
    UNTIL IP = 0 OR ND >= 11
    END_REPEAT;
    IF NB + ND + 6 > 12288 THEN
        OVER := TRUE;
    ELSE
        IF IS_NEG THEN
            BUF[NB] := BYTE#45;
            NB := NB + 1;
        END_IF;
        FOR K := ND - 1 TO 0 BY -1 DO
            BUF[NB] := DIG[K];
            NB := NB + 1;
        END_FOR;
        IF CMD = 2 THEN
            BUF[NB] := BYTE#46;
            BUF[NB + 1] := TO_BYTE(48 + TO_INT(FR / 100));
            BUF[NB + 2] := TO_BYTE(48 + TO_INT((FR / 10) MOD 10));
            BUF[NB + 3] := TO_BYTE(48 + TO_INT(FR MOD 10));
            NB := NB + 4;
        END_IF;
    END_IF;
ELSIF CMD = 6 THEN
    IF NB + AN > 12288 OR AN > 32 THEN
        OVER := TRUE;
    ELSE
        FOR K := 0 TO AN - 1 DO
            BUF[NB + K] := A[K];
        END_FOR;
        NB := NB + AN;
    END_IF;
END_IF;
