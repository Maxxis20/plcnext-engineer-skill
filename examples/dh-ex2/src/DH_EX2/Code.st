(* DH-ex2: district heating substation, heating and domestic hot water.
   After example connection 2 of Finnish Energy publication K1/2013. See DESCRIPTION.md.
   Order: plant model (SIM only), OUTDOOR, TC1_DHW, TC2_HEAT, ALARM. *)

(* 0 Plant model: gives the three temperatures and the pump faults while SIM is TRUE.
   It reads the outputs of the previous cycle. *)
IF SIM THEN
    fbPlant(TV1_CMD := TV1_OUT, TV2_CMD := TV2_OUT, P1_CMD := P1_OUT, P2_CMD := P2_OUT,
            TOUT := TOUT, DHW_TAP := DHW_TAP, P1_TRIP := P1_TRIP, P2_TRIP := P2_TRIP, TS := TS);
    TE2B_IN := fbPlant.TE2B;
    TE1_IN := fbPlant.TE1;
    TE2A_IN := fbPlant.TE2A;
    P1_FLT_IN := P1_TRIP;
    P2_FLT_IN := P2_TRIP;
    TV1_POS := fbPlant.TV1_POS;
    TV2_POS := fbPlant.TV2_POS;
    P1_ON := fbPlant.P1_ON;
    P2_ON := fbPlant.P2_ON;
END_IF;

(* 1 OUTDOOR *)
fbOutdoor(TE2B_IN := TE2B_IN, TOUT_FALLBACK := TOUT_FALLBACK, TOUT_FILT_T := TOUT_FILT_T, TS := TS);
TE2B := fbOutdoor.TE2B;
TE2B_F := fbOutdoor.TE2B_F;
TE2B_FAULT := fbOutdoor.TE2B_FAULT;

(* 2 TC1_DHW *)
fbTC1(TE1_IN := TE1_IN, P1_FLT_IN := P1_FLT_IN, DHW_ENABLE := DHW_ENABLE, DHW_SP := DHW_SP,
      DHW_PID_P := DHW_PID_P, DHW_PID_I := DHW_PID_I, DHW_HI_LIM := DHW_HI_LIM, DHW_LO_LIM := DHW_LO_LIM,
      DHW_ALM_DLY := DHW_ALM_DLY, TS := TS);
TE1 := fbTC1.TE1;
TE1_FAULT := fbTC1.TE1_FAULT;
P1_RUN := fbTC1.P1_RUN;
P1_FAULT := fbTC1.P1_FAULT;
P1_ST := fbTC1.P1_ST;
TV1 := fbTC1.TV1;
DHW_TEMP_ALM := fbTC1.DHW_TEMP_ALM;

(* 3 TC2_HEAT *)
fbTC2(TE2A_IN := TE2A_IN, TE2B_F := TE2B_F, P2_FLT_IN := P2_FLT_IN, HEAT_ENABLE := HEAT_ENABLE,
      SUM_START := SUM_START, SUM_STOP := SUM_STOP, SUM_DLY := SUM_DLY,
      CRV_N20 := CRV_N20, CRV_0 := CRV_0, CRV_P20 := CRV_P20, TS_MIN := TS_MIN, TS_MAX := TS_MAX,
      HEAT_PID_P := HEAT_PID_P, HEAT_PID_I := HEAT_PID_I, HEAT_HI_LIM := HEAT_HI_LIM, HEAT_LO_LIM := HEAT_LO_LIM,
      HEAT_ALM_DLY := HEAT_ALM_DLY, TS := TS);
TE2A := fbTC2.TE2A;
TE2A_FAULT := fbTC2.TE2A_FAULT;
SUMMER := fbTC2.SUMMER;
HEAT_SP := fbTC2.HEAT_SP;
P2_RUN := fbTC2.P2_RUN;
P2_FAULT := fbTC2.P2_FAULT;
P2_ST := fbTC2.P2_ST;
TV2 := fbTC2.TV2;
HEAT_TEMP_ALM := fbTC2.HEAT_TEMP_ALM;

(* 4 ALARM: common alarm, no latching, no acknowledgement *)
ALARM_SUM := TE2B_FAULT OR TE1_FAULT OR DHW_TEMP_ALM OR TE2A_FAULT OR HEAT_TEMP_ALM OR P1_FAULT OR P2_FAULT;

(* outputs *)
TV1_OUT := TV1;
TV2_OUT := TV2;
P1_OUT := P1_RUN;
P2_OUT := P2_RUN;
ALARM_OUT := ALARM_SUM;

(* for displays *)
TV1_OPEN := TV1 > 1.0;
TV2_OPEN := TV2 > 1.0;
