# Findings: PLCnext Engineer 2026.6 driven from outside

Worked out in November 2026 against PLCnext Engineer 2026.6 (build 9.4.230.0) on Windows 11 and one AXC F 2152
with firmware 2025.6.0 and no I/O modules. Each fact is marked **proven** (done and checked), **seen** (observed
once, not exercised) or **untested**.

## No scripting interface

- No command line switches beyond opening a project file, no free API (**seen**: nothing in the installation; a
  paid, undocumented add-in "ACI" exists according to Phoenix Contact's forum).
- Engineer is a .NET 10 WPF application. Its controls carry UI Automation ids (`AID_...`), which is what the
  driver uses (**proven**).

## Project file `.plcnx2`

**Proven**: a file built by `pxproj.py` opens with 0 errors, compiles, and when the tool saves it back unchanged
the content is identical apart from the items the tool adds by itself (a `Login` HMI page, its settings file).

- A zip. `PROJECT.proj` is a JSON index: every item has `Id`, `Name`, `Type`, `Stream` (path under
  `PROJECT/Content/`), `ParentId`, `Attributes`. `PROJECT/Manifest.manifest`: tamper protection off by default.
- POU = folder `Logical Elements/<Name>.pou` with `Metadata.meta` (kind, ids), `Variables.var` (declarations as
  IEC text), `Code.st` (body as IEC text), and companions (`.usermeta`, descriptions, `.locres`).
- Declarations must be in the tool's own form, `NAME : TYPE := init { EHMI, OPC, CustomGroupReference('<guid>') }
  {Id('<guid>')};` under a first line `{ CustomGroupDefinition('<guid>', '') }`. Without the `Id` a flag shows as
  ticked in the variable table but the HMI build says `The field or variable 'X' does not exist in '<program>'`.
  `pxproj.py` writes this form; sources carry only `{ EHMI, OPC }`.
- `pxproj.py` reads **one declaration per line**. With several on one line (`A : INT; B : INT;`) only the first
  gets its `Id` and flags; the rest of the line is passed on as it stands, without an `Id`, so its flags do not
  work (**seen**). One per line, always.
- `%%ENV:NAME%%` in a source is replaced by `pxproj.py` with the value of the environment variable `NAME` at build
  time; the build stops when it is not set, or when the value holds `'`, `$`, `\` or a line break (`env_tokens`).
  For a password the program itself needs (**proven** with the ClickHouse client of `examples/pump-sequence`).
  The value then stands in clear in the built `.plcnx2`.
- **Program instance names**: `D` is refused at `open` with "Invalid program instance name" (**proven**); `DRV`
  works, and so does `M` in every example. Probably because `D` is a type prefix of IEC literals (guess); avoid
  other one-letter names (`T`) as well.
- Tasks and program instances are stored twice and must agree: `Hardware/CFG_*/PLCnext/EsmConfiguration.esmc`
  (XML) and `Hardware/CFG_*/RES_*/ResourceSettings.set` (IEC text, `TASK ...; PROGRAM <inst> WITH <task> : <type>;`).
  A stale entry in the second gives `SEM1033 Invalid program instance type`.
- Cockpit target: two lines of `ResourceSettings.set`, `CommunicationMetadata` (`UniqueId=TCP/IP` or
  `UniqueId=TcpIp_Simulation`) and the `-ip` in `CommunicationParameters`.
- HMI server settings are `InstVal` lines of the device settings file `Hardware/CFG_*/<id>.ds`:
  `HMI:AccessRights` 2 = PLCnext user management, 0 = none; `HMI:EnableRestIF` True / False.
- Libraries: `References` in `PROJECT.proj`, `{"Path": "%SYSTEMLIBRARIES%/<name>.plcnlx2", "IsReadOnly": true}`.
- Build output: `Documents\PLCnext Engineer\Binaries\<project>@binary\RES_*\` of the Windows user.

- LD/FBD worksheet (**proven**, 2026-11-23: generated sheets compile and run): stream `Code.ld` in the POU folder,
  index entry as for `Code.st` with `Extension` and `Type` `.ld`. XML close to PLCopen TC6: `<body><LD>` with
  `block` (`typeName`, `instanceName` for function blocks, pins as `variable formalParameter=`), `inVariable` /
  `outVariable` (`expression`), `contact` / `coil` (`variable`; `negated="true"`, `storage="set"|"reset"`),
  `leftPowerRail` / `rightPowerRail`. Every object has `localId`, `position` and size in grid units (about 6.9
  pixels at 100 %); pins are 4 apart, the first at y 6 of a block; contact 18 x 4, variable 8 or wider x 4, rail
  3 x 4. A wire is a `connection refLocalId=<source> formalParameter=<source pin>` inside the input's
  `connectionPointIn`, with `position` points from the input back to the source; several connections on one
  input of a contact = OR. Negated block input: `negated="true"` on the `variable`. Function output pin is named
  like the function. The tool takes sizes, points and `executionOrderId` as written and does not declare
  variables: all go into `Variables.var`. The tool has three sheet types: ST, LD/FBD (free) and NOLD (ladder in
  networks, not looked at). By hand in the editor: click the canvas and type a name; double click a pin and type.
- Components > Programming > Local > right click: "Import IEC 61131-10..." exists (not tried).

**Untested**: NOLD worksheets (SFC needs a licence of its own: `sequence-st.md`), data type worksheets, global variables other than ports, the controller as
Modbus TCP server, alarms. Now known (sections below): I/O modules and their process data, ports, the remote
server of the Modbus TCP client, OPC UA visibility and client connections, a Profinet device on the controller
side.

## HMI pages

- Folder `HMI_Server/Application/<Page>.hmi` with `Definition.hmipagedef` (XML), `Variables.hmivar`,
  `Parameters.hmiparams`, `Definition.hmipagedef.locres`; pages are listed in `Navigation.hminav`; the start page
  has the attribute `StartPage` in the index (**proven**).
- A program variable is `<instance>.<variable>` in expressions (`M.TE1`) and
  `<Name>M</Name><Suffix>.TE1</Suffix>` in actions and symbol parameters (**proven**). It needs the EHMI flag.
- **Proven** elements: `HmiText` with `TextDynamic` (`Format="fixed1"`), `Rectangle` with `FillDynamic`
  (thresholds) and `ScaleDynamic`, `Ellipse`, `Line`, `Button` with `WriteValueAction` and
  `IncrementValueAction`, `SymbolInstance` with `ParameterBindingVariable`.
- `VisibilityDynamic ChangeWhen="True"` hides the object while the expression is true. `pxhmi.py` writes
  `ChangeWhen="False"`, so `visible=` means what it says (**proven**).
- The HMI data list (HMI tags) is not needed for program variables (**proven**); it maps tags to global
  variables.
- Where the element XML came from: the tool's templates (`Templates/*.plcntx2`) and libraries
  (`DefaultLibraries/HMI Standard.plcnlx2`, `Libraries/Symbols-Schematic.plcnlx2`, `Symbols-Chroma.plcnlx2`).
  They are zips of the same format; look there for an element that `pxhmi.py` does not have yet.
- With user management on, the tool adds a `Login` page by itself and the browser asks for the controller's
  user. With `hmi_server.login: false` the page opens directly (**proven**).
- Page address: `https://<controller>/ehmi/hmiapp.html` (**proven**). Self-signed certificate.
- `IncrementValueAction` with a step of 0.5 on a REAL is refused: "Invalid step value" (**proven**; 0.1 gives a
  warning and a button that does nothing). Keep such a value as an INT x 10 and step it by 5.
- The page's REST interface (`hmi_server.rest`, login off) reads **and writes** program variables flagged
  `{ EHMI }` without a session: `pxe.sh set M.SQ_CMD=1` is a `PUT /_pxc_api/api/variables` (**proven**: the 41
  checks of `examples/pump-sequence/test_seq.sh` drive both controllers this way). So with login off, anyone who
  reaches the controller can read and change every page variable: never put a secret in one.

## The tool, driven

- Start takes about 2.5 minutes; opening a project about 30 s; background compile a few seconds more. The error
  count is in the status bar (`N errors, M warnings`) and the messages in MESSAGES > Error List (**proven**).
- File > Open while another project is open asks "save the current project?" only if that project changed.
  Engineer marks a freshly opened generated project as changed when it adds its `Login` page (**seen**).
- Cockpit: PLANT > controller (double click) > Cockpit. The Cockpit tab is a toggle: a second click closes the
  editor (**proven**, cost an hour).
- Buttons must be clicked with the mouse. UI Automation "invoke" on Connect only flips its look (**proven**).
- Connect asks for user and password once per Engineer session; with "Remember credentials" the dialog comes
  filled and only needs OK. Later connects in the same session ask nothing (**proven**).
- Write and Start downloads and restarts the controller's runtime. Engineer usually loses the connection then
  ("Connection lost" in the Online Log); the project is running all the same. Reconnect and read the project
  name in the Cockpit (**proven**; `pxe.sh write` does this).
- The controller in the project must match the firmware, else `MSG_ONL0156 Connection failed ... does not match
  the configured controller` (**proven**).
- After a change of screen resolution the Engineer window keeps its old size until it is restored and
  maximized again (`scripts/win/maximize.ps1`) (**proven**).
- A browser or any other window on top of Engineer takes the clicks. `pxe.sh` closes the browser first.
- Debug view: connected and "Debug On" pressed (`AID_Debug On / Off`), a double click on the program instance in
  PLANT (on its label, not elsewhere in the row) opens code and variable table with online values. Without debug
  mode the double click does nothing (**proven**; `pxe.sh show`).
- A Write and Start click right after the login can be lost: connected, project name on the controller empty,
  RUN off. Clicking again works (**seen** twice; `pxe.sh write` presses again after 25 s).

## Base project

A base project is an empty project for one controller type and firmware. It is Phoenix Contact's data, so it is
made on the user's machine and is not in this repository.

By hand, once per controller type and firmware (**proven**):

1. In Engineer's start page double click the controller (e.g. "AXC F 2152 v00 / 2026.0.0").
2. If the controller's firmware differs: COMPONENTS > search the type > select the entry of the right firmware
   (`AXC F 2152 Rev. >= 00/2025.6.0`) > right click > Copy; PLANT > select the controller > right click > Replace.
3. File > Save As, any name.
4. `python3 scripts/pxproj.py --strip <saved file> ~/.plcnext-engineer/base/<TYPE>-<FW>.plcnx2`

## Controller (AXC F 2152)

Worked out on firmware 2025.6.0; the same was seen on 2026.0.2 unless a line says otherwise.

- Factory address `192.168.1.10/24`, static, no DHCP (**proven**). User `admin`, password printed on the housing.
- Open ports: 22 (SSH), 80 / 443 (WBM, eHMI), 41100 (Engineer), 4840 (OPC UA) (**proven**).
- `admin` has a short sudo list: `date`, `reboot`, `passwd`, `nft`, `dpkg`, and start / stop of `plcnext`, `sshd`,
  `firewall`, `chronyd`. `root` is locked from the factory (**proven**).
- Factory reset from the Cockpit ("Reset to Factory Defaults", one confirmation): back after about 90 s, removes
  everything added to the device, firmware stays (**proven**).
- CPU load with a small program and one HMI page: about 26 % (**proven**).
- Simulation (**proven** 2026-11-23 with the free AXC F 1152, simulation package 2026.0.2, district heating
  example: write, operator page, REST read, button): a separate installer ("PLCnext Engineer Simulation", from
  the PLCnext Engineer product page), QEMU emulating the ARM controller. AXC F 1152 is free; 2152 / 3152 need the
  add-in licence. Restart Windows after installing it: before that Connect does nothing, without a message.
  - Base project: start page > "AXC F 1152 v00 / 2026.0.0"; the new project is already a file,
    `%APPDATA%\PHOENIX CONTACT\PLCnext Engineer\2026.6\NEW\PROJECT1.plcnx2`; `pxproj.py --strip` it.
  - `"target": {"simulation": true}`. The PLANT node is then `Simulation : AXC F 1152`: run the driver with
    `PXE_CONTROLLER='AID_Project_Simulation : AXC F 1152'` and `PLC_HOST=192.168.1.2`.
  - The first Connect starts the emulator; in a VM it needed 5 to 6 minutes, and 14 once (8 vCPUs, Windows' virtualisation-based security off: the emulator is pure software, it needs no hypervisor feature of Windows) (progress box stays at 40 %), then a
    certificate warning (OK) and the login: `admin` / `plcnext`, the vendor's published default for the
    simulation, typed once with "Remember credentials". `pxe.sh write` gives up before that: connect by hand
    the first time (`uia 'click AID_Connect / Disconnect'`, wait, OK, login), then `write`.
  - After the first write the program was loaded but stopped (values 0): `pxe.sh coldstart`.
  - Network: the emulator sits on a TAP adapter `PLCnextSimTAP`, host 192.168.1.250, controller 192.168.1.2;
    page `https://192.168.1.2/ehmi/hmiapp.html`, REST the same host. That is the 192.168.1.0/24 of the factory
    default controller address: on a machine that is also on such a network Windows has two routes to it (here
    it still worked, the real controller at .10 and the simulation at .2 side by side).
  - It stays up until Engineer or the project is closed; it does not keep the project (starts from a snapshot).
  - The image's own start file uses user networking with ports 5555 / 5050 / 41100 on localhost; started that way
    by hand the web server answers but Engineer does not connect over TCP/IP. Not a way in.
  - No field bus, no I/O, not real time. CPU load 2 to 8 % with the example.

- Two controllers on one address (every new one comes up at 192.168.1.10): both answer, in turn. On the Engineer
  machine pin the address to one of them by MAC and talk to that one: `New-NetNeighbor -InterfaceIndex <if>
  -IPAddress 192.168.1.10 -LinkLayerAddress <mac> -State Permanent -PolicyStore ActiveStore` (**proven**).
- Firmware 2026.0: the address is in `/etc/systemd/network/79-if-1.network` (`Address=`), writable by admin;
  takes effect at the next boot (`sudo /sbin/reboot`). A live change with `sudo ifconfig` did not work from a
  script. `79-if-2.network` is the interface of an AXC F XT ETH 1TX module (`enp1s0`) (**seen**).
- `scripts/plc-backup.sh` does all of the following in one command each (**proven** 2026-11-24 on firmware 2026.0.2: backup
  3 MB, 48 project files, checksum equal to the controller's; restore of that archive onto the same controller,
  runtime back with the program running).
- Backup and restore of a controller's project (**proven** 2026-11-23: project of one AXC F 2152 backed up, put
  on a second one with the same firmware, checksum of the folder equal, runtime loads it, `projectCRC` equal,
  state Running, operator page served):
  - Backup: `plc-ssh.sh --out <file on the Engineer machine> 'cd / && tar czf - --exclude=opt/plcnext/logs opt/plcnext
    etc/plcnext etc/systemd/network'` (3 MB). Through the normal paths. **Not** from the overlay's storage
    `/media/rfs/rw/upperdir`: read there, 32 of 75 project files came out with length 0, without any error.
    The restore test found it: the runtime logs `Project integrity check: Hash value of file ... is not
    correct` and the REST interface says `project unloaded`.
  - Check a backup: `find . -type f -exec md5sum {} + | sort -k2 | md5sum` in `projects/PCWE` on the controller
    and on the restored copy must agree; count the files of length 0.
  - Restore: `plc-ssh.sh --in <file on the Engineer machine> 'cat > /tmp/b.tgz; ...'`, extract `opt/plcnext/projects/PCWE`,
    move the present `PCWE` aside, put the new one in place (`chmod -R g+w`), `sudo systemctl restart plcnext`
    in the foreground (a minute). `projects/current` is a link to `PCWE`.
  - Same firmware on both sides: a project compiled for 2026.0 does not load on 2025.6.
  - As admin about 10 entries cannot be read (keys, user database). The firmware is not in it: note the version
    (`cat /etc/plcnext/arpversion`). The web interface has its own Backup & restore page (System), not tried.
  - The project on a controller is compiled (`Plc/Eclr/eCLR.img`): type and variable names can be read out of
    it, the source cannot. `sudo` also lists `recover-plcnext` / `recover-axcf2152`: the factory reset, never.
- Firmware update: file `axcf2152-<version>.raucb` (inside the zip from the product page). Any firmware from
  2022.0 takes a 2026.0 file directly (change notes). Admin has no update command in `sudo -l` (2025.6); the
  web interface does it (Administration, software update: upload through `/arp_api/upload/`, then a service
  call). `su` to root from a script hangs ("must be run from a terminal", and with a forced terminal no answer).
  Not scripted: done by hand in the web interface (System > Update: "Prepare and stop" first, only then the
  file can be selected, then "Start update"; 2025.6.0 to 2026.0.2 took six minutes, address and login kept).
- Time (firmware 2026.0.2): chrony runs but has no source (`local stratum 10`) (**proven**). `/etc/chrony.conf`
  is writable by admin: add `server <ip> iburst` lines, `sudo systemctl restart chronyd`, check with `chronyc -n
  sources`. A controller with a second interface can serve the others (`allow <subnet>` in its own file). A
  controller with a static address has no DNS: give servers as addresses. `hwclock` is not available to admin.
  A step of 1.5 years did not disturb the running program (**seen**).

- Serial: the AXC F 2152 itself has none. Module AXL F RS UNI 1H (2688666), data sheet 8533_en_04 (**read**, not
  yet used): RS-485 two-wire on connector 2, data + on terminal 10 (or 20), data - on 11 (or 21); 00 / 01
  (TxD) are not used in RS-485. Module at the end of the bus: bridge 20-30 and 21-31 (built-in termination, also
  polarises the line). Shield to a busbar before the module; no ground terminal for RS-485 (33 is the RS-232
  ground). Protocols: transparent, end-to-end, XON/XOFF, Modbus/RTU master (no slave); 1 or 2 stop bits; baud
  rate, data width, parity and protocol are startup parameters of the module. Connector 1 only passes 24 V on.

## I/O modules (proven 2026-11-23: AXL F RS UNI 1H on an AXC F 2152, firmware 2026.0.2)

- A module is a folder `Hardware/CFG_*/AXLF_Master/<TYPE>/<uuid>.ds` (its parameters as `InstVal` lines), about
  1500 lines of `DataList.dl` (one `Datum` per process data item) and entries in `PROJECT.proj`. Not generated:
  made once in the tool and kept in the base project. By hand: PLANT > Axioline F > Device List, double click
  the first row, type part of the name, pick the entry; then the module's Parameters; Ctrl+S (a new project
  asks for a file name).
- RS UNI parameters in the `.ds`: `p80_0_0` protocol (`0011` Modbus/RTU, `0000` transparent), `p80_0_4`
  interface (`01` RS-485, `11` off), `p80_1_0` data width (`0100` 8N1, `0010` 8E1), `p80_1_4` baud rate (`1001`
  19200, `0111` 9600).
- A port is a program variable with usage IN Port / OUT Port. In the program's `Variables.var` it stands in a
  `VAR_GLOBAL ... END_VAR` block with the flag `InputPort` / `OutputPort`. In a plain `VAR` block the flag
  compiles but the tool shows usage Local and offers the variable nowhere. Each port of each instance also has a
  line in `Hardware/CFG_*/RES_*/GlobalVariables.var` (`VAR_CONFIG`, `M.NAME : TYPE { OutputPort, ...,
  ProgramGlobal } {Id('...')}`) and a `Datum` in `DataList.dl` with a `Role TypeName="OutPort"` whose `ObjectId`
  is that Id and whose `SourceId` is `<PlcIdentifier>.L7_2`. `pxproj.py` writes all three from `{ InputPort }` /
  `{ OutputPort }` in the sources.
- A connection port to process data = both `Role` elements in one `Datum`. By hand: GDS Port List of the module,
  the empty cell beside the item, type the port's name, pick `Arp.Plc.Eclr / M : NAME`.
- RS UNI process data (data sheet 8533_en_04): 20 bytes each way. Out: byte 0 command (`10` transmit, `30` read
  characters, `50` / `70` the same with the toggle bit, for repeating), byte 1 control bits (`06` resets
  transmit and receive error), byte 2 length, bytes 3 to 19 characters. In: byte 0 echo of the command (bit 7 =
  error), byte 1 status (bit 0 receive buffer not empty, bit 1 receive error, bit 2 transmit error = no answer
  in 2.5 s), byte 2 length (bit 7 = more to read), then the characters. Items: `Control Word High Byte` = byte
  0, `Control Word Low Byte` = byte 1, `TxCHAR01` = byte 2 (length), `TxCHAR02`.. the characters; the same with
  `Status Word ...` and `RxCHAR..`. In Modbus/RTU mode the module adds and checks the CRC.
- No bit cast from DWORD to REAL was found; `FB_IEEE` in the example computes it.
- The Modbus RTU room sensor stopped answering once while the network was being changed and came back by itself,
  with nothing done to it (**seen** once, 2026-11-24; cause unclear). The program needs no restart for it: the
  next poll that gets an answer sets `COMM_OK` again.

## Modbus TCP client (proven 2026-11-23: AXC F 2152, firmware 2026.0.2, one remote server, read)

How to use it: `modbus-tcp.md`. The file side:

- Library `Modbus.pcwlx` in the tool's `Libraries` folder; `PROJECT.proj` References gets
  `%SYSTEMLIBRARIES%/Modbus.pcwlx`. `PlmConfiguration.plmc` gets `<ComponentInstance name="Arp.Io.MbC"
  libraryName="Arp.Io.Mb" componentType="Arp.Io.Mb.ControllerComponent">`.
- The client is a folder `Hardware/CFG_*/ModbusTCP_Client/` with `Arp.Io.MbC.acf.config`, `<...>.L7_MOD.pces` and
  `<...>.station`. Per server a folder `Generic_Modbus_TCP_Server/` with `<id>.ds` (`InstVal` lines
  `ModbusTCP:UnitID`, `ModbusTCP:PortNo`, `IP:IpAddress`, `ModbusTCP:SwapBytes`, the timeouts,
  `ModbusTCP:TriggerRate`) and `<id>.mbreg`, JSON: `{"Registers":[{"Id","FunctionCode":4,"Name","DataType":"Word","UnitId":1,"DataItems":
  [{"Id","DataDirection":"Input","Name":"input","Address":0,"Number":1}]}]}`. Not generated: made once in the tool
  and kept in the base project; `pxproj.py` rewrites the registers and the three settings.
- `DataList.dl` gets two `Datum` per register: one with a `Role TypeName="ProcessDatum"` (`ObjectId` = the data
  item's `Id`, `SourceId` = the server's id, `DataType` `Bitstring16`, `Label` `<name>_input`, `Offset` the running
  byte offset, `ObjectIndex` counting), and one with a `Role TypeName="OutPort"` (`ComponentInstance` and `Program`
  `Arp.Io.MbC`, `PortDataTypeDomain` `Fdcml`, `Index` = `Offset`). A connection to a program port is the program's
  `InPort` role inside that second `Datum`.
- The status items of a server (`STATE`, `OFFLINE_CNT`, ...) are in the base project's data list already,
  `Unsigned32`: a UDINT port connects to them by label.
- A deleted server stays in `PROJECT/Content/RecycleBin/` (**seen**). `pxproj.py` skips that folder.
- The tool saves an empty task list as `<Tasks />` (**seen** in a base made this way); `pxproj.py` takes both forms.
- `target.ip` sets the controller's own address in the project too (`IP:IpAddress` of `L34_1` in the controller's
  `.ds`), not only the Cockpit's.
- **Service switch**: WBM > System Services > "Modbus Client TCP". On file it is the line `<Feature id="MODBUS
  CLIENT TCP" enable="true"/>` in `/opt/plcnext/config/System/Scm/Default.scm.config`, writable by admin over SSH;
  `sudo systemctl restart plcnext` afterwards. The same file holds `OPCUA CLIENT`.
- Compile warning `TCPP0007` ("The IP address ... lies below the network's start address") for a server outside
  the project's IP range: harmless, the read works over a route of the controller's Linux.

## OPC UA (proven 2026-11-23: two AXC F 2152, firmware 2026.0.2, server on one, configured client on the other)

How to use it: `opcua.md`. The file and controller side:

- **Server visibility**: in the controller's `.ds`, `Para[@uID='opcuaGdsPortsToProvideType']/Current` =
  `OpcUAConfigurationDocument.GdsPortsToProvide.None | Flagged | All` (Engineer: PLANT > OPC UA > Server Settings
  > Basic settings, "Visibility of variables"). Every base project and template has `None`; `pxproj.py` sets it
  from `"opcua": {"visibility": ...}`.
- Node id of a program variable: namespace `http://phoenixcontact.com/OpcUA/PLCnext/GlobalDataSpace/`, identifier
  `s=Arp.Plc.Eclr/<instance>.<VARIABLE>`.
- The server takes no anonymous client and offers only signed and encrypted policies (Basic256Sha256,
  Aes128Sha256RsaOaep, Aes256Sha256RsaPss). With an empty trust store it accepts any client certificate (**seen**).
- **Client connections** in the project: `Hardware/CFG_*/OPCUA/<id>.L7_5.opcuaclicon`, empty in the bases. Form:
  `<ClientConnectionsConfiguration xmlns="http://phoenixcontact.com/OpcUA/PLCnext/GlobalDataSpace/">` with per
  group `<VariableGroup GroupType="Subscribe|Write" CycleTime="500">` and per variable `<VariableMapping>
  <LocalVariable Identifier="Arp.Plc.Eclr/M.A_TEMP" /><RemoteVariable Identifier="s=Arp.Plc.Eclr/M.TEMP"
  ShortName="" Namespace="<same namespace>" ServerName="PLC_A" /></VariableMapping>`, and per server
  `<Connection Name="PLC_A" ServerUrl="opc.tcp://192.168.1.10:4840" SecurityMode="SignAndEncrypt"
  SecurityPolicy="BestAvailable" UserName=".." Password=".." ServerIndex="1" />`. The password stands there in
  clear.
- Compiled on the controller: `projects/PCWE/Services/OpcUA/Modules/Client/Configs/clientconnections.xml`, an
  `eUAClientConfigurationDocument` (`NamespaceArray`, `ServerConnections` with endpoint URL, `SecurityMode`
  `SignAndEncrypt_3`, `UserTokenType` `UserName_1`, `UserName`, `Password` in clear again; `VariableGroups` with
  `GroupType` `Subscribe_0` / `Write_1`, `CycleTime`, node mappings `ns=1;s=Arp.Plc.Eclr/<instance>.<NAME>`).
  The same form in `projects/Default/Services/OpcUA/Modules/Client/Configs/` is read too: that is where
  `plc-opcua-client.sh` puts it, so the password never stands in a project file (**proven**).
- **Certificate checks** of the client, `InstVal` lines in the controller's `.ds`:
  `opcuaClientModuleSessionSecurityDefinitionEnabled` (True to apply the three below),
  `opcuaClientModuleApplicationAuthentication`, `opcuaClientModuleApplicationUriCheck`,
  `opcuaClientModuleCertificateHostnameCheck` (False each = take any server certificate). The log then says
  "Overriding default element value" (**proven**).
- **Service switch**: `<Feature id="OPCUA CLIENT" enable="true"/>` in
  `/opt/plcnext/config/System/Scm/Default.scm.config` (= WBM > System Services > "OPC UA Client"), then
  `sudo systemctl restart plcnext`.
- **Licence**: without the "OPC UA Client License" the log says `LicenseCheckFailed`, then `LicenseTrialStarted`;
  the client runs 4 hours counted from the start of the runtime. A project write (Write and Start) does **not**
  start them again: trial started 21:41, a write at 21:54, the client stopped at 01:41:39 with
  `ConnectionStatusChanged ... ServerState='Disconnected'`, `DisconnectPassed`, `License WARN -
  LicenseTrialStopped - Done stopping trial period` (**proven**). Then the mapped variables keep their last values
  on both sides, with nothing in the program to show it. Only `sudo systemctl restart plcnext` (or a reboot)
  starts another 4 hours.
- **Log**: `/opt/plcnext/logs/Arp.log`, logger `Arp.Services.Modules.OpcUAServer.Client.Internal.RemoteSession`;
  `grep -a`, the file has binary bytes. Lines in `opcua.md`, "Diagnosis". No status variable of the client found.
- No OPC UA client function blocks in Engineer's libraries (checked: only status enums).
- **Users** through the web interface's own calls (**seen to work**, firmware 2026.0.2, undocumented): OAuth code
  flow with PKCE at `/_auth_api/authorize`, `/_auth_api/login`, `/_auth_api/token`, then with the Bearer token
  `POST /arp_internal_rsc/jrpc/Arp/Arp/System/Um/Services/Internal/IUserManagementService/AddUser`
  `{"username","password"}` and `SetUserRoles` `{"username","roles":["DataChanger"]}`.

## Profinet (proven 2026-11-24: two AXC F 2152, firmware 2026.0.2, one controller and one device)

How to use it: `profinet.md`. The file and controller side:

- **Device side**: nothing in the project's hardware. The firmware's Profinet device function is on by default;
  the program declares the system variables `PND_S1_INPUTS`, `PND_S1_OUTPUTS` (`PND_IO_512`, 512 bytes) and
  `PND_S1_VALID_DATA_CYCLE` (BOOL) in a `VAR_EXTERNAL` block of its `Variables.var` (**proven**). Also in the
  data list: `PND_S1_PLC_RUN`, `PND_S1_OUTPUT_STATUS_GOOD`, `PND_S1_INPUT_STATUS_GOOD`, `PND_S1_DATA_LENGTH`,
  `PND_IO_DRIVEN_BY_PLC` (**seen**, untested).
- **Controller side**: a folder `Hardware/CFG_*/PN_Master/` with `Arp.Io.PnC.acf.config` and `.station` files;
  per device `AXC_F_2152/<id>.ds` (and `<id>_PN_Device.station`), `DAP/` (Interface, Port_1, Port_2) and
  `IO_512/IO_512/<id>.ds` for the module (**seen**). The device's IP address and name of station are `InstVal`
  lines in its `.ds`. Not generated: made once in the tool and kept in the base project.
- The module "IO 512" has two data items, `DI4096` (from the device) and `DQ4096` (to the device), Octetstring[512].
  A program port of type `PND_IO_512` connects to each like any port (`io`) (**proven**).
- Default update time 8 ms gives warning `PNIO0112` ("cannot be updated cyclically faster than a value of 16
  ms"): the interface's "Reduction ratio" 16 or more; 32 used (**proven**).
- **Name of station**: `target.station` writes `IP:DnsName` and `IP:ExtendedDomainName` (`[UTF-8;<hex>]`) of
  `L34_1` in the controller's `.ds`; the PLANT node is then labelled `<station> : AXC F 2152` (**proven**). It
  does **not** name the controller on the network: written that way, both controllers answered a scan as
  `axcf2152-lan1` (the firmware default), the controller's BF-C lamp was red and nothing was exchanged
  (**proven**). Assigned from Engineer (PLANT > Profinet > Online Devices, scan, "Name of station (Online)",
  pick by MAC address) it took at once and the exchange started within seconds (**proven**). Kept across a
  restart of the device: untested.
- **Address**: the controller sets the device's IP address from its project by DCP when the connection starts
  (**seen**, with the address the device already had). A different one: untested.
- Profinet RT and Modbus TCP, OPC UA and the operator page share the same Ethernet interface (**seen**).
- `pxe.sh` finds the controller's own PLANT node by itself (its label follows the station name);
  `PXE_CONTROLLER` is only needed to pick one of several. `pxproj.py --strip` also drops the ports of the
  programs of a project it built (data list roles and `VAR_CONFIG`), so a built project can be stripped to a base.
- **Several devices** (2026-11-24, B and a SCALANCE XC216): each device's DAP items (`PN_AR_VALID`, ...) are
  `OutPort` roles in `DataList.dl` with the same `<Name>`, told apart only by `SourceId` = the uuid of a `.ds`
  under that device's folder in `PN_Master/`; the device's `.ds` holds its name of station as `IP:DnsName`.
  `io` takes `"<station>/<item>"` for that (**proven**: ports of both devices linked, values live). Submodule
  Node IDs (for `RDREC`) are `PN:NodeID` in the submodule's `.ds`. Diagnosis items and records: `profinet.md`,
  "Diagnosis on the controller".
- After a `write` the program was sometimes left loaded but stopped (seen 5 times on 2026-11-24, firmware
  2026.0.2: runtime log `Plc state transition from 'Ready|Loading' to 'Stop|Warm'`, RUN lamp blinking, counters at
  0, REST values frozen) although `write: ok`. `pxe.sh coldstart` did not reach it once (Engineer had lost the
  connection); `sudo systemctl restart plcnext` started it every time. `pxe.sh write` now reads the last state
  change from the runtime log and, when it is a stop, restarts the runtime once (`program: running after the
  restart`; `PXE_AUTOSTART=0` only reports). The check needs `plc-ssh.sh` (password); without it the result is
  "state unknown". The restart path itself has not yet been exercised by the script (the normal path, **proven**).

## Structured Text (proven 2026-11-23 on a controller: the MQTT subscriber blocks)

- `ARRAY[0..n] OF BYTE` declared inline, as `VAR`, `VAR_OUTPUT` and `VAR_IN_OUT`; arrays of 4 kB in a block's
  `VAR`. The output array of one block passed to the `VAR_IN_OUT` of another: `JT(BUF := MQ.PAYLOAD, ...)`.
- `STRING`, `STRING[120]`; `LEN`, `MID`, `FIND`. `WHILE`, `FOR`, `CASE`. `UDINT`, `DINT`, `WORD`, `DWORD`,
  `TO_BYTE`, `TO_INT`, `TO_DINT`, `TO_UDINT`, `TO_REAL`, `TO_DWORD`, `SHL`, `SHR`.
- A string literal must not contain a backslash, and `$` starts an escape: "String literal contains Invalid
  escape characters".
- No direct character-to-byte conversion was found. The blocks look the character up with `FIND` in a table
  string of the characters 40..126 (no quote, no dollar, backslash replaced); position + 39 is the code.
- A variable named like a function or POU gives a warning, "named like a POU" (**proven**: `NEG`, `RS`). A variable
  named `LEN` clashes with the function `LEN` (**proven**): rename it.
- A string literal cannot hold everything JSON or HTTP needs (no `$`, no backslash, no line break).
  `FB_TXT` of `examples/clickhouse-log` writes text into a byte buffer with stand-ins: `` ` `` for `"`, `@` for `'`,
  `^` for CR LF, `|` for LF; characters missing from its table (below 40, the quotes) become spaces (**proven**:
  HTTP requests and JSON rows accepted by a ClickHouse server, `clickhouse.md`).
- Socket blocks `TCP_SOCKET`, `TCP_SEND`, `TCP_RECEIVE` of the "PLCnext Controller" library, referenced by every
  project: a plain TCP client works with them (`mqtt-subscribe.md`). `TLS_SOCKET_2` and relatives exist
  (**untested**).

## Transport

`scripts/vm.sh` reaches the machine that runs Engineer; everything else goes through its verbs (`ps`, `ui`,
`pipe`, `put`, `get`, `shot`, `gui`, `uia`). Which transport: `PXE_TRANSPORT` (`scripts/config.sh`), `local` by
default in Git Bash on Windows, `proxmox` elsewhere.

- **local**: the scripts run on the Engineer machine itself, in Git Bash (Git for Windows, Python 3). PowerShell
  is started directly with `powershell.exe`, files are copied, paths converted with `cygpath`. `ps` and `ui` are
  the same thing here: the scripts already run in the user's desktop session. **Proven** 2026-11-24 on Windows
  11, Git for Windows 2.47 (portable), Python 3.12 (embeddable): `check`, `build`, `open`, `errors`, `write`,
  `state`, `read`, `wait`, `hmi`, `tap`, `show`, `shot`, and the stdin pipe that carries passwords. Not run
  there: `plc-ssh.sh` with a real password, `pxe-login.sh`, `plc-opcua-client.sh`, `mqtt`, `fuxa`, `timer`. Seen
  on the way: `python3` on Windows can be the Store's stub (the scripts look for one that runs); PowerShell
  prints numbers with the system's thousands separator (the helpers print plain digits); a file Python writes has
  CR LF.
- **proxmox**: the Engineer machine is a Windows VM on a Proxmox host, reached through the qemu guest agent (root
  ssh by key to the host, `qm guest exec`); no password, no remote desktop (**proven**: the whole skill was worked
  out this way).
  - `ps` runs as SYSTEM, `ui` in the logged-on user's desktop session through a scheduled task that is hidden
    behind `wscript` (a visible console steals the focus and sits on top of what gets clicked).
  - The guest agent drops outputs above a few hundred kB: files are read in 240 kB pieces.
  - One `ui` round trip costs about 8 s. Put several `uia` commands into one call.
  - A command that does not end by itself blocks the next one (`mosquitto_sub.exe -W` does not end under the
    guest agent; `-C <n>` does).
  - The guest agent can be away for a while without the VM being down (**seen**: minutes after a boot, and at
    odd moments under load): `vm.sh` asks again for a minute, then says `vm.sh: the Engineer machine does not
    answer`. A command the agent never took was not run, so asking again is safe.
  - A VM that really hangs (**seen**: no answer for minutes while the host calls it running): reset it from the
    host (`qm reset <id>`), wait for the desktop session, `pxe.sh start`. What was open in Engineer is lost; the
    controller is not affected and keeps running its program. A Windows clock that stands still is not proof:
    the clock of a VM that worked on was seen 25 minutes behind.

## MQTT from the controller (works, 2026-11-23): firmware client -> Mosquitto -> FUXA

The firmware (2024.0 and later, here 2025.6.0) has an MQTT client inside its Proficloud service. No store app, no
library, no licence. It only publishes (no subscribe), QoS 0, one broker.

- **What is published: OUT ports of a program that carry the Proficloud flag.** In the declaration text:
  `TE1 : REAL { OutputPort, PROFICLOUD };` inside the program's `VAR` block (**proven**). `VAR_OUTPUT` in a program
  is an error ("'VAR_OUTPUT' is not supported for programs."), `{ OutPort }` is an error ("The pragma with the
  name 'OUTPORT' cannot be found."). `InputPort` exists by the same token (untested).
- **Payload** (**proven**): all flagged ports in one JSON message on one topic, once a second:
  `{"MessageId":"...","MessageType":"ua-data","Messages":[{"MessageType":"ua-keyframe","Payload":{"MQ_P2_ON":1,"MQ_TE1":57.50},"Timestamp":"2026-11-23T06:38:44.522Z"}]}`.
  Keys are the bare port names (no instance name), BOOL comes as 1/0, REAL with full float digits.
- **Broker settings** live in `/opt/plcnext/projects/Default/Services/ProfiCloudV3/ProfiCloudV3.config` (owner
  admin, writable over SSH). The WBM page Configuration > Proficloud writes the same values. On the `<ProfiCloud>`
  element: `enabled="true" location="Mqtt" anycloudTls="false" anycloudHost="<broker ip>" anycloudPort="1883"
  anycloudPath="" anycloudClientId="<id>" anycloudUsername="" anycloudPassword="" anycloudMqttTopic="<topic>"`,
  and `<TimeSeriesData enabled="true" ...>` (`intervalMilliseconds`, `samplingRateMilliseconds`, default 1000).
  `location` is what selects the own broker (`GermanyFrankfurt` and `ChinaShanghai` are Proficloud); a wrong value
  is ignored without a log line. Names read from the firmware (`libArp.Services.ProfiCloudV3.so`) and the WBM
  plugin, the file form **proven** by the running connection. Keep the factory file (`...config.factory` here).
- **The file is read at start only.** admin may not restart the runtime (`/etc/init.d/plcnext` is not in its sudo
  list) but may `sudo /sbin/reboot`: 2.5 minutes. `Arp.log` then says "Starting to collect and publish time series
  data." and "Successfully subscribed to all Proficloud OUT-Ports."; it says **nothing** about the broker
  connection, failed or not. Trust the broker log.
- **If the broker is not reachable at start the client does not come back by itself** (seen: 10 minutes without an
  attempt after the path was opened; a reboot connected at once).
- **Broker as it was set up**: Mosquitto 2.0.22 on the Engineer machine (service `mosquitto`, listeners
  `127.0.0.1:1883` and the machine's address on the controller's network, port 1883, anonymous, log
  `C:\agentwork\mqtt\log\mosquitto.log`), a Windows firewall rule for TCP 1883 from the controller's address only.
  With the Engineer machine in a VM, the hypervisor's firewall for that VM needs the same opening: with an inbound
  policy of DROP the connection showed as a time-out from the controller and nothing in the Windows firewall log.
- A variable can be operator page variable and port at once: `{ EHMI, OPC, OutputPort, PROFICLOUD }` (**proven**,
  16 variables; REST read and the eHMI page work as before). Newly flagged ports are published after a plain
  `write`, without a reboot (**proven**).
- **One topic per value** for viewers that cannot look inside the message (FUXA's `json` tag type reads top-level
  keys only): `scripts/win/mqtt-flatten.js` beside the broker republishes `<topic>/<NAME>`, retained, 3 decimals.
  Here it was started at boot, log `C:\agentwork\mqtt\log\flatten.log`.
- **FUXA 1.3.5** on the Engineer machine: Node.js 22 in `C:\agentwork\node`, `npm install @frangoteam/fuxa@1.3.5` in
  `C:\agentwork\fuxa\app`, data `C:\agentwork\fuxa\data`, started at boot, `uiHost: "127.0.0.1"`
  in `data\_appdata\settings.js`, page `http://127.0.0.1:1881/`. Project in with `POST /api/project`
  (`pxe.sh fuxa`), generator `scripts/pxfuxa.py` (**proven**: 16 live values and lamps).
- **Subscribing** is not in the firmware client: a client in Structured Text does it, `mqtt-subscribe.md`
  (**proven**).
- Do not edit `pxe.sh` while one of its commands runs: bash reads the file as it goes ("bar: command not found").
- Ctrl+O does nothing on Engineer's start page (no project open); the Open button of the toolbar does.
