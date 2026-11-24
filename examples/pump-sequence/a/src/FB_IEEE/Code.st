(* IEEE 754 single precision bit pattern -> REAL, without a bit cast *)
E := TO_INT(SHR(D, 23) AND DWORD#16#FF);
M := D AND DWORD#16#7FFFFF;
IF E = 0 OR E = 255 THEN
    V := 0.0;
ELSE
    V := 1.0 + TO_REAL(TO_DINT(M)) / 8388608.0;
    E := E - 127;
    IF E > 0 THEN
        FOR I := 1 TO E DO
            V := V * 2.0;
        END_FOR;
    ELSIF E < 0 THEN
        FOR I := 1 TO -E DO
            V := V / 2.0;
        END_FOR;
    END_IF;
    IF (D AND DWORD#16#80000000) <> DWORD#0 THEN
        V := -V;
    END_IF;
END_IF;
