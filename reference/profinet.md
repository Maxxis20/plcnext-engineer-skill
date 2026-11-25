# Profinet between two PLCnext controllers

Proven 2026-11-24 on two AXC F 2152 (firmware 2026.0.2) with PLCnext Engineer 2026.6: controller A is the
Profinet controller, controller B a Profinet device (station name `plc-b`). 16 of 512 bytes were used each way:
values of B's Modbus TCP server (temperature, humidity, battery), B's counter and a status bit arrived at A; A's
counter and a room temperature arrived at B, and A's counter came back to A as an echo. Values moved within a
second of the start. Example: `examples/profinet-pair` (A 192.168.1.10, B 192.168.1.11).
A ring of A, B and a managed switch with MRP, and the controller's diagnosis of its devices: sections "MRP ring
redundancy" and "Diagnosis on the controller", example `examples/profinet-mrp-ring`.

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
- **The controller's own name** (A): neither A's project nor a write sets it; A answers as the firmware's default
  (`axcf2152-lan1`). A DCP Set NameOfStation (option 2, suboption 2, "permanent") from any host on the same
  network renamed it (`plc-a`) while A ran its Profinet connections, without disturbing them; the name stayed
  after the next write and runtime restart (**proven**). Cosmetic: devices do not use the controller's name, but
  scans, LLDP neighbour tables (record 0x802A, the switch) then show it.
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

## MRP ring redundancy

Proven 2026-11-24 on A, B and a SCALANCE XC216 managed switch (firmware V4.4) with Engineer 2026.6, firmware
2026.0.2: the three in one ring, the switch as MRP manager, A and B as clients. Example with the program and its
pages: `examples/profinet-mrp-ring`.

### Roles and where they are set

- **Switch: MRP manager.** Import its GSDML (File > Import > Import GSDML File(s)...), take the catalogue entry that
  matches the switch's firmware (here "SCALANCE XC216 V4.4"), drag it onto A's `Profinet` node, give it an IP
  address and a name of station (`xc216`). On its interface node (`32768 : PN-IO`) > Settings, category **MRP 1**:
  Role **Manager**. Ring ports: its port nodes > Settings > "Ring port configuration", "Selected ring port: Yes" on
  ports 1 and 2 (the GSDML's default ring ports), the others not.
- **B (an AXC F 2152 as device): client.** Its interface node under A's Profinet > Settings: Role Client is the
  default. B's own project needs no MRP setting: A writes role, domain and ring ports to every device at the start
  of the connection (records 0x8052 / 0x8053, seen in the compiled project).
- **A (the Profinet controller): no setting.** Engineer 2026.6 has no MRP category for the controller's own
  interface. Its two ports still worked as ring ports: traffic went round the ring with either of A's cables pulled
  (**proven**, tests below).
- **Domain**: Engineer's default kept everywhere, UUID all-F, name `PLCNext-Engineer-MRP-Default`. A has no setting,
  so it can only be in that one; change it only together with all others.
- A's `Profinet` node > Settings: "MRP Configuration > Generate MRP Configuration" ticked (the default). The
  switch's PN-IO parameter "Media redundancy setting: Not by STEP7" Off, so the switch takes MRP from A.
- **Timing**: the switch's GSDML has `MinDeviceInterval` 128 ms; at a shorter update time Engineer warns
  `PNIO0112`. Reduction ratio 128 and monitor factor 3 gave 384 ms. B: 32 ms x 12 = 384 ms. The monitor factor must
  be a multiple of 3 (3..255). The manager's ring timing (test frames 10 / 20 ms, the 200 ms profile) kept as it
  was. Profinet node > tab **Interface List** shows every device's update and monitor time on one page.
- Keep the result as a base project, like any device (`pxproj.py --strip`).

### MRP 2..4: give them their own domain UUIDs

A catalogue entry with `MaxMRP_Instances="4"` in its GSDML (the XC216 V4.4 entry) shows four categories MRP 1..4
on the interface node. They cannot be removed: no delete, no menu, fixed values `PN:MRPRole_1..4`,
`PN:MRPDomainUUID_1..4` in the `.ds`. Engineer writes all four into record 0x8052, MRP 2..4 with role Off but in
the **same domain UUID** as MRP 1. The switch took MRP 1 (the ring worked) and refused the rest: its F lamp was red
and A read a parameterization fault (below, 0xE00C).

**Fix (proven 2026-11-24)**: give MRP 2..4 domain UUIDs of their own (e.g. `11111111-1111-1111-1111-111111111111`,
`22222222-...`, `33333333-...`, names `mrp-unused-2..4`), roles stay Off, MRP 1 unchanged. After the write: no
diagnosis from the switch (0xE00C empty), `PN_NO_DIAG` TRUE, `PNIO_SYSTEM_SF` and `PNIO_DIAG_AVAILABLE` off on A,
the switch reports no fault, its **F lamp off** (seen at the switch), and its redundancy mode reads "MRP Manager"
instead of "MRP Auto-Manager" (before, it had kept part of its own factory role). The values were written into the
base's `.ds` by hand and the base stripped again; the fields are the "Domain UUID" and "Domain" lines of
Engineer's categories MRP 2..4 (**seen**; entering them there: untested).

### Naming the switch

Online Devices as for B (section "Names and addresses"). The switch first refused every write from Engineer
(`MSG_NET0030` ... `SetNotPossibleByLocalReasons`): its DCP server was read-only after the switch's own setup. On
its CLI `dcp server read-write` (and save the configuration), then the name went in from Online Devices; A set
the address by DCP and the AR came up within a minute or two (**proven**). A replaces any address the switch had,
so its management address is then the one in A's project.

### Cabling: close the ring last

A ring of ports without an MRP manager is a loop. Cable a line first (switch port 1 - A port 1, A port 2 - B port
1), name the devices, write A, check that the switch is manager (`show ring-redundancy` on its CLI, or the page
below), then plug the last cable (B port 2 - switch port 2). The Engineer machine and any other network go on a
non-ring port of the switch, never into the ring.

### What the ring did (ring tests, 2026-11-24, pump running at 870 rpm)

| Test | Result |
|---|---|
| one cable pulled (A - B), then the switch - A | pump keeps running, no alarm, no AR lost on A or B; A still reachable around the ring; the switch's ring state active, passive again after the cable is back (**proven**) |
| both cables of B pulled (B cut off) | forced stop within one sample, drive stops at B (**proven**) |

With B cut off the input bytes fell to 0 at once, so the "safety chain OK" bit read as open before the heartbeat
timed out and the stop was named "safety chain". Name the link first, from `PN_AR_VALID` (section "Diagnosis on the
controller"). With that change a restart of B's runtime gave "Profinet link to plc-b lost" (**proven**); with a
pulled cable: untested.

How the controller reads ring state and diagnosis, and the page built on it: next section, and
`examples/profinet-mrp-ring`.

## Diagnosis on the controller

Proven 2026-11-24 on A with three devices (B, a managed switch as MRP manager, a p-net device), Engineer 2026.6,
firmware 2026.0.2. The program and its page "Network": `examples/profinet-mrp-ring`.

**Per device, as process data.** Every device's DAP brings items `PN_AR_VALID` (AR up, data exchanged),
`PN_NO_DIAG` (FALSE while the device reports diagnosis), `PN_APPL_RUN`, `PN_IS_PRIMARY` (BOOL). Program ports of
type BOOL, linked with the device's name of station in front because all devices have the same names:

```
B_AR_VALID : BOOL { InputPort };
```
```json
"io": {"M.B_AR_VALID": "plc-b/PN_AR_VALID", "M.X_NO_DIAG": "xc216/PN_NO_DIAG"}
```

`pxproj.py` finds the device by the `IP:DnsName` in its `.ds` and takes only items whose `SourceId` is one of that
device's modules. An unqualified name still takes the first match (old projects build unchanged).

**Controller-wide, as system variables** (`VAR_EXTERNAL`): `PNIO_SYSTEM_BF`, `PNIO_SYSTEM_SF`,
`PNIO_DIAG_AVAILABLE`, `PNIO_MAINTENANCE_REQUIRED`, `PNIO_MAINTENANCE_DEMANDED` (BOOL), `PNIO_CONFIG_STATUS`
(WORD; 3 seen with everything running), `PNIO_CONFIG_STATUS_READY`, `PNIO_CONFIG_STATUS_CFG_FAULT` (BOOL). With one
device reporting a diagnosis: SF TRUE, DIAG_AVAILABLE TRUE, BF FALSE.

**Records with `RDREC`** (library "PLCnext Controller", referenced by every project; pins from the library's
`Arp.Iec.Profinet.dll`): `REQ : BOOL`, `ID : DWORD`, `INDEX : INT`, `MLEN : INT`, `RECORD` (in-out, an `ARRAY OF
BYTE` at least MLEN long); `VALID`, `BUSY`, `ERROR`, `STATUS : DWORD`, `LEN : INT`. At most 32 instances.

- `ID` is the **Node ID** of the submodule, which Engineer assigns: in the `.ds` of each submodule,
  `PN:NodeID` (e.g. B's DAP 6, its interface 7, ports 8, 9; the switch's DAP 29, interface 30, port 1 31, port 2
  32). No `ADDRESS_TO_ID` needed.
- `INDEX` is an INT: indexes above 0x7FFF as negative numbers (0x802A -> -32726, 0xE00C -> -8180).
- Pattern that works: REQ TRUE on one cycle, call every cycle, take the data when `NOT BUSY AND VALID` (or
  `ERROR`), REQ FALSE for one call, again. Two reads a second (alternating ports) ran through the tests without
  a failed read.
- `STATUS` of a refused read is the Profinet error: `16#DE80B900` = read error, ErrorCode1 0xB9 (invalid type),
  what the switch answers to 0x8050.

| Record | Of | Result |
|---|---|---|
| 0xE00C all diagnosis of the AR | DAP (29) | **works**: DiagnosisData blocks (0x0010): API, slot, subslot, ChannelNumber, ChannelProperties, USI 0x8000 / 0x8002, then ChannelErrorType, ExtChannelErrorType, ExtChannelAddValue. LEN 0 = no diagnosis |
| 0x802A PDPortDataReal | each port (31, 32) | **works**: own port id, peer port and chassis (LLDP), MAU type, **LinkState** (the 2 bytes 8 before the end: port state 2 blocking / 5 forwarding, link 1 up / 2 down) |
| 0x8054 PDPortMrpDataReal | port | works, only the domain UUID (24 bytes) |
| 0x8050 PDInterfaceMrpDataReal | interface (30) | refused by the SCALANCE XC216 V4.4 (`DE80B900`) |

**MRP ring state** from the manager's two ring ports (0x802A): the manager blocks one ring port while the ring is
closed and forwards on both when it opens (IEC 62439-2). Both links up and one port blocking = closed; a link down
or both forwarding = open. Seen with the ring closed: port 1 forwarding, port 2 blocking (**proven**, two reads a
second, no failed read). The open case is the standard's behaviour: the page's warning, latch, Ack and event list
were proven with a test input that sets the state to open (`RING_SIM`); with a real pulled cable while this
program ran: untested.

**A parameter the device refused** shows as ChannelErrorType 0x0010 (parameterization fault), ExtChannelErrorType
0x8001, ExtChannelAddValue = record index (high word) and offset (low word): seen as 0x8052 / 0x0060 on the switch,
the MRP adjust record. Offset 96 is the domain UUID of the second of the four MRP instances Engineer writes, the
same as the first's. Fixed by giving MRP 2..4 their own domain UUIDs (section "MRP ring redundancy"); after that
the record read empty and the switch's F lamp went off (**proven**).

## A third-party device from its GSDML

Proven 2026-11-24: a Raspberry Pi running the rt-labs p-net sample app (GSDML "P-Net multi-module sample app",
slot 1 DIO 8xLogicLevel, slot 2 Echo Module) as a device of A, beside B and the switch, values live on A.
Details and UIA steps: `bench/pnpi/NOTES.md`, section 11.

- **Import** once per project: File > Import > Import GSDML File(s)..., tick the DAP, OK. The device then sits in the
  COMPONENTS catalogue under Network > Local > Devices > vendor; drag it onto the controller's `Profinet` node and
  keep the result as a base project, like any device.
- **Modules**: the device's Module List tab, row "Select type here": type part of the module name, double click
  the suggestion. Module parameters (GSDML `ParameterRecordDataItem`) are on the submodule's Parameters tab and
  are written by A at every connection start.
- **Address**: the IP field is one masked box (Backspace crosses octets): `{END}`, 16 x `{BACKSPACE}`, type the
  whole address. Gateway **0.0.0.0 is refused**; the device's own address is accepted and means "no router".
- **Timing**: the reduction ratio list follows the GSDML's MinDeviceInterval (1 ms there, so 8 ms gave no
  warning); monitor factor in steps of 3. A device without `MediaRedundancy` in its GSDML has **no MRP category**:
  it can hang on a switch port outside the ring with nothing to set.
- **Typed items**: GSDML `DataItem`s with types become typed data list items, `Float32` -> `REAL`, `Unsigned32` ->
  `UDINT`, `Unsigned8` with bits -> `Bitstring8` (`BYTE`) plus one BOOL per bit. Link ports to them through `io`
  with the station in front (`"pnpi/Output float from controller"`; the item names are the GSDML's texts,
  spaces and brackets included). The controller converts the byte order (Profinet is big-endian): a REAL sent came
  back equal (**proven**). Raw `~IN` / `~OUT` octet strings also exist.
- A writes the device's name-of-station only from Online Devices (by hand, as for B) unless the device already
  answers with that name; a device that keeps its own name (p-net stores it) is found by A directly. A then sets the
  IP by DCP, temporarily.

## Limits, not tried

More devices on A than the three of the ring example (B, a switch, a p-net device); a ring of more than three
stations, or a controller as MRP manager; the ring-open state read from the records with a real pulled cable (the
page was proven with `RING_SIM`); whether the switch's name and DCP setting survive its power cycle; modules other
than "IO 512"; generating the device entry (address, name in its `.ds`)
instead of a base made by hand; a device address in A's project different from B's own; whether the online name
survives a power cycle; what `PND_S1_VALID_DATA_CYCLE` and the data do when the cable is pulled or A stops; the other
`PND_S1_...` variables; update times of B other than reduction ratio 32; floats over the B link (typed Float32 items of a third-party device work, above); a third-party
Profinet controller; Profinet on a second Ethernet interface.
