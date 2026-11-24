# opcua-pair: two controllers share values over OPC UA

Controller A (192.168.1.10) is the server: its program has three variables flagged `{ EHMI, OPC }` and the
project shows the flagged ones (`"opcua": {"visibility": "marked"}`). Controller B (192.168.1.11) runs the
firmware's OPC UA client, configured, not programmed: every 500 ms it reads `M.TEMP` of A into its `M.A_TEMP`
and writes its `M.TO_A_VALUE` and its counter `M.TO_A_BEAT` into A's `M.REMOTE_VALUE` and `M.REMOTE_BEAT`. On
A, `LINK_OK` is TRUE while the counter moves.

This pair was built only, not opened in Engineer nor run. The same pattern ran on two AXC F 2152 (firmware
2026.0.2, 2026-11-23): B read four values of A every 500 ms and wrote two REALs and a counting INT into A, seen on
both sides over REST and on A's operator page.

How it works, passwords, certificates, the log: `../../reference/opcua.md`.

## Steps, in this order

1. **A user on A for B.** A's web interface > Security > User Authentication > "Add User": a user for B (here
   `plc_b`) with the role **DataChanger** (reads and writes; DataViewer only reads). The OPC UA server takes no
   anonymous client. Make the password available under the name in B's `program.json`
   (`PLC_A_OPCUA_PASSWORD`): an environment variable in your shell, or an entry your secret manager's runner
   (`PLC_SECRET_RUN`, `scripts/config.sh`) provides.
2. **Write A**: `pxe.sh build examples/opcua-pair/a`, `open`, `write` as usual. `pxe.sh read M.TEMP` moves
   between 20 and 24.
3. **Switch the client on, on B** (once per controller): B's web interface > System Services > "OPC UA Client".
   The same as a file: `findings.md`, "OPC UA". Without the vendor's client licence it runs 4 hours from the
   start of B's runtime; a later write of B does not start them again, `sudo systemctl restart plcnext` on B
   does. Enough for a bench, not for a plant.
4. **Write B**: `pxe.sh build examples/opcua-pair/b` prints `opcua_client: connections are not in the project;
   run plc-opcua-client.sh <program dir> after the write`. That is expected: with `password_secret` the
   connection stays out of the project file. Open and write as usual (the project's target is B; `read` and
   `state` on B need `PLC_HOST=192.168.1.11` in front of `pxe.sh`).
5. **Put the connection on B**: `PLC_HOST=192.168.1.11 PLC_SECRET=<variable with B's admin password>
   scripts/plc-opcua-client.sh examples/opcua-pair/b`. It writes the client's configuration file on B with the
   password (through stdin, never printed), restarts B's runtime (about 45 s) and prints the last client lines of the
   log. Without `PLC_HOST` the script goes to 192.168.1.10, which is A.
6. **Look**: the log line `ConnectFinished - Connected to server endpoint` on B (`opcua.md`, "Diagnosis");
   then `PLC_HOST=192.168.1.11 pxe.sh read M.A_TEMP` follows A's `M.TEMP`, and on A `M.REMOTE_VALUE` is that
   value + 100 and `M.LINK_OK` TRUE. Watch `LINK_OK` rather than the values: when the link stops (the 4 hour
   trial is over, A is away) the copied values just keep their last state on both sides.

`"trust_all": true` in B makes its client take A's certificate without a trust store entry. Bench only; for a
plant trust A's certificate on B instead (`opcua.md`, "Certificates").

A later write of B keeps the file of step 5 (it lies outside the project folder) and the session comes up again
by itself (`opcua.md`). If B shows no client lines after a write, run step 5 again.
