# The MCP server app on the controller (read-only diagnosis for an AI client)

Phoenix Contact offers an app "MCP for PLCnext Control" (version 1.0, free, from the PLCnext Store): an MCP server
in a container on the controller, port **58080**, that gives an MCP client read access to the controller's device
data, variables, notifications, files, OPC UA, data logger, Axioline I/O and licences. It writes nothing. This
skill does the engineering (build, write, test); the MCP server is a second way to *look* at a running controller,
for example from Claude Code (`claude mcp add --transport http plcnext https://<controller>:58080/mcp`).

**Proven** on an AXC F 2152, firmware 2026.6.1, app 1.0.0.31224 (ARM32 package), November 2026, through
`scripts/plc-mcp.py`. Get the app yourself (Store or the package from Phoenix Contact); it is not part of this skill.

## Getting it to run on an AXC F 2152 (what it took)

- **The app manager installs it but does not start its container** on this controller (firmware 2026.0.2 and
  2026.6.1): the container start file is placed by a script that runs only for the user `app_user`, which exists
  only with the newer permission layout ("secure by default" controllers). The app shows as installed and active,
  nothing listens on 58080, nothing in the logs. Install through the web page (System > App Management) or the
  same calls by script (`reference/findings.md`, "Apps through the same API").
- A package from outside the Store may be unsigned: the controller refuses it ("App has no signature extension")
  unless signature checking is relaxed (test benches only, `findings.md`).
- **Run the container yourself as admin instead** (rootless podman, which the firmware has): the parameters are in
  the app's own `mcp-server.container` (inside the `.app`, a squashfs): environment, port, volumes (config, data,
  logs, the controller's HTTPS certificate and key, the gRPC socket `/var/run/plcnext/grpc.sock`), `--userns
  keep-id:uid=1002`. From 2026.6 admin may `loginctl enable-linger admin`, so a container with `--restart always`
  and `systemctl --user enable podman-restart.service` outlives the session.
- **Not on the internal flash**: the image is 56 MB packed, 144 MB unpacked, and `podman load` stages every layer
  unpacked on the same flash; at 97 % fill the controller reboots itself (`findings.md`). Use an SD card: an ext4
  card made with `mkfs.ext4 -E root_owner=1002:1002` (so admin owns its root) is mounted at
  `/media/rfs/externalsd` at the next start (a card is only taken at startup); put podman's `graphroot` and
  `image_copy_tmp_dir` there (`~/.config/containers/storage.conf`, `containers.conf`). A third-party card worked;
  the manual asks for Phoenix Contact cards.
- Loading: convert the app's docker-archive image into an OCI directory (layers stay compressed) and `podman pull
  oci:<dir>` (without a reference: the image's tag has capitals, which podman refuses), then `podman tag`.
- With the container running the controller had about 120 MB of 488 MB RAM available (pump program, Profinet, a
  Modbus RTU master running). `GET https://<controller>:58080/health/ready` -> `{"status":"ready","checks":
  {"config":true,"database":true,"grpc":true,"mcp":true}}`.

## Login

The server uses the controller's own users (no user database of its own) and OAuth 2.0 with PKCE: dynamic client
registration (`/register`), `/authorize` sends to `/login?auth_session=..`, the page posts `{username, password}`
to `/auth/login?auth_session=..` and gets back a redirect with the code, `/token` gives a Bearer token. MCP over
Streamable HTTP at `/mcp` (JSON-RPC, `Mcp-Session-Id`). Clients without OAuth use a token made at `/token-gen`
(browser login). Each call is logged on the server (audit log), 60 calls a minute per user.

The controller's HTTPS certificate is self-signed (subject "PLCnext HTTPS Interface List", the controller's IP as
SAN): a Node client such as Claude Code needs it as `NODE_EXTRA_CA_CERTS=<pem>` **when it starts**; fetch it with
`openssl s_client -connect <controller>:58080 </dev/null | openssl x509 > plc.pem`.

`scripts/plc-mcp.py` does the login itself (password from the environment, under your secret runner; never
printed, token kept in memory) and then `tools`, `schema <tool>`, `call <tool> '<json>'`, `resources`,
`resource <uri>`.

## The tools (25), as found

| Group | Tools | Result on the bench |
|---|---|---|
| device | `device_get_device_info(s)`, `_status(es)`, `_setting(s)` | works. Info: `General.ArticleName`, `General.ArticleNumber`, `General.Firmware.Version`, `General.Hardware.Version`. Status names are in the resource `docs://plcnext/device/status/parameters`, e.g. `Status.Cpu.0.Load.Percent`, `Status.Memory.Usage.Percent.Actual`, `Status.ProgramMemoryIEC.Usage.Percent`, `Status.Board.Temperature.Centigrade`; a wrong name gives `CT_Void`, not an error |
| gds | `gds_read_variable(s)` | works, **any port variable** of the program (`Arp.Plc.Eclr/<instance>.<var>`), not only `{ EHMI }` ones; system ports too (`Arp.Io.PnC/PNIO_CONFIG_STATUS`). Values come typed (`CT_Real32`, `CT_Int16`, ...) |
| notifications | `..._get_active_notifications`, `..._get_notification_history {limit}`, `..._get_alarm_history` | works: archives such as `security` (logins, sessions) with name, sender, time, severity, payload |
| files | `files_list_directory {path}`, `files_read_file`, `files_get_file_info` | works with the Admin role: `/opt/plcnext/logs` (Arp.log, Output, sqlite archives) |
| historical | `historical_get_data_loggers`, `historical_get_logged_values {logger_name, start, end}` | the list works (the project's DataLogger sessions); reading values failed with every time format: "grpc_call failed: startTime: Unspecified datetimekind" (app 1.0 on firmware 2026.6.1) |
| axioline | `axioline_read_configuration {frame_reference: 0}`, `axioline_pdi_read` | works: the local bus modules (type, id, process data length) |
| opcua | `opcua_browse_nodes`, `opcua_browse_tree`, `opcua_read_value`, `opcua_get_connection_info` | refused: "Insufficient permissions" - by default these four are granted to no role (server's own docs, `docs_read_page {page: tools/opcua}`); they also need the server's OPC UA client certificate (made at first start) trusted by the controller's OPC UA server |
| licensing | `licensing_get_license_status {firm_code, product_code, feature_code}` | not tried (needs the vendor's codes) |
| docs | `docs_search {query}`, `docs_read_page {page}` | works: the server's own manual, the tool table with permissions and roles |

## Where it helps the skill

- After a write: notifications and `Arp.log` through `files_read_file` without SSH; device status (CPU, memory,
  temperature) without the web page.
- Reading any program variable for a test, also ones not marked `{ EHMI }` (the REST interface reads only those).
- It does not replace `pxe.sh read/set`: it cannot write, and each call needs a login (or a held session).
