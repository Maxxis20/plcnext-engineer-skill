# Modbus TCP from a PLCnext controller

Proven 2026-11-23 on an AXC F 2152 (firmware 2026.0.2) with PLCnext Engineer 2026.6: the controller's own Modbus
TCP client reads input registers of one server over Ethernet, floats and scaled integers, and the program sees
the connection state. No programming of the protocol: the client is configured in the project and the program
gets one port per register. Example: `examples/modbus-tcp-read`.

## What it takes

- No extra hardware: the controller's Ethernet interface. The server must be reachable from the controller (same
  network, or a route the controller's Linux knows).
- Engineer's library **Modbus.pcwlx** (in the tool's `Libraries` folder, it ships with the tool). Firmware 2024.6
  or newer for the client and remote servers (help text). The controller as Modbus TCP server (a local server)
  needs 2026.0 (help text, untested).
- The service on the controller: WBM > System Services > **"Modbus Client TCP"** must be on. The same switch as
  a file: `findings.md`, "Modbus TCP client".
- The server: its address, port (502), unit id, the register list with function (3 holding, 4 input) and
  addresses as on the wire (0-based), and the word order of 32-bit values.

## Steps

1. **Base project with the client and one server** (once, by hand, kept as a base project):
   - COMPONENTS > Libraries > right click the inner "Libraries" node > "Add Library..." > `Modbus.pcwlx`.
   - Type "Modbus" in the COMPONENTS search. Drag **"Modbus TCP Client 8"** onto the controller in PLANT: the
     node "Modbus TCP Client-1" appears. 8 / 16 / 32 is the number of servers it takes (guess, not checked).
   - Click **"Generic Modbus TCP Server Rev. >= xx"** to select it, then drag it onto the client node. The drag
     takes the selected row, not the one under the mouse: without selecting first, the "Gateway" variant above it
     landed, twice. A wrong one goes with the Delete key.
   - Ctrl+S, then `pxproj.py --strip <saved> ~/.plcnext-engineer/base/<NAME>.plcnx2`.
   - The generator handles **one server per base project**.
2. **Switch the service on** on the controller (WBM, above), once per controller.
3. **Describe the server and its registers** in `program.json` (next section). Build, open, write as usual.
4. **Check**: `pxe.sh read M.MB_STATE M.<register>`: `MB_STATE` 1 and live numbers. `MB_STATE` 0: service off,
   address, port, or no route. Numbers but nonsense: function, register base or word order (below).

## The program side

`program.json`:

```json
"modbus_tcp": {"ip": "192.168.1.50", "unit": 1, "port": 502, "registers": [
  {"name": "VALUE_HI", "fc": 4, "address": 0}, {"name": "VALUE_LO", "fc": 4, "address": 1},
  {"name": "VALUE10", "fc": 4, "address": 100}]},
"io": {"M.VALUE_HI": "VALUE_HI_input", "M.VALUE_LO": "VALUE_LO_input", "M.VALUE10": "VALUE10_input",
       "M.MB_STATE": "STATE"}
```

- `ip`, `unit`, `port` go into the server's settings; the registers replace the ones the base came with.
- Every register is one WORD (16 bit). Its process data item is named `<name>_input`; `io` links a program
  port to it.
- Only function 3 and 4 (read registers) are built. `target.ip` also sets the controller's own address in the
  project.

In the program, a plain `VAR` block (the generator moves ports where the tool wants them):

```
VAR
    VALUE_HI : WORD { InputPort, EHMI };
    VALUE_LO : WORD { InputPort, EHMI };
    VALUE10 : WORD { InputPort, EHMI };
    MB_STATE : UDINT { InputPort, EHMI };
    VALUE : REAL { EHMI };
    VALUE_S : REAL { EHMI };
    fbV : FB_IEEE;
END_VAR
```

```
fbV(D := SHL(TO_DWORD(VALUE_HI), 16) OR TO_DWORD(VALUE_LO));
VALUE := fbV.V;
VALUE_S := TO_REAL(TO_INT(VALUE10)) / 10.0;
```

- **32-bit float** = two registers = two WORD ports, joined into a DWORD and decoded by `FB_IEEE` (from the
  examples; no bit cast was found). The word order is the device's: if the number is nonsense, swap HI and LO.
- **Scaled integer** (value x 10): `TO_INT` first for a signed value, then the factor.
- The client runs on its own, not in the program's task. Its "Trigger rate" (server settings, 500 ms in the
  base) is presumably how often it asks (untested).

## Status items of a server

Per server the client offers these items besides the registers, all 32 bit unsigned (UDINT port): `STATE`,
`IP_ADDRESS`, `UNIT_ID`, `OFFLINE_CNT`, `EXCEPTION_CNT`, `EXCEPTION_CODE`, `EXCEPTION_FC`, `EXCEPTION_REG_ADDR`,
`AVG_NET_CYCLE_TIME`, `MIN_NET_CYCLE_TIME`, `MAX_NET_CYCLE_TIME`, `ACTUAL_NET_CYCLE_TIME`, `ADDITIONAL_ERR`,
`CONTROL_DIAG_STATISTIC`. Link them in `io` by these names.

- `STATE` is 1 while the server is connected and answers (**seen**). Use it for a lamp and to mark the values
  as stale.
- `STATE`, `OFFLINE_CNT` and `EXCEPTION_CNT` are **proven** as UDINT ports. What the counters count and what
  the other items mean is read from their names, not checked.

## In the tool (for reading a project, not needed for building)

The server node has the editors Settings (IP address, port 502, unit id, swap bytes, connection timeout 5000 ms,
reconnection interval, response timeout, trigger rate), Registers, Data List and GDS Port List. A register row:
function code (FC1, 2, 3, 4, 15, 16, 23 offered; FC5 / 6 in the help), name, address (decimal, as on the wire),
quantity. The data type is WORD only. Quantity 1 gives a 16-bit item (a WORD port); quantity 4 gave an 8-byte
octet string item (not used; one register per row is simpler in the program).

## Compiler warning TCPP0007

"The IP address ... of device [generic-server-1 ...] lies below the network's start address" comes when the
server is in another subnet than the project's IP range. Harmless: the read works (**proven**, server reached
through the controller's second Ethernet interface, routed by the controller's Linux).

## Limits

**32 registers per server** (seen: 65 registers gave "Modbus error by the register 'T14'. The Modbus server has too
many function codes (32)" when the project was opened). Example at the limit: `examples/spot-price`.

Not tried:

Writing registers (FC6 / 16 offered by the tool, not built by the generator); coils and discrete inputs (FC1 /
2); more than one server in a project; several registers in one row (quantity > 1); swap bytes; the controller
as Modbus TCP server; Modbus RTU through a gateway (the "Gateway" server variant).
