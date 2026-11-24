# Profinet between two PLCnext controllers

Proven 2026-11-24 on two AXC F 2152 (firmware 2026.0.2) with PLCnext Engineer 2026.6: controller A is the
Profinet controller, controller B a Profinet device (station name `plc-b`). 16 of 512 bytes were used each way:
values of B's Modbus TCP server (temperature, humidity, battery), B's counter and a status bit arrived at A; A's
counter and a room temperature arrived at B, and A's counter came back to A as an echo. Values moved within a
second of the start. Example: `examples/profinet-pair` (A 192.168.1.10, B 192.168.1.11).

## What it takes

- Both controllers on one Ethernet network, in one subnet. Profinet RT runs beside the other traffic on the same
  interface: B kept reading its Modbus TCP server and serving its operator page while it exchanged data (**seen**).
- **On B (device)**: nothing in the hardware tree. The firmware's "Profinet device" function is on by default; the
  program reaches the data through system variables (below).
- **On A (controller)**: B as a device in A's Profinet tree. Made **once by hand** in Engineer and kept in a base
  project; `pxproj.py` does not generate it.
- **B's name on the network**: set once from Engineer's "Online Devices" while connected to A. Without it nothing
  is exchanged. Not done from a script (section "Names and addresses").
- No library, no function block, no licence (none was asked for).

## Device side (controller B)

The program declares the system variables it uses as `VAR_EXTERNAL`, in `Variables.var` beside its `VAR` block:

```
VAR_EXTERNAL
    PND_S1_OUTPUTS : PND_IO_512;          (* to the Profinet controller *)
    PND_S1_INPUTS : PND_IO_512;           (* from the Profinet controller *)
    PND_S1_VALID_DATA_CYCLE : BOOL;       (* TRUE while a controller exchanges data *)
END_VAR
```

- `PND_IO_512` is 512 bytes, indexed `[0]` to `[511]` like an array of BYTE: `PND_S1_OUTPUTS[0] := ...`,
  `X := PND_S1_INPUTS[0];` (**proven**). `VAR_EXTERNAL` of system variables compiles and runs as written; the
  generator passes the block through.
- `PND_S1_VALID_DATA_CYCLE` was TRUE while A exchanged data (**proven**). What it does when the link breaks:
  untested.
- Other system variables in the data list: `PND_S1_PLC_RUN`, `PND_S1_OUTPUT_STATUS_GOOD`,
  `PND_S1_INPUT_STATUS_GOOD`, `PND_S1_DATA_LENGTH`, `PND_IO_DRIVEN_BY_PLC` (**seen**, not used; meaning read
  from the names only).
- `program.json` of B: any base without extra hardware will do; the example uses the Modbus TCP base to show both
  at once. `"target": {"ip": "192.168.1.11", "station": "plc-b"}` (station: section "Names and addresses").

## Controller side (controller A, once by hand, base project)

In Engineer, a project for A (start from A's plain base project):

1. PLANT > Profinet > Device List > "Select type here", type "AXC F 2152", pick the newest **"AXC F 2152 Rev. >=
   2/V21.0.0"** (in the catalogue: Axioline F Profinet > Devices > Phoenix Contact > Axiocontrol > Controller
   Device). It comes with the module **"IO 512"**: 512 bytes each way.
2. Double click the new device in PLANT > Settings: **IP address** and **Name of station** (`plc-b`). Edit the
   address octet by octet: typing a whole address into the cell mangles it.
3. On its node "interface-1 : Interface" > Settings: the default update time of 8 ms gives the warning **PNIO0112**
   "cannot be updated cyclically faster than a value of 16 ms". Set "Reduction ratio" to 16 or more (32 used).
4. Ctrl+S, then `pxproj.py --strip <saved> ~/.plcnext-engineer/base/AXCF2152-2026.0-PNB.plcnx2`. `--strip`
   also drops ports of programs of an earlier build, so a project the generator built can be stripped again.

The module's data list has two items, both Octetstring[512]: **`DI4096`** (from the device) and **`DQ4096`** (to
the device). A program port of type `PND_IO_512` connects to each through `io`:

```
VAR
    PN_IN : PND_IO_512 { InputPort };     (* from device plc-b *)
    PN_OUT : PND_IO_512 { OutputPort };   (* to device plc-b *)
END_VAR
```

```json
"io": {"M.PN_IN": "DI4096", "M.PN_OUT": "DQ4096"}
```

The base fixes the device's address and name; for another device make another base (the generator handles one
device; more: untested). `pxe.sh` finds the controller's own PLANT node by itself; with several controllers in a
project set `PXE_CONTROLLER` to the one to connect to.

## Names and addresses

A Profinet controller finds its device by **name of station**, not by address.

- `target.station` in B's `program.json` writes the project setting "Name of station" of B's own project
  (`IP:DnsName` and `IP:ExtendedDomainName` of the controller's `.ds`); the PLANT node is then labelled
  `plc-b : AXC F 2152`. This did **not** name B on the network (**proven**): a scan showed both controllers
  answering as `axcf2152-lan1`, the firmware's default, A's BF-C lamp was red and nothing was exchanged.
- **The way that works** (**proven**): A's project open in Engineer and connected to A. PLANT > Profinet >
  **Online Devices**. In the drop-down choose the network adapter of the Engineer machine that is on the
  controllers' network, press the scan button. In the row of the project's device click the cell "Name of
  station (Online)" and pick the scanned device by its MAC address. Engineer assigns the name at once (a green
  tick); the exchange started within seconds.
- Once per device: the name stays on the device. After a restart of B's runtime the exchange came back by itself
  within about 20 s (**proven**); after a power cycle of B: untested. Not done from a script.
- Close the Online Devices editor afterwards: while it was open, UI Automation found no control of Engineer at
  all and every driver command failed with "no controller in the PLANT tree" (**seen**).
- **Address**: A sets B's IP address from its project when the connection starts (DCP). In the test it was the
  address B already had, so B stayed reachable. With a different address in A's project: untested. Expect B to
  move to A's address and to be unreachable at its old one (Engineer, page, SSH): put B's own address in A's
  project.

## Data layout and byte order

The bytes arrive in the order they were sent: byte n of B's `PND_S1_OUTPUTS` is byte n of A's `PN_IN`, and byte n
of A's `PN_OUT` is byte n of B's `PND_S1_INPUTS` (**proven**). Anything wider than a byte is the two programs'
agreement. The example packs 16-bit values high byte first (big endian):

```
PND_S1_OUTPUTS[0] := TO_BYTE(SHR(W, 8));                         (* sender, W : WORD *)
PND_S1_OUTPUTS[1] := TO_BYTE(W AND WORD#16#FF);
V := TO_INT(SHL(TO_WORD(PN_IN[0]), 8) OR TO_WORD(PN_IN[1]));     (* receiver: signed 16 bit *)
```

- A REAL goes across as an integer x 10 (or x 100), as above. Four bytes of a float would need `FB_TOIEEE` /
  `FB_IEEE` (`examples/modbus-rtu-room-sensor`; not tried over Profinet).
- Write the layout down once, in a comment in both programs: offset, size, meaning, scale. The example's:

| Bytes | B -> A | A -> B |
|---|---|---|
| 0-1 | temperature x 10 (INT) | A's counter (INT) |
| 2-3 | humidity x 10 (INT) | a set value x 10 (INT) |
| 4-5 | battery mV (WORD) | |
| 6-7 | B's counter (INT) | |
| 8 | status, bit 0: B's Modbus TCP server answers | |
| 10-11 | A's counter, sent back (echo) | |

The other bytes of the 512 are not written by either program.

## Checking it

- **BF-C lamp** on A (bus fault, controller): it was red while B had no name on the network and nothing was
  exchanged (**seen**), and off while data flows (**seen**). Look at it first after a write of A.
- **`PND_S1_VALID_DATA_CYCLE`** on B: TRUE while A exchanges data. Copy it into a program variable flagged
  `{ EHMI }` to read and show it (`PN_VALID` in the example).
- **A counter echo**: A sends a counter, B sends it back. When the echo on A follows A's counter, both
  directions work and B's program runs (**proven**). A counter of B's own (`B_BEAT`) moving on A shows that
  B's data is fresh; the example's `B_ALIVE` is TRUE while it moved within the last 3 s.
- `pxe.sh read` on each controller (`PLC_HOST=192.168.1.11` in front for B).

## Limits, not tried

More than one device on A; modules other than "IO 512"; generating the device entry (address, name in its `.ds`)
instead of a base made by hand; a device address in A's project different from B's own; whether the online name
survives a power cycle; what `PND_S1_VALID_DATA_CYCLE` and the data do when the cable is pulled or A stops; the other
`PND_S1_...` variables; update times other than reduction ratio 32; floats over the link; a third-party
Profinet controller or device; Profinet on a second Ethernet interface.
