# modbus-tcp-read: values from a Modbus TCP server

AXC F 2152 (firmware 2026.0) reads three input registers of a server at 192.168.1.50 with the firmware's own
Modbus TCP client: a float in registers 0-1 (high word first) and a value x 10 in register 100. The page shows
both values, the raw registers, a lamp for the connection (`STATE`) and the client's counters for lost
connections and exceptions.

This example was built only, not yet opened and compiled in Engineer nor run. The same pattern (`modbus_tcp`
registers, WORD ports, `FB_IEEE`, status items) ran on a controller against a real server.

How it works and what the base project must hold: `../../reference/modbus-tcp.md`. `program.json` names the base
project (one that holds a Modbus TCP Client with one Generic Modbus TCP Server), describes the server and its
registers under `modbus_tcp`, and links the program's ports to the register items and the status items. Change
`ip`, `unit` and the register list for your device; swap `VALUE_HI` and `VALUE_LO` if the float is nonsense.
