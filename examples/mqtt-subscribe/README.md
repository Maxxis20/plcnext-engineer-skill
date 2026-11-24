# mqtt-subscribe: values from an MQTT broker into the program

AXC F 2152 (firmware 2026.0) subscribes to one topic on a broker at 192.168.1.50 and takes two numbers out of each
message: the uplinks of one LoRaWAN device as a ChirpStack network server publishes them (JSON, decoded values
under `object`). `TEMP` and `HUM` are the device's `temperature` and `humidity`, `FCNT` its frame counter, `AGE`
the minutes since the last good message. The `MQ_...` variables show the connection (state, error, counters).

The firmware's own MQTT client only publishes. Receiving is done in the program: `FB_MQTT_SUB` is a small MQTT
3.1.1 client on the socket blocks of the "PLCnext Controller" library, `FB_JSON_NUM` finds one number in the
payload. No library to buy, no app.

The two blocks ran on a controller (2026-11-23, firmware 2026.0.2): connected and subscribed at the first start,
a ChirpStack uplink of 695 bytes arrived and gave the same values as the same device read over Modbus TCP; then
8 hours overnight, 49 uplinks of about 700 bytes, no reconnect, the values equal to the device's Modbus TCP
registers every time. This MAIN was only built, not opened in Engineer nor run.

Change in `src/MAIN/Code.st`: `BROKER_IP`, `TOPIC` (a ChirpStack application publishes on
`application/<application id>/device/<devEUI>/event/up`), `CLIENT_ID` (unique on the broker), and the keys. The
broker must take plain TCP on 1883 without login. Uplinks are not retained: after a restart the values stay 0
until the device sends again (`VALID` FALSE until then).

How it works and its limits: `../../reference/mqtt-subscribe.md`.
