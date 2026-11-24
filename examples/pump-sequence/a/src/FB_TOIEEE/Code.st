(* REAL -> IEEE 754 single precision bit pattern, without a bit cast *)
IF V = 0.0 THEN
    D := DWORD#0;
ELSE
    A := ABS(V);
    E := 127;
    WHILE A >= 2.0 DO
        A := A / 2.0; E := E + 1;
    END_WHILE;
    WHILE A < 1.0 DO
        A := A * 2.0; E := E - 1;
    END_WHILE;
    D := SHL(TO_DWORD(E), 23) OR (TO_DWORD(TO_DINT((A - 1.0) * 8388608.0)) AND DWORD#16#7FFFFF);
    IF V < 0.0 THEN
        D := D OR DWORD#16#80000000;
    END_IF;
END_IF;
