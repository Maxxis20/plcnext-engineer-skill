(* Modbus TCP: the firmware's client fills the WORD ports every cycle of its own *)
fbV(D := SHL(TO_DWORD(VALUE_HI), 16) OR TO_DWORD(VALUE_LO));
VALUE := fbV.V;
VALUE_S := TO_REAL(TO_INT(VALUE10)) / 10.0;
