# profinet-pair: two controllers exchange 16 bytes each way over Profinet

Controller A (192.168.1.10) is the Profinet controller, controller B (192.168.1.11) a Profinet device with the
station name `plc-b`. B reads three registers of a Modbus TCP server at 192.168.1.50 (temperature x 10,
humidity x 10, battery mV) and sends them to A with its own counter and a status bit. A sends its counter and a
set value to B; B sends A's counter back. On A, `B_ALIVE` is TRUE while B's counter moves, and `B_ECHO` follows
`A_CNT`. Byte layout: in the comment at the top of both `Code.st`, and in `../../reference/profinet.md`.

This pair was built only, not opened in Engineer nor run. The same pattern ran on two AXC F 2152 (firmware
2026.0.2, 2026-11-24): 16 bytes each way, three Modbus TCP values of B, B's counter and a status bit at A, A's
counter and a temperature at B, A's counter back at A as an echo, within a second of the start. `a/` cannot be
built until its base project exists (step 1).

How it works, names, addresses, checks: `../../reference/profinet.md`.

- `b/`: the device. No Profinet hardware in its project: the program uses the system variables
  `PND_S1_INPUTS`, `PND_S1_OUTPUTS` (`PND_IO_512`) and `PND_S1_VALID_DATA_CYCLE`, declared `VAR_EXTERNAL`. Base
  `AXCF2152-2026.0-MBTCP` (a Modbus TCP client with one server, `../../reference/modbus-tcp.md`). Operator page
  `hmi.py`: the three values, a lamp for the Modbus server, a lamp for the Profinet exchange, A's data.
- `a/`: the controller. Two ports of type `PND_IO_512` linked to the items `DI4096` / `DQ4096` of the device's
  module "IO 512". Base `AXCF2152-2026.0-PNB`, made by hand (step 1). No page: `pxe.sh read`.

## Steps, in this order

1. **Base project for A** (once, by hand): `profinet.md`, "Controller side". In short: a project from A's plain
   base; PLANT > Profinet > Device List > "Select type here" > "AXC F 2152", the newest "AXC F 2152 Rev. >=
   2/V21.0.0" (module "IO 512" comes with it); in the device's Settings IP address 192.168.1.11 (octet by
   octet) and Name of station `plc-b`; on "interface-1 : Interface" Reduction ratio 32 (the default gives warning
   PNIO0112). Ctrl+S, then
   `python3 scripts/pxproj.py --strip <saved> ~/.plcnext-engineer/base/AXCF2152-2026.0-PNB.plcnx2`.
2. **Modbus TCP on B**: B's web interface > System Services > "Modbus Client TCP" on, once per controller. Put
   your server's address and registers into `b/program.json` (`modbus_tcp`). Without a server the Profinet part
   should work all the same, with `M.MB_STATE` and status bit 0 at 0 (untested).
3. **Write B**: `pxe.sh build examples/profinet-pair/b`, `open`, `write` with B as the target (the project's
   target is 192.168.1.11; `read` and `state` need `PLC_HOST=192.168.1.11` in front of `pxe.sh`).
4. **Write A**: `pxe.sh build examples/profinet-pair/a`, `open` (a warning PNIO0112 means step 1's
   reduction ratio is missing), `write`. A's BF-C lamp is red: B has no name on the network yet.
5. **Name B on the network** (once per device, by hand, with A's project open and connected): PLANT > Profinet >
   Online Devices, choose the Engineer machine's network adapter on the controllers' network in the drop-down,
   press the scan button. In the row of `plc-b` click "Name of station (Online)" and pick the scanned device by
   its MAC address. A green tick: the name is set. `target.station` in `b/program.json` does not do this: it
   only names B in its own project (both controllers answered the scan as `axcf2152-lan1` before this step).
6. **Look**: within seconds the values move. On A: `pxe.sh read M.B_TEMP M.B_BEAT M.B_ALIVE M.B_ECHO M.A_CNT`:
   `B_ALIVE` TRUE, `B_ECHO` follows `A_CNT`. On B:
   `PLC_HOST=192.168.1.11 pxe.sh read M.PN_VALID M.FROM_A_CNT M.FROM_A_SP`: `PN_VALID` TRUE, `FROM_A_SP` 21.5.

A sets B's address from its project when the exchange starts. Keep the address in step 1 equal to B's own
(192.168.1.11 here), or B can become unreachable at its old address.
