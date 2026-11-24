# clickhouse-log: values from the controller into ClickHouse, over HTTP

The ClickHouse client of `../pump-sequence` on its own: `FB_TXT` (text into bytes) and `FB_CH` (samples, batched
inserts, a query read back), and a `MAIN` that stores one counting value (`RAMP`) every second and counts its
rows once a minute. Design, limits and security: `../../reference/clickhouse.md`.

The blocks are **proven** in `../pump-sequence/a` (2026-11-24, AXC F 2152, firmware 2026.0.2, a ClickHouse server
on the controllers' network): ten values a second, one row per value and second with no gaps, 0 errors and 0
dropped rows after the fix described there, the read back every 60 s. This small project was only built here;
its `MAIN` is the same call with one value.

- `src/FB_TXT`, `src/FB_CH`: copy both into a project (FB_TXT first in `pous`). They use the socket blocks
  `TCP_SOCKET`, `TCP_SEND`, `TCP_RECEIVE` of the "PLCnext Controller" library that every project references.
- `src/MAIN`: the call. Server `192.168.1.60` (a placeholder: put yours), port 8123, user `plc_writer`, table
  `plc.samples`.
- `table.sql`: the table.
- `grafana/pump-p1.json`: a Grafana dashboard over the tags of `../pump-sequence` (speed, room temperature,
  step and drive state, open interlocks, rows per minute, age of the newest row).

## The server (once)

A ClickHouse server reachable from the controller on its HTTP port (8123, plain HTTP). The controller has no DNS
with a static address: give the server as an address. The statements below are the setup the bench had, written
out for this README; they were not run as they stand here (**untested** as written).

```sql
-- as an admin user of the server (one with access_management)
CREATE DATABASE IF NOT EXISTS plc;
-- then table.sql

-- the controller: writes and reads plc.*, nothing else, only from the controller's address
CREATE USER plc_writer IDENTIFIED WITH sha256_password BY '<password>' HOST IP '192.168.1.10';
GRANT INSERT, SELECT, CREATE TABLE ON plc.* TO plc_writer;

-- Grafana (and you, for checks): read only
CREATE USER plc_reader IDENTIFIED WITH sha256_password BY '<another password>';
GRANT SELECT ON plc.* TO plc_reader;
```

The same as XML, for a server whose users come from files (`/etc/clickhouse-server/users.d/plc.xml`):

```xml
<clickhouse>
  <users>
    <plc_writer>
      <password_sha256_hex>...</password_sha256_hex>   <!-- echo -n '<password>' | sha256sum -->
      <networks><ip>192.168.1.10</ip></networks>
      <profile>default</profile>
      <grants><query>GRANT INSERT, SELECT, CREATE TABLE ON plc.*</query></grants>
    </plc_writer>
  </users>
</clickhouse>
```

- Never give the controller the `default` user: its password stands in the program (below).
- The password's characters: printable, from `(` (40) to `~` (126) only, and no `'`, `$`, `\`. FB_TXT turns
  ` ! " # $ % & '` into spaces, and an ST literal cannot hold the others (`../../reference/findings.md`,
  "Structured Text").
- `listen_host` must include the address on the controllers' network; a firewall that lets only the
  controller (and Grafana) reach port 8123 is worth having, as everything crosses in clear.

## Build

The password goes in at build time, never through REST: `KEY := '%%ENV:CLICKHOUSE_PASSWORD%%'` in `MAIN` is
replaced by `pxproj.py` with the value of the environment variable `CLICKHOUSE_PASSWORD`, and the build stops if
it is not set. Run the build through your secret manager so the value reaches only that process:

```bash
op run -- scripts/pxe.sh build examples/clickhouse-log     # or any runner that sets CLICKHOUSE_PASSWORD
scripts/pxe.sh open examples/clickhouse-log/CHLOG.plcnx2
scripts/pxe.sh write
scripts/pxe.sh read M.CH_STATE M.CH_ROWS M.CH_ERR M.CH_CODE M.Q1
```

The built `.plcnx2` holds the password in clear: keep it out of version control (this skill's `.gitignore`
has `*.plcnx2`) and do not pass it on. Name the variable as you like; the token is `%%ENV:<NAME>%%`.

Within 10 s `CH_ROWS` grows by about 10 per request and `CH_CODE` is 200; a minute later `Q1` is the row count
of `RAMP`. `CH_STATE` 9 with `CH_ERR` growing and `CH_CODE` 0: no connection (address, port, firewall; `ERR_STATUS` of
`FB_CH` holds the socket's status). `CH_CODE` other than 200: the server refused; send the same request with curl
(below) to read its reason.

## Check the rows with curl

From a machine on the same network, as the read-only user, the password out of the command line (curl reads
headers from stdin with `-H @-`):

```bash
q() { printf 'X-ClickHouse-User: plc_reader\nX-ClickHouse-Key: %s\n' "$CH_READER_PW" |
      curl -s -H @- --data-binary "$1" http://192.168.1.60:8123/; }
q "SELECT tag, count(), min(ts), max(ts) FROM plc.samples WHERE ts > now() - INTERVAL 5 MINUTE GROUP BY tag"
# one row a second, no gaps: rows = span + 1
q "SELECT count() AS rows, dateDiff('second', min(ts), max(ts)) AS span FROM plc.samples
   WHERE tag = 'RAMP' AND ts > now() - INTERVAL 2 MINUTE"
# the time stamps: 1 s apart, about 0.1 s off where one batch ends and the next begins
q "SELECT ts, value, ago_ms FROM plc.samples WHERE tag = 'RAMP' ORDER BY ts DESC LIMIT 30"
```

## Grafana

The ClickHouse data source plugin (`grafana-clickhouse-datasource`) with the read-only user. The dashboard file
is in the form of Grafana's HTTP API (`{"dashboard": ..., "overwrite": true}`, `POST /api/dashboards/db`); its
panels name the data source by uid `clickhouse`: give your data source that uid, or replace it in the file. For
the UI's import dialog, take the inner `dashboard` object. Queries are plain SQL with the plugin's macros:

```sql
SELECT $__timeInterval(ts) AS time, tag, avg(value) AS v FROM plc.samples
WHERE $__timeFilter(ts) AND tag IN ('SPEED_SP_RPM', 'SPEED_ACT_RPM') GROUP BY time, tag ORDER BY time
```
