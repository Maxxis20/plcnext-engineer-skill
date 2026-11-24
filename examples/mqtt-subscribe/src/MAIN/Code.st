(* Uplinks of one device from a ChirpStack network server: JSON, decoded values under "object" *)
MQ(ENABLE := TRUE, BROKER_IP := '192.168.1.50', BROKER_PORT := 1883, CLIENT_ID := 'plc-sub-1',
   TOPIC := 'application/1/device/0000000000000000/event/up', TS := TS);
MQ_CONNECTED := MQ.CONNECTED;
MQ_STATE := MQ.STATE;
MQ_ERR := MQ.ERR_STATUS;
MQ_MSGS := MQ.MSG_CNT;
MQ_RECONN := MQ.RECONNECTS;
AGE := AGE + TS / 60.0;
IF MQ.NEW_MSG THEN
    MQ_LEN := MQ.PAYLOAD_LEN;
    JT(BUF := MQ.PAYLOAD, BUF_LEN := MQ.PAYLOAD_LEN, KEY := 'temperature');
    JH(BUF := MQ.PAYLOAD, BUF_LEN := MQ.PAYLOAD_LEN, KEY := 'humidity');
    JF(BUF := MQ.PAYLOAD, BUF_LEN := MQ.PAYLOAD_LEN, KEY := 'fCnt');
    IF JT.FOUND AND JH.FOUND THEN
        TEMP := JT.VALUE;
        HUM := JH.VALUE;
        VALID := TRUE;
        AGE := 0.0;
    END_IF;
    IF JF.FOUND THEN
        FCNT := JF.VALUE;
    END_IF;
END_IF;
