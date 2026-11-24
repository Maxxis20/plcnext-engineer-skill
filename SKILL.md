---
name: plcnext-engineer
description: Program Phoenix Contact PLCnext controllers (AXC F 2152 and relatives) through PLCnext Engineer without hand clicking - write IEC 61131-3 Structured Text as plain files, generate the project file, open and compile it in the real tool, write it to the controller, build an eHMI operator page with live values, buttons and library symbols, and check the result. Use whenever the task is to build, change, download or inspect a PLCnext Engineer project (`.plcnx2`), to make an HMI page for a PLCnext controller, or when the user mentions PLCnext, PLCnext Engineer, AXC F, Axioline, eHMI or Phoenix Contact PLC programming.
---

# PLCnext Engineer, scripted

PLCnext Engineer has no command line and no free scripting interface. This skill works around that in two halves:

1. **Files.** A project file (`.plcnx2`) is a zip with the code as plain text inside. `scripts/pxproj.py` builds a
   complete project from Structured Text sources and a Python description of the operator page, on top of an
   empty *base project* that the tool itself made for the controller type and firmware.
2. **The tool.** `scripts/pxe.sh` opens that file in the real PLCnext Engineer, reads the compiler's errors, and
   presses Connect and Write and Start. Controls are found by UI Automation id, not by screen position.

Undocumented behaviour of one tool version (PLCnext Engineer 2026.6, build 9.4.230). On another version prove
each step again. `reference/findings.md` records what was proven and what was only tried; read it before changing
how anything is built.

## First use

**Where the scripts run.** `scripts/vm.sh` reaches the Windows machine that runs Engineer, by one of two
transports: `local` (the default in Git Bash on Windows: the scripts run on the Engineer machine itself and start
PowerShell directly; needs Git for Windows and Python 3 there) or `proxmox` (the scripts run elsewhere and the
Engineer machine is a Windows VM on a Proxmox host, reached through the qemu guest agent; set `PXE_TRANSPORT=proxmox`,
`PLCVM_NODE`, `PLCVM_NODE_IP`, `PLCVM_ID`, `PLCVM_USER`). Settings come from the environment or from
`~/.plcnext-engineer/config` (`NAME=value` lines; all of them described in `scripts/config.sh`), among them
`PLC_HOST`, the controller's address (default 192.168.1.10).

Run `scripts/pxe.sh check` before anything else, and again whenever something basic fails. One line per
requirement; it tells what is missing. Ask the user only for what needs their hands: installing Engineer, its
licence, the transport settings, the controller's password, a base project for a new controller type or firmware
(`reference/findings.md`, "Base project").

**Passwords.** The default way: the user types the controller's user and password into Engineer's own login
dialog once, at the first Connect, with "Remember credentials"; never into the chat. Scripts that need the
password themselves (`plc-ssh.sh` and what uses it: `plc-mqtt.sh`, `plc-opcua-client.sh`; `pxe-login.sh`) read
it from the environment variable named in `PLC_SECRET` (default `PLC_PASSWORD`), set by the user in their own
shell, or through their secret manager when `PLC_SECRET_RUN` names its runner (e.g. `"op run --"`). It travels
on stdin only: never printed, never in a command line, never on disk. Never ask for the value, never print it.

When the password is available that way, `scripts/pxe-login.sh [user]` can fill Engineer's login instead of the
user: press Connect so the dialog shows, then run it. It passes the password to the dialog through a named pipe,
ticks "Remember credentials" and presses OK.

Tell the user once: **hands off the keyboard and mouse of the machine that runs Engineer while a command runs.**

Never write to a controller the user has not named for this work, and never reset one, on your own.

## The loop

```bash
P=scripts/pxe.sh
$P check                      # Engineer machine / Engineer / controller reachable, base projects
$P build <program dir>        # sources -> <program dir>/<name>.plcnx2        (seconds, no tool needed)
$P open <program dir>/<name>.plcnx2    # opens in Engineer under a fresh name; prints "N errors, M warnings"   (1-2.5 min)
$P errors                     # the compiler's messages: run it when errors OR warnings are not 0
$P write                      # connect, Write and Start, wait until the controller runs this project       (2-6 min)
$P state                      # connected / project on the controller / memory / CPU load
$P read M.TE1 M.TV1 M.ALARM   # current values straight from the controller, 3 s, no screen needed
$P wait M.TE1 57 59 300       # block until M.TE1 is inside 57..59, at most 300 s (BOOL: wait M.ALARM 1 1)
$P set M.SQ_CMD=1 M.SIM=true  # write variables over REST ({ EHMI }), as a page button does; no session needed
$P hmi out.png                # the operator page in a browser window over Engineer, screenshot. Read the PNG.
$P mqtt 6                     # what the broker receives in 6 s, "topic payload" lines (section MQTT below)
$P tap 1150 622 [x y ...]     # click on the operator page at PAGE coordinates (the ones in hmi.py); several pairs = several clicks
$P show M                     # Engineer in front, debug mode on, program instance M open with live values in the code
$P shot out.png               # screenshot of the whole desktop. Read the PNG.
```

- One command at a time, in the foreground. Give the shell call a timeout of **at least 420 s** for `write` and
  240 s for `open`; the others finish within 30 s. One `wait` per call, of at most 150 s; wait again if needed.
  If your harness moves a long call to the background, wait for its result: never start another command against
  the Engineer machine while one runs.
- A command that ends with `vm.sh: the Engineer machine does not answer` did not reach the machine at all (it is
  off, starting, or hung; the transport has already tried for a minute): nothing is wrong with the project or the
  controller. Try once more after two minutes; if it fails again, tell the user and do not go on.
- A warning counts: `0 errors, 2 warnings` has meant two buttons that do nothing. Read `errors` and fix.
- A full turn (build, open, write, look) costs about 5 minutes, nearly all of it `open` and `write`. So get as
  much right as you can before each `write`: read your own sources again, and lay the page out on paper.
- Fix errors in the sources and build again: never edit the project in the tool, the next build overwrites it.
- `open` always makes a new file name, so the project name on the controller tells you which build is running.
  It goes offline first (a connected Engineer ignores File > Open) and says `open: FAILED` when the new project did
  not come up.
- Use `wait` to let a loop settle or a reaction arrive, `read` to check values; never poll with screenshots or
  sleep loops. Take screenshots only for what must be seen.
- `write`, `open`, `state` and `show` bring Engineer to the front and close the browser. Run `hmi` again
  afterwards if the operator page is to stay on the screen. `read`, `wait`, `tap` and `shot` disturb nothing.
- Every verb costs 8-10 s of overhead on top of its own work. Do not chain two `wait`s, or a `wait` after
  several other verbs, in one shell call (a `read` right after a `wait` is fine).
- Red entries in Engineer's Online Log after a good `write` (`Connection lost`, `MSG_ONL0156 An error occurred
  while writing ...`) are the controller restarting its runtime. `write: ok` and the project name are what count.

## A program directory

```
<dir>/program.json
<dir>/src/<POU>/Variables.var      declarations, IEC text
<dir>/src/<POU>/Code.st            body, IEC Structured Text
<dir>/src/<POU>/Code.ld.py         instead of Code.st: body as ladder / function block diagram (pxld.py)
<dir>/hmi.py                       optional: pages() -> [pxhmi.Page]
```

`program.json`:

```json
{
  "name": "MYPROJ",
  "base": "AXCF2152-2025.6",
  "pous": [{"name": "FB_FILTER", "kind": "FunctionBlock"}, {"name": "MAIN", "kind": "Program"}],
  "tasks": [{"name": "Cyclic100", "interval_ms": 100, "instances": [{"name": "M", "program": "MAIN"}]}],
  "target": {"ip": "192.168.1.10"},
  "hmi": "hmi.py",
  "hmi_server": {"login": false, "rest": true}
}
```

- `base`: name of a base project in the work folder (`pxe.sh check` lists them). It fixes controller type and
  firmware; the controller refuses a project made for another firmware.
- `pous`: list every POU, a type before the POUs that use it. `kind`: `FunctionBlock`, `Function` or `Program`.
- `tasks`: cyclic tasks and the program instances they run. The instance name is what the HMI refers to.
- `target`: where the Cockpit connects. `{"simulation": true}` runs without a controller on Engineer's own
  simulation (free for the AXC F 1152, base `AXCF1152-2026.0`): slower to start and with its own names and
  address, see `reference/findings.md`, "Simulation", before using it. `"station": "plc-b"` beside `ip` sets the
  project's Profinet "Name of station" of the controller (lower case, digits, `-`); it labels the PLANT node but
  does not name the device on the network (section "Profinet between controllers").
- `hmi_server.login: false` switches the operator page's login off. Bench use only; say so to the user.
- `modbus_tcp` (optional): the remote Modbus TCP server and the registers to read, `{"ip": "192.168.1.50",
  "unit": 1, "port": 502, "registers": [{"name": "VALUE_HI", "fc": 4, "address": 0}]}`. Needs a base project
  with the client (`reference/modbus-tcp.md`). `io` links ports to process data (section "I/O modules and ports").
- `opcua` (optional): `{"visibility": "marked"}` makes the controller's OPC UA server show the variables flagged
  `{ OPC }`. Every base comes with "none": without this the flag shows nothing (`reference/opcua.md`).
- `datalogger` (optional): DataLogger sessions (TSDB) that record ports for trend charts on the page,
  `[{"name": "Speed", "sampling_ms": 1000, "variables": ["M.TR_SPEED_ACT"]}]`. Ports only (`{ OutputPort }` copies
  of the page's values). Write and Start starts them. `reference/hmi-trends.md`.
- `opcua_client` (optional): connections of the firmware's OPC UA client to other servers and the variables it
  copies (`connections`, `groups` of type `Subscribe` / `Write`, `trust_all`). Section "OPC UA between
  controllers".

### Structured Text, as this tool takes it

`Variables.var` holds only declarations, `Code.st` only the body (no `PROGRAM` / `END_PROGRAM` lines):

```
VAR_INPUT
    X   : REAL;          (* comment *)
    TAU : REAL := 10.0;
END_VAR
VAR_OUTPUT
    Y : REAL;
END_VAR
VAR
    xInit : BOOL;
    fbLag : FB_FILTER;   (* instance of another POU of this project *)
END_VAR
```

- One variable per line, `NAME : TYPE [:= init] [{ flags }];  (* comment *)`. The generator adds the ids the
  tool wants.
- Flags: `{ EHMI }` makes a variable visible to the operator page, `{ OPC }` to OPC UA; `{ EHMI, OPC }` both.
  Only program variables of an instantiated program can be shown; flag every one the page uses.
- Proven to compile: `REAL`, `BOOL`, `INT`; plain literals (`0.5`, `-5.0`, `TRUE`, `2`), also as initial values;
  `IF / ELSIF / ELSE / END_IF`; `AND`, `OR`, `NOT`, comparisons (`<`, `<=`, `>`, `>=`, `=`, also against negative
  literals); `ABS`; expressions as arguments of a call; initial values on a block's own `VAR` and `VAR_OUTPUT`; function block calls
  `fb(IN := x, T := y);` and `fb.OUT`; BOOL from an expression (`X := (A < -45.0) OR (A > 50.0);`), brackets,
  division; statements over several lines; `(* comments *)`; blank lines and
  comment-only lines inside `VAR` blocks.
- Proven on the controller (`examples/mqtt-subscribe`): `UDINT`, `DINT`, `BYTE`, `WORD`, `DWORD` and typed
  literals (`BYTE#16#22`, `DWORD#16#FF`); `ARRAY[0..n] OF BYTE` declared inline, as `VAR`, `VAR_OUTPUT` and
  `VAR_IN_OUT`; `STRING` and `STRING[120]`; `LEN`, `MID`, `FIND`; `WHILE`, `FOR`, `CASE`; `TO_BYTE`, `TO_INT`,
  `TO_DINT`, `TO_UDINT`, `TO_REAL`, `TO_DWORD`, `SHL`, `SHR`, `AND` on bit strings; the output array of one block
  passed to the `VAR_IN_OUT` of another (`JT(BUF := MQ.PAYLOAD, ...)`, no copy).
- A string literal must not contain a backslash, and `$` starts an escape ("String literal contains Invalid
  escape characters"). No direct character-to-byte conversion was found: look the character up with `FIND` in a
  table string (`reference/mqtt-subscribe.md`, "Characters"). No bit cast between DWORD and REAL either
  (`FB_IEEE`).
- System variables of the firmware are declared `VAR_EXTERNAL` in the program and used like any variable
  (**proven** with the Profinet device's `PND_S1_INPUTS : PND_IO_512;`, a 512 byte array indexed `[0]..[511]`,
  and `PND_S1_VALID_DATA_CYCLE : BOOL;`, `reference/profinet.md`).
- Not tried in ST: `TIME` and the standard timers (`TON`; proven in a diagram), structs. If you need them, write
  a small test POU first and read the errors. Timers can be avoided by counting seconds with the cycle time
  (`acc := acc + TS;`).
- Avoid IEC keywords and type names as variable names: `DT`, `T`, `EN`, `ENO`, `IN`, `OUT`, `TIME`, `DATE`. A
  variable named like a function or POU (`NEG`, `RS`) gives a warning; one named `LEN` clashes with `LEN`. A
  program instance named `D` is refused ("Invalid program instance name"); `DRV` works.
- `%%ENV:NAME%%` anywhere in a source is replaced at build time with the environment variable `NAME` (the build
  stops when it is not set): for a password the program itself needs, such as a database client's. Build
  through the secret manager's runner; the built `.plcnx2` then holds the value, so never commit or share it.
  Never pass a secret through a page variable: with login off, REST reads it back.
- A program does not know its cycle time. Keep it in one variable (`TS : REAL := 0.1;` for a 100 ms task) and
  pass it to the blocks that integrate or delay.
- With no I/O modules, put a plant model in a function block and feed the controller from it (`SIM` switch).

### I/O modules and ports

Hardware modules come with the base project: add the module in Engineer once (PLANT > Axioline F > Device List,
type its name), set its parameters, save, `pxproj.py --strip` it to a base of its own (`reference/findings.md`,
"I/O modules"). The program reaches the module's process data through ports:

```
VAR
    STAT_L : BYTE { InputPort, EHMI };      (* from the module *)
    CTRL_H : BYTE { OutputPort, EHMI };     (* to the module *)
END_VAR
```

and `program.json` says which port goes where: `"io": {"M.STAT_L": "Status Word Low Byte", "M.CTRL_H": "Control
Word High Byte"}` (instance.variable: name of the process data item as the module's Data List shows it). Types
must fit (8 bit item: BYTE, 16 bit: WORD). Worked examples: `examples/rs-uni-modbus`, `examples/modbus-rtu-room-sensor`
(proven on the controller). The D lamp in the Cockpit is green when the module on the
rail matches the project.

### Modbus RTU devices

A serial module (AXL F RS UNI 1H) makes the controller a Modbus RTU master. Read `reference/modbus-rtu.md`
first: wiring, the base project with the module, the probe (`examples/rs-uni-modbus`: find address, register
base and word order of an unknown device from a page), the exchange with the module, frames, and how a value
with two writers (page and device) is kept. Complete device with page: `examples/modbus-rtu-room-sensor`.

### Modbus TCP devices

The firmware has its own Modbus TCP client: configured in the project, nothing to program. Read
`reference/modbus-tcp.md` first: the base project with the client and one server (made once by hand), the service
switch on the controller, the status items. Then `program.json` gets `modbus_tcp` (server address, unit, registers)
and `io` links one WORD port per register (`"M.VALUE_HI": "VALUE_HI_input"`) and the status items (`"M.MB_STATE":
"STATE"`, UDINT). Reading function 3 / 4 only. Floats: two registers into `FB_IEEE`. Example:
`examples/modbus-tcp-read`.

### OPC UA between controllers

Every controller runs an OPC UA server (port 4840); the firmware also has a configured OPC UA client that copies
variables to and from another server. Nothing to program: no client function blocks exist. Read
`reference/opcua.md` first. In short:

- Server (A): flag the variables `{ OPC }` and set `"opcua": {"visibility": "marked"}`. Add a user for the
  client in A's web interface (Security > User Authentication, role DataChanger): no anonymous access.
- Client (B): switch the service "OPC UA Client" on (web interface > System Services), then `opcua_client` in
  `program.json`: groups `Subscribe` (A -> local variable) and `Write` (local -> A), `"M.A_TEMP": "M.TEMP"`.
  Any program variable of B, no port; REAL, BOOL, INT, DINT.
- The password stands in clear in the client's configuration. Prefer `password_secret` (the name of an
  environment variable, read as in "Passwords"): the connection stays out of the project and
  `PLC_HOST=<client> scripts/plc-opcua-client.sh <program dir>` puts it on the controller after the write.
- `"trust_all": true` lets B take A's certificate; bench only, say so.
- Without the vendor's client licence the client runs 4 hours from the start of B's runtime. A Write and Start
  does not start them again; only `sudo systemctl restart plcnext` (or a reboot) does. Tell the user.
- Check in B's `Arp.log`: `ConnectFinished - Connected to server endpoint`. The program sees no link state: when
  the trial ends the mapped variables simply keep their last values on both sides. Send a counting value across
  and watch it move. Example: `examples/opcua-pair`.

### Profinet between controllers

A controller (A) exchanges up to 512 bytes each way with another PLCnext controller (B) that acts as a Profinet
device, in real time beside the other Ethernet traffic. Read `reference/profinet.md` first. In short:

- Device (B): no hardware entry. The program declares the system variables `PND_S1_OUTPUTS`, `PND_S1_INPUTS`
  (`PND_IO_512`) and `PND_S1_VALID_DATA_CYCLE` (BOOL) as `VAR_EXTERNAL` and reads / writes the bytes.
  `"target": {"ip": ..., "station": "plc-b"}`.
- Controller (A): B as a device in PLANT > Profinet (type "AXC F 2152 Rev. >= 2/V21.0.0", module "IO 512", IP
  address, name of station, reduction ratio 16 or more against warning PNIO0112), made once by hand and kept as
  a base project. Ports `PN_IN : PND_IO_512 { InputPort }`, `PN_OUT : PND_IO_512 { OutputPort }`, `"io":
  {"M.PN_IN": "DI4096", "M.PN_OUT": "DQ4096"}`.
- **B's name on the network is set by hand**, once per device: A's project connected, PLANT > Profinet > Online
  Devices, scan, pick B by its MAC address in "Name of station (Online)". `target.station` does not do it. Until
  then A's BF-C lamp is red and nothing moves. Not scripted: ask the user to do it.
- A sets B's IP address from its project at the start: give A's project B's own address.
- Bytes arrive in the order sent; pack wider values yourself (high byte first in the example). Check with
  `PND_S1_VALID_DATA_CYCLE` on B and a counter that B sends back to A. Example: `examples/profinet-pair`.

### MQTT in

The firmware's MQTT client only publishes. To receive, `FB_MQTT_SUB` (a small MQTT 3.1.1 client on the socket
blocks of the "PLCnext Controller" library) and `FB_JSON_NUM` (one number from a JSON payload) go into the
program: copy them from `examples/mqtt-subscribe/src/`. Plain TCP, no login, one topic, QoS 0, reconnects by
itself. Read `reference/mqtt-subscribe.md` first: pins, states, error codes, the characters a topic may hold
(no `#`, no space), a ChirpStack uplink as example.

### Step sequences

SFC needs a licence of its own (`LIC001 No license for SFC found`; without it the editor does not open) and
`pxproj.py` does not generate it. Write the sequence in ST: one INT for the step, per step a list of requirements
walked one by one, a settle time, a supervision time, an alarm held until Reset or Continue, Manual Next / Go to
below the forced stop, outputs computed from step and interlocks after the sequence. Read
`reference/sequence-st.md` first. Worked example with a drive simulator over Profinet, pages and a test script of
41 checks: `examples/pump-sequence` (proven on two controllers).

### Values into a database (ClickHouse)

`FB_CH` and `FB_TXT` (`examples/clickhouse-log/src/`) store up to 16 values every second in ClickHouse over its
HTTP interface (plain HTTP, batched inserts every 10 s, time stamps from the age of each sample, so the
controller's clock is not used) and read a query's numbers back for display. A user of its own with
`INSERT, SELECT, CREATE TABLE ON plc.*`; its password goes in with `%%ENV:NAME%%`. Read `reference/clickhouse.md`
first: design, proven numbers, limits, security, Grafana.

### Ladder and function block diagram (`Code.ld.py`)

A POU may have `Code.ld.py` instead of `Code.st`. It describes the diagram; `pxld.py` places the objects in
columns along the signal flow, routes the wires and writes Engineer's LD/FBD worksheet. Declarations stay in
`Variables.var`, including every function block instance (`TON1 : TON;`). Mix freely: one POU in ST, the next
as a diagram. Worked example: `examples/ld-demo` (proven on the controller).

```python
def code(d):
    d.network("Start with delay")
    a = d.fn("AND", "START", d.neg("STOP"))            # function, inputs in pin order; d.neg = negated pin
    t = d.fb("TON1", "TON", IN=a, PT="T#5s")           # function block instance, inputs by pin name
    d.out("RUN", t["Q"])                               # RUN := TON1.Q
    lim = d.fb("LIM1", "FB_LIMITS", VALUE="LEVEL", LOW_LIMIT="10.0", HIGH_LIMIT="40.0")   # a POU of this project
    d.out("ALARM", d.fn("OR", lim["TOO_LOW"], lim["TOO_HIGH"]))
    d.rung("START", d.par("A", ["B", "/C"]), coils=["LAMP", "S:LATCH"])       # ladder rung
    d.rung("RUN", d.fb("TON2", "TON", PT="T#2s"), coils=["R:LATCH"])          # a block in a rung
```

- An input is a text (variable or constant), a block (its first output), `block["PIN"]`, or `d.neg(...)` of one.
- `d.network(title)` starts a group; blocks of one network are laid out together. A value may be used in a later
  network (the wire runs there); for a value used far away, write it to a variable and read the variable.
- Rung: items in series; a list is a series, `d.par(a, b, ...)` parallel branches. Contacts `"X"`, `"/X"`
  (normally closed); coils `"X"`, `"/X"`, `"S:X"`, `"R:X"`. A block in a rung takes the rung on its first free
  input and passes it on from its first output.
- Pins: this project's function blocks are read from their `Variables.var`; standard ones are in `PINS` in
  `pxld.py` (AND OR XOR ADD MUL MAX MIN take any number of inputs). For another library block name the pins:
  `d.fn("X", A=..., B=..., outs=["Y"])`.
- Edge contacts: `"P:X"` rising, `"N:X"` falling (compile; not exercised).
- A plain copy is `d.out("Y", "X")`. A comparison cannot sit in a rung (no BOOL input): put `d.out("TOO_HIGH",
  d.fn("GT", "TE1", "65.0"))` in a block network and read `TOO_HIGH` with a contact.
- A sheet is one column of networks and gets tall (26 networks: nine screens). `show` shows its top. To see
  more: zoom out with the "-" of the zoom slider at the right end of the status bar (`pxe.sh click <x> <y>`, 10 %
  per click; find it on a `shot`) and click on the
  overview map at the right edge of the sheet to jump. The title of `d.network(title)` is not drawn.
- Proven at size: sheets of 19 and 26 networks, a whole district heating controller in each.
- No feedback wires: write the value to a variable with `d.out` and read the variable (it is then the value of
  the previous cycle where it is read before it is written). Objects run in the order they are created.
- Not there: EN / ENO, jumps, comments on the sheet, the NOLD worksheet type, SFC.
- A page wider than 1300 gets a browser window over the whole screen width (three panels side by side fit).
- Look at the result: `pxe.sh show <instance>` after `write`, then `shot`. Wires may cross; a wire through a block
  means too much in one network: split it.

### The operator page (`hmi.py`)

```python
from pxhmi import Page

def pages():
    p = Page("Home", 1280, 800, fill="#FFF3F4F6")             # first page = start page
    p.rect("card1", 20, 60, 300, 200, fill="#FFFFFFFF", line="#FFD5D9DD", radius=8)
    p.text("t1", 36, 72, 260, 24, "Outdoor temperature", size=16, weight=700, color="#FF2B2F33")
    p.value("v1", 36, 110, 90, 34, "M.TOUT", size=26, weight=700, color="#FF1F5FD0", align="Right", fmt="fixed1")
    p.text("u1", 130, 110, 60, 34, "°C", size=26, weight=700, color="#FF1F5FD0")
    p.button("b1", 36, 160, 56, 32, "-5", step=("M.TOUT", -5))            # add to a variable
    p.button("b2", 100, 160, 80, 32, "Trip", write=("M.P1_TRIP", "TRUE")) # set a variable
    p.ellipse("lamp1", 36, 210, 18, 18, fill="#FFB8BCBF", fill_by=("M.ALARM", [(0, "#FFB8BCBF"), (1, "#FFD93A32")]))
    p.text("s1", 60, 208, 80, 22, "RUN", color="#FF1E8E3E", visible="M.P1_ST = 1")   # shown while the expression is true
    p.rect("bar", 36, 240, 110, 8, fill="#FFF29D0C", grow=("M.TV1_POS", 0, 100))     # bar: grows from its left edge, full width at 100
    p.line("d1", 200, 260, 260, 60, color="#FF2B2F33", width=2)
    p.pump("pump1", 400, 303, "M.P1_ST", flow="left")          # centre point on the pipe; red 0, green 1, red 2
    p.valve("valve1", 500, 303, "M.TV1_POS")                   # centre point on the pipe; coloured by position 0..100
    return [p]
```

- A variable is `<instance>.<VARIABLE>` (`M.TOUT`): instance name from `program.json`, variable flagged `{ EHMI }`.
  A missing flag gives `The field or variable 'X' does not exist in '<program>'` at `open`.
- Every object needs its own id (first argument): letters, digits, underscore, unique on the page. Colours are
  `#AARRGGBB`.
- Signatures (all in `scripts/pxhmi.py`):
  `text(id, x, y, w, h, text, size=16, color, weight=400, align="Left", visible=None)`;
  `value(id, x, y, w, h, expression, fmt="fixed1", + the keywords of text)`;
  `rect(id, x, y, w, h, fill, line, line_width=1, radius=0, fill_by=None, grow=None, axis="x", visible=None)`
  (`axis="y"`: a `grow` bar that grows upward from its bottom edge);
  `ellipse(id, x, y, w, h, fill, line, line_width=1, fill_by=None, visible=None)`;
  `line(id, x1, y1, x2, y2, color, width=1)`; `poly(id, points, fill, line, line_width=2, fill_by=None)`;
  `button(id, x, y, w, h, text, write=None, step=None, size=14, page=None)` (`page="Trends"`: switch to that page);
  `chart(id, x, y, w, h, session, pens, minutes=15, sampling_ms=1000, left=(0, 0), right=(0, 0))` (trend chart over a
  DataLogger session: `reference/hmi-trends.md`);
  `pump(id, cx, cy, state, r=24, flow="right")`; `valve(id, cx, cy, position, size=20)`.
- `value(...)` shows one decimal by default (`fmt="fixed1"`; `fixed0`, `fixed2` ...; `fmt=None` for a whole number
  or a text). Put the unit in a separate `text`.
- A controller that is switched off by a fault (P2 trip closes TV2) starts from 0 after the reset: its loop needs
  its settling time again. Plan the proof so nothing waits on that, or `wait` on the measured value.
- `fill_by=(expression, [(threshold, colour), ...])`: colour of the highest threshold the value reaches. Works
  for BOOL (0 / 1) and numbers.
- `visible="<expression>"`: ST expression, e.g. `M.ST = 2`, `NOT M.SUMMER`.
- Text is one line and is **clipped at the box width**; it does not wrap. Arial needs about 0.45 x font size
  per character (a 23-character label at size 13 measured 126 px). Make boxes generous; a too wide box costs
  nothing, but leave room for what stands to the right of it.
- `button(..., step=(var, -5))`: whole numbers only, also negative, on REAL and INT (`0.1` is rejected with a
  warning and the button does nothing, `0.5` with "Invalid step value": keep the value as an INT x 10, step by 5). `button(..., write=(var, "10.0"))` sets a REAL, `"TRUE"` / `"FALSE"` a BOOL.
- `Pump`, `Valve`, `Control Valve` draw white while their BOOL is TRUE and grey while FALSE.
- `pump(id, cx, cy, state, r=24, flow="right")`: a circle with an arrow, **centred on (cx, cy)**. Put the centre
  on the pipe's centre line (for a pipe `rect(x, y, w, 7)` that is `y + 3.5`). `state` is an expression: red at
  0 (stopped), green at 1 (running), red from 2 on (fault); a BOOL works too. `flow` is the way the arrow points:
  on a return line it points back towards the exchanger. It covers `cx - r .. cx + r`, `cy - r .. cy + r`.
- `valve(id, cx, cy, position, size=20)`: a control valve with actuator, **centred on (cx, cy)** on the pipe.
  Its body is grey when closed, light green when open, full green from half open on. `position` is 0..100 %
  (or a BOOL). It covers about `cx - size .. cx + size` and reaches `1.75 * size` above the pipe.
- `poly(id, [(x, y), ...], fill=..., fill_by=...)`: any closed, filled shape.
- The tool's own library `Symbols-Schematic` also has `Pump`, `Valve`, `Control Valve` (`p.symbol(id, x, y, name,
  bool_variable, scale, rotation)`, library listed under `libraries`): they only turn white / grey with one BOOL
  and are placed by their top left corner. Prefer `pump()` and `valve()`.
- No heat exchanger symbol exists; draw a `rect` with a diagonal `line`.
- Draw pipes as thin `rect`s. Objects are drawn in the order you add them: backgrounds first.
- `pxe.sh hmi` shows the page in a browser window over Engineer (three quarters of the screen wide, as high as
  the page needs), scaled to fit. `tap` takes PAGE coordinates and works out the place on the screen itself.
- Every `write` restarts the program from its initial values. With slow tuning (integral times of a minute) a
  loop then needs minutes to settle. Start near the steady state: give the model's temperatures initial values
  near their set values, and give the PI block an initial output (an input `Y0`, taken over on the first
  cycle), e.g. 30 %. Then `wait` on the measured value before the "settled" screenshot.
  Take the "settled" screenshot before any disturbance test: after a load step a slowly tuned loop swings for
  3 to 5 minutes. A PI with a dead band creeps toward the edge of the band and may never cross it: make the
  `wait` window the dead band plus 1 degree on each side, or the wait times out (one run lost three waits of
  150 s that way). For a bench demonstration a shorter integral time than the description's is fair; say so.
- Check the page with `pxe.sh hmi out.png` and Read the picture; fix overlaps and build again.
- For a page that looks finished (palette, cards, status banner, step chips, checklist, mode switch, interlock
  ladder, bars): `reference/hmi-design.md`, with `examples/pump-sequence/a/hmi.py`.
- A light / dark look: a BOOL in the program, two buttons that write it, `fill_by=(var, [(0, light), (1, dark)])`
  on the areas, and each text twice with `visible=` (`examples/modbus-rtu-room-sensor/hmi.py`, helper `both`).

## Values out over MQTT (and a FUXA view)

The controller's firmware publishes by itself; nothing to program, only to flag (findings, section MQTT).

1. **Flag** the variables in the program's `VAR` block: `TE1 : REAL { EHMI, OPC, OutputPort, PROFICLOUD };`.
   Build, open, write as usual. BOOL arrives as 1/0. Not `VAR_OUTPUT` (error in a program).
2. **Broker, once per controller**: `scripts/plc-mqtt.sh <broker ip> <topic> [client id]` writes the settings file
   and reboots the controller (2.5 minutes; `plc-mqtt.sh off` undoes it). The broker must be reachable when the
   controller starts, or reboot it again. Publish only, QoS 0, plain TCP, one broker.
3. **Look**: `pxe.sh mqtt 6` prints what the broker receives. One JSON message a second on `<topic>` with all
   flagged values, and, from `mqtt-flatten.js` beside the broker, one retained topic per value: `<topic>/TE1 57.5`.
4. **FUXA view**: a `fuxa_view.py` with `pxfuxa.Fuxa` (`tag(name, topic)`, `text`, `box`, `line`, `value`,
   `lamp`, `save`; example `examples/dh-ex2/fuxa_view.py` where the skill came with its examples), then `pxe.sh fuxa <project.json> out.png` and Read the picture.
   The view only reads: the firmware client cannot subscribe.

Values **into** the program from a broker: section "MQTT in".

## Checking the result

- `pxe.sh state` after `write`: `Project name:` must be the name `open` printed, CPU load sane.
- `pxe.sh read ...`: values must be live and plausible. `ERROR NotExists` = wrong name or no `{ EHMI }` flag.
- To exercise logic, give the page buttons that write test inputs (trip a pump, step a temperature), press them
  with `pxe.sh tap <x> <y>`, then `read` the reaction (a few seconds later) and take one `shot` as proof.
  `tap` returns before its last click has landed (one pair or several): `sleep 3` before a `read` in the same call.
  `hmi` needs about 15 s before its picture is taken and the process moves on meanwhile: for a picture of a
  passing state, take `hmi` first and `shot` at the moment (the page window stays open; `shot` is immediate).
  `wait` returns on the first sample inside its window, also when the value is only passing through: wait on a
  signal that comes from one side (a valve output, a filtered set value) or wait twice.
  `tap` wants the centre of the button: `button()` takes the top left corner and size, so x + w/2, y + h/2.
- For a demonstration, `pxe.sh show <instance>` puts the program with its live values on the screen, and
  `pxe.sh hmi` the operator page.
  `show` leaves Engineer in debug mode with the program's editor open; that is harmless, `write` and `open`
  work from there.
- Say plainly what was checked on the controller and what was only compiled.

## Where things are

| Path | What |
|---|---|
| `scripts/pxe.sh` | the driver, one verb per step |
| `scripts/pxproj.py` | project generator; `--strip` makes a base project from one the tool saved |
| `scripts/plc-ssh.sh` | a shell on the controller, password as in "Passwords"; `--out` / `--in` for backup and restore, `PLC_SECRET` / `PLC_HOST` for another controller |
| `scripts/plc-backup.sh` | `backup [name]` / `restore <archive>` / `check <archive>`: the controller's project and settings into a local archive with checksum, and the project back (findings, "Backup and restore") |
| `scripts/pxld.py` | ladder / function block diagram worksheets with layout and wires |
| `scripts/pxhmi.py` | operator page elements |
| `scripts/config.sh` | the settings (transport, controller address, password variable), read from the environment or `~/.plcnext-engineer/config` |
| `scripts/vm.sh` | transport to the machine that runs Engineer, `local` or `proxmox`: PowerShell (`ps`, `ui`), files (`put`, `get`), screenshots, mouse and keys, UI Automation |
| `scripts/plc-mqtt.sh` | broker settings of the controller's MQTT client, then reboot |
| `scripts/pxfuxa.py` | FUXA project generator (MQTT tags, a view with live numbers and lamps) |
| `scripts/win/mqtt-flatten.js` | beside the broker: one topic per value out of the controller's JSON message |
| `scripts/win/` | PowerShell that runs on the Engineer machine |
| `scripts/plc-opcua-client.sh` | OPC UA client connections onto the controller, passwords as in "Passwords", then runtime restart |
| `scripts/pxe-login.sh` | fills Engineer's controller login with the password (first connect to a controller) |
| `reference/modbus-rtu.md` | Modbus RTU through a serial module: steps, probe, frames, pitfalls |
| `reference/modbus-tcp.md` | Modbus TCP with the firmware's own client: base project, registers, status items |
| `reference/opcua.md` | OPC UA server and the firmware's client between two controllers: users, passwords, certificates, log |
| `reference/profinet.md` | Profinet between two controllers: device by system variables, controller base by hand, naming, byte layout |
| `reference/mqtt-subscribe.md` | MQTT subscriber in Structured Text: the two blocks, states, characters, ChirpStack |
| `reference/hmi-trends.md` | trend charts on the page: DataLogger sessions, port copies, time range and point limits, page switch |
| `reference/hmi-design.md` | operator pages that look good: palette, cards, banner, step chips, checklist, mode switch, interlock ladder, bars |
| `reference/sequence-st.md` | step sequences in ST (why not SFC), requirements, settle and supervision times, alarms, overrides, the page |
| `reference/clickhouse.md` | values into ClickHouse over HTTP: batching, time stamps, read back, security, Grafana, alternatives |
| `reference/findings.md` | file format, tool behaviour, controller facts: proven / seen / untested |
