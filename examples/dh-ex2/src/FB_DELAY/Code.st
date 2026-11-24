(* On-delay: Q follows X after X has been TRUE for DELAY seconds, drops at once. *)
IF X THEN
    IF rAcc < DELAY THEN
        rAcc := rAcc + TS;
    END_IF;
ELSE
    rAcc := 0.0;
END_IF;
Q := X AND (rAcc >= DELAY);
