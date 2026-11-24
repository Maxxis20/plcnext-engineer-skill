# MQTT in: subscribing from a PLCnext program

Proven 2026-11-23 on an AXC F 2152 (firmware 2026.0.2) with PLCnext Engineer 2026.6: a program connected to the
broker of a LoRaWAN network server and subscribed at the first start; a ChirpStack uplink of 695 bytes arrived
and gave the same three values as the same device read over Modbus TCP. Then **proven** over 8 hours overnight:
49 uplinks of about 700 bytes received, no reconnect, the values equal to the same device's Modbus TCP registers
every time. Example: `examples/mqtt-subscribe` (blocks as they ran, its MAIN only built).

The firmware's own MQTT client only publishes (`findings.md`, "MQTT from the controller"; SKILL.md, "Values out
over MQTT"). To receive, a small MQTT 3.1.1 client in Structured Text runs in the program.

## What it takes

- A broker the controller reaches over plain TCP (1883) that takes clients without login.
- The socket blocks `TCP_SOCKET`, `TCP_SEND`, `TCP_RECEIVE` of the "PLCnext Controller" library, which every
  project references already. No library to buy, no app, no licence.
- The two blocks of the example: `FB_MQTT_SUB` (the client) and `FB_JSON_NUM` (one number from a JSON text).
  Copy their folders from `examples/mqtt-subscribe/src/` and list them in `pous` before the program.

## The two blocks

**`FB_MQTT_SUB`**: plain TCP, no login, no TLS, one topic filter, QoS 0, clean session, keep alive 60 s with a
ping every 30 s. On any error it closes and opens again after 5 s. Packets may arrive in pieces; the block
collects them (4 kB buffer, up to 1 kB per call) and takes whole MQTT packets from the front, at most one
message per cycle.

| | Name | Type | Meaning |
|---|---|---|---|
| in | `ENABLE` | BOOL | TRUE: connect and stay connected; FALSE: close |
| in | `BROKER_IP` | STRING | address, e.g. `'192.168.1.50'` |
| in | `BROKER_PORT` | UINT | 1883 by default |
| in | `CLIENT_ID` | STRING | unique on the broker; at most 23 characters are sent |
| in | `TOPIC` | STRING[120] | one topic filter |
| in | `TS` | REAL | cycle time of the calling task in s (0.1 by default); all timeouts count with it |
| out | `CONNECTED` | BOOL | CONNACK accepted and SUBACK received |
| out | `NEW_MSG` | BOOL | TRUE for one cycle: a whole message payload is in `PAYLOAD` |
| out | `PAYLOAD` | ARRAY[0..2047] OF BYTE | the payload; a longer one is cut at 2048 bytes |
| out | `PAYLOAD_LEN` | INT | bytes in `PAYLOAD` |
| out | `MSG_CNT`, `RECONNECTS` | UDINT | messages received, connections lost |
| out | `STATE` | INT | see below |
| out | `ERR_STATUS` | WORD | the reason of the last error, see below |

`STATE`: 0 closed (opens 1 s after the close when `ENABLE` is TRUE); 1 opening the socket; 2 CONNECT sent,
waiting for CONNACK; 3 SUBSCRIBE sent, waiting for SUBACK; 4 connected; 9 closed after an error, waiting 5 s.

`ERR_STATUS`: the `STATUS` of the socket block that failed (also when the broker closed the connection), or the
block's own codes: `16#0001` receive buffer full; `16#0002` timeout (socket not open, no CONNACK or no SUBACK
within 10 s, or nothing from the broker for 90 s); `16#0003` a bad or refused packet (CONNACK with a return code
other than 0, SUBACK with 16#80, a packet too long for the buffer). The socket codes were not looked up.

The socket blocks as the code uses them (read `Code.st` for the details):
`TCP_SOCKET(ACTIVATE, IS_SRV := FALSE, BIND_PORT := 0, DEST_IP, DEST_PORT)` -> `HANDLE`, `ACTIVE`, `BUSY`,
`ERROR`, `STATUS`; `TCP_SEND(REQ, HANDLE, DATA_CNT, DATA)` -> `DONE`, `BUSY`, `ERROR`, `STATUS`, sends on a
rising edge of `REQ`; `TCP_RECEIVE(EN_R, HANDLE, EXP_DATA_CNT := 0, DATA)` -> `NDR`, `DATA_CNT`, `ERROR`,
`STATUS`, with 0 it delivers what has arrived since the last call. `ERROR` is TRUE for one cycle; `STATUS` is
valid in that cycle.

**`FB_JSON_NUM`**: finds `"KEY":` in the payload (spaces allowed around the colon) and reads the number after it:
an optional minus sign, digits, an optional fraction. No exponent; a quoted value, `true`, `null` give nothing.
The **first** match anywhere in the text counts, nested or not.

| | Name | Type | Meaning |
|---|---|---|---|
| in | `BUF_LEN` | INT | bytes in `BUF` |
| in | `KEY` | STRING | e.g. `'temperature'`, at most 60 characters |
| in out | `BUF` | ARRAY[0..2047] OF BYTE | the JSON text; in out so the 2 kB are not copied on every call |
| out | `FOUND` | BOOL | the key was found and a number follows it |
| out | `VALUE` | REAL | keeps its last value while `FOUND` is FALSE |

**Characters.** No direct character-to-byte conversion was found in the tool's Structured Text. Both blocks look
each character up with `FIND` in a table string of the characters 40..126 (backslash replaced): position + 39 is
its code. Characters 32..39 (space, `!`, `"`, `#`, `$`, `%`, `&`, `'`) and the backslash are not in the table
and come out wrong. So a topic, client id or key must not contain them: `+` (43) works, `#` (35) does not.

## Calling them

```
VAR
    TS : REAL := 0.1;
    MQ : FB_MQTT_SUB;
    JT : FB_JSON_NUM;
    TEMP : REAL { EHMI, OPC };
END_VAR
```

```
MQ(ENABLE := TRUE, BROKER_IP := '192.168.1.50', BROKER_PORT := 1883, CLIENT_ID := 'plc-sub-1',
   TOPIC := 'application/1/device/0000000000000000/event/up', TS := TS);
IF MQ.NEW_MSG THEN
    JT(BUF := MQ.PAYLOAD, BUF_LEN := MQ.PAYLOAD_LEN, KEY := 'temperature');
    IF JT.FOUND THEN
        TEMP := JT.VALUE;
    END_IF;
END_IF;
```

- Call `MQ` every cycle, unconditionally: the socket blocks only move when they are called.
- Read the payload only in the cycle of `NEW_MSG`. The output array of `MQ` goes straight into the in out of
  `JT` (**proven**, no copy).
- One `FB_JSON_NUM` instance per key (the key is turned into bytes again only when it changes).
- Keep an age counter (`AGE := AGE + TS / 60.0`, 0 on each good message) to mark values as stale.
- `TS` must be the task's cycle time, or the timeouts and the ping run wrong.

## ChirpStack example

A ChirpStack network server publishes each uplink of a device as JSON on
`application/<application id>/device/<devEUI>/event/up`. The decoded values (when the device profile has a
decoder) stand under `object`, e.g. `"object":{"humidity":27,"temperature":22.9,"vdd":3673}`, and the frame
counter as `fCnt`. `FB_JSON_NUM` with the keys `temperature`, `humidity`, `vdd`, `fCnt` read them from a 695
byte message (**proven**). Uplinks are not retained: after a restart of the program there is no value until the
device sends again.

## Limits, not tried

TLS (`TLS_SOCKET_2` and its relatives exist in the library); user name and password in CONNECT; QoS 1;
publishing; wildcards in the topic (`+` is in the character table, `#` is not); payloads over 2 kB; several
topics; a broker that drops the link (the reconnect path was not exercised); CPU load
of the blocks.
