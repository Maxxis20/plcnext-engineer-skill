# OPC UA between two PLCnext controllers

Proven 2026-11-23 on two AXC F 2152 (firmware 2026.0.2) with PLCnext Engineer 2026.6: controller B read four values
of controller A every 500 ms and wrote two REALs and a counting INT into A; both sides seen over REST and on A's
operator page. A runs the firmware's OPC UA server, B the firmware's configured OPC UA client. Nothing of the
protocol is programmed. Example: `examples/opcua-pair` (controller A 192.168.1.10, controller B 192.168.1.11).

## What it takes

- Both controllers on one network (or a route between them). The server listens on port 4840.
- A **user on the server controller** for the client. No anonymous access: every client logs in.
- On the client controller: the service **"OPC UA Client"** switched on, and for a plant the vendor's **"OPC UA
  Client License"** (store). Without it the client runs 4 hours from the start of the runtime (below).
- The server's variables flagged `{ OPC }` and the server set to show flagged variables.
- No library, no function block: Engineer's libraries have no OPC UA client blocks (checked: only status enums).

## Server side (controller A)

- Every controller runs an OPC UA server on port 4840. A program variable shows there when it carries `{ OPC }`
  **and** the project's server setting "Visibility of variables" (PLANT > OPC UA > Server Settings > Basic
  settings) is "Marked" (or "All"). Every base project and template comes with **"None"**: the flag alone shows
  nothing. `program.json`: `"opcua": {"visibility": "marked"}` (`"all"`, `"none"`).
- Node id of a program variable: namespace `http://phoenixcontact.com/OpcUA/PLCnext/GlobalDataSpace/`,
  identifier `s=Arp.Plc.Eclr/<instance>.<VARIABLE>` (`s=Arp.Plc.Eclr/M.TEMP`).
- **Users.** Add one in A's web interface: Security > User Authentication > "Add User", with a role. DataViewer
  reads, DataChanger also writes (read in the vendor's documentation; a DataChanger user was used). By hand is
  the documented way. **Seen to work** on firmware 2026.0.2, undocumented: the web interface's own calls, an
  OAuth code flow with PKCE (`/_auth_api/authorize`, `/_auth_api/login`, `/_auth_api/token`), then with the
  Bearer token `POST /arp_internal_rsc/jrpc/Arp/Arp/System/Um/Services/Internal/IUserManagementService/AddUser`
  `{"username", "password"}` and `.../SetUserRoles` `{"username", "roles": ["DataChanger"]}`. Not in this skill's
  scripts; it may change with any firmware.
- **Security policies** offered by the server: only signed and encrypted ones (Basic256Sha256,
  Aes128Sha256RsaOaep, Aes256Sha256RsaPss), no "None". With an empty trust store the server accepts any client
  certificate (**seen**).

## Client side (controller B)

The firmware's client copies variables between this controller and one or more servers, in **groups**:

- `Subscribe`: server -> local variable. `Write`: local variable -> server. Each group has a cycle time in ms
  (500 used).
- The local side is any program variable of B: no port, no flag needed. Simple types REAL, BOOL, INT, DINT are
  supported (REAL and INT **proven**). Each local variable only once.
- In Engineer: PLANT > OPC UA > "Client Connections" (a table of servers: name, URL, user, password, security
  mode; and the variable groups) and "Client Settings".

`program.json` of B:

```json
"opcua_client": {
  "connections": [{"name": "PLC_A", "url": "opc.tcp://192.168.1.10:4840", "user": "plc_b",
                   "password_secret": "PLC_A_OPCUA_PASSWORD"}],
  "groups": [
    {"type": "Subscribe", "cycle_ms": 500, "server": "PLC_A", "map": {"M.A_TEMP": "M.TEMP"}},
    {"type": "Write", "cycle_ms": 500, "server": "PLC_A", "map": {"M.TO_A_VALUE": "M.REMOTE_VALUE"}}],
  "trust_all": true
}
```

- `map`: local variable (B) : variable on the server (A), both `<instance>.<NAME>`. The remote one must be
  visible on A (above).
- `security_mode` (`SignAndEncrypt`, default; `Sign`; `None`) and `security_policy` (`BestAvailable`, default)
  per connection. A offers no "None".

**Switch the client on**, once per controller: web interface > System Services > "OPC UA Client". On file:
`<Feature id="OPCUA CLIENT" enable="true"/>` in `/opt/plcnext/config/System/Scm/Default.scm.config`, then restart
the runtime (`sudo systemctl restart plcnext`).

**Licence.** Without the "OPC UA Client License" the client works for 4 hours, counted from the start of the
runtime (log: `LicenseCheckFailed`, then `LicenseTrialStarted`). A project write (Write and Start) does **not**
start them again (**proven**, 2026-11-23: trial started 21:41, a write at 21:54, the client stopped at 01:41:39).
The end shows only in the log:

```
ConnectionStatusChanged ... ServerState='Disconnected'
DisconnectPassed
License WARN - LicenseTrialStopped - Done stopping trial period
```

After that the mapped variables simply keep their last values, on both sides; nothing in the program shows it
(no status variable). Send a counting value across and watch it, as the example does. Only
`sudo systemctl restart plcnext` (or a reboot) starts another 4 hours. Fine on a bench; for a plant buy the
licence, and tell the user so.

## Passwords

The client logs in with user and password, and the firmware wants the password **in clear**: in the project file
(`Hardware/CFG_*/OPCUA/<id>.L7_5.opcuaclicon`) and again in the compiled file on the controller. Two ways in
`program.json`, one per connection:

- `password_env`: name of an environment variable read when the project is built. The password goes into the
  project file. Simple, but it is then in every copy of the project (backups, mails, the repository).
- `password_secret`: name of an environment variable that `plc-opcua-client.sh` reads when it runs, the same
  way as the controller's password (`scripts/config.sh`: from your shell, or through your secret manager's runner
  `PLC_SECRET_RUN`). The connections stay **out** of the project
  (`pxproj.py` prints `opcua_client: connections are not in the project; run plc-opcua-client.sh <program dir>
  after the write`). After the write, `scripts/plc-opcua-client.sh <program dir>` writes the same compiled form
  to `/opt/plcnext/projects/Default/Services/OpcUA/Modules/Client/Configs/clientconnections.xml` on the
  controller, with the password piped through stdin (never printed, never in argv), and restarts the
  runtime. `PLC_HOST` must name the **client** controller; the default is 192.168.1.10. **Proven**: this way.

Never put the same connection in both places: the client would log in twice, and a wrong password repeated
every few seconds may lock the user.

## Certificates

The client rejects a server certificate it does not know. Two ways:

- Trust the server's certificate on the client controller: web interface > Security > Certificate
  Authentication, trust store "OPC UA Client" (**untested**).
- For a bench: `"trust_all": true`. In the controller's `.ds` this sets
  `opcuaClientModuleSessionSecurityDefinitionEnabled` True and `opcuaClientModuleApplicationAuthentication`,
  `opcuaClientModuleApplicationUriCheck`, `opcuaClientModuleCertificateHostnameCheck` False (**proven**; the log
  then says "Overriding default element value"). Say to the user that it is a bench setting.

## Diagnosis

The client's lines are in `/opt/plcnext/logs/Arp.log` of the client controller, logger
`Arp.Services.Modules.OpcUAServer.Client.Internal.RemoteSession`. Use `grep -a` (the log has binary bytes):

```bash
grep -a OpcUAServer.Client.Internal.RemoteSession /opt/plcnext/logs/Arp.log | tail
```

- `ConnectFinished - Connected to server endpoint`: up.
- `ConnectFailed ... Service='Activate session', Status='BadUserAccessDenied'`: wrong user or password.
- `Open secure channel ... Bad` to the server's own host name: comes first when that name does not resolve
  (a controller with a static address has no DNS); the address is tried next and works. Seen every time,
  harmless.
- `LicenseCheckFailed`, `LicenseTrialStarted`: no licence, 4 hours trial (above).
- `LicenseTrialStopped - Done stopping trial period`, after `ServerState='Disconnected'` and `DisconnectPassed`:
  the 4 hours are over; values no longer move.

No status variable of the client was found: the program cannot see whether the link is up, and a link that
stopped (trial over, server away) leaves the last values standing. Give the server a counter that the client
writes (a heartbeat) and watch it there (`examples/opcua-pair`, `LINK_OK`).

## Limits, not tried

Trusting the server certificate in the trust store instead of `trust_all`; the licensed client; BOOL and DINT over the link; arrays, strings, structs; more than one server; a cycle
time other than 500 ms; how the client behaves when the server restarts or is away for long; security mode
`Sign`; a third-party OPC UA server or client.

A "Write" group sends a value when it changes. After the server's program was written again (its variables back
at their initial values) the counting value arrived at once and the two unchanged REALs stayed 0 until their
source changed (**seen**). Where the server must always hold the value, let it change (add a counter) or keep it
in a retain variable on the server.

A later write of the client controller keeps the file that `plc-opcua-client.sh` wrote (it lies outside the
project folder), and the session comes up again by itself (**proven**).
