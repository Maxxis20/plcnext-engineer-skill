# From the controller into ClickHouse

Proven on 2026-11-24 on an AXC F 2152 (firmware 2026.0.2) with PLCnext Engineer 2026.6 and a ClickHouse server on
the controllers' network: ten values of the pump sequence stored every second, read back once a minute, drawn by
Grafana. Blocks and setup: `examples/clickhouse-log`; in use: `examples/pump-sequence/a`.

Nothing of it is the firmware's: no library, no app, no licence. Two function blocks in Structured Text on the
socket blocks of the "PLCnext Controller" library (`TCP_SOCKET`, `TCP_SEND`, `TCP_RECEIVE`, the same ones as the
MQTT subscriber, `mqtt-subscribe.md`).

## Design

- **ClickHouse's HTTP interface**, port 8123, plain HTTP/1.0. One request per connection: open, send, read until
  the server closes; the answer is complete when the connection is closed. No keep-alive, no chunked reading.
- **User and password in headers**: `X-ClickHouse-User`, `X-ClickHouse-Key`. The query is the start of the POST
  body, the data follows it (no `?query=` in the URL, so nothing has to be URL-encoded).
- **Insert**: `INSERT INTO plc.samples (tag, value, ago_ms) FORMAT JSONEachRow`, then one line per value and
  sample: `{"tag":"SPEED_ACT_RPM","value":870.000,"ago_ms":7012}`. Values go out with 3 decimals.
- **Batching**: every `SAMPLE_S` (1 s) the block keeps up to 16 values with its own millisecond clock; every
  `SEND_S` (10 s) it sends what it has. A request holds whole samples only, up to about 12 KB of rows (about 25
  samples of 10 values). When 5 or more samples are left after a good insert, the next request goes at once.
- **Time stamps from `ago_ms`**: each row says how old the value is when it is sent; the table computes `ts DEFAULT
  now64(3) - toIntervalMillisecond(ago_ms)`. The controller's clock is never used: it may have no time source at
  all (`findings.md`, "Controller", Time). The time stamp is the server's receiving time minus the age, so the
  network and the request time shift a whole batch by the same small amount: about 0.1 s of jitter at the edges of
  a batch, none inside it (**proven**).
- **The table** (`examples/clickhouse-log/table.sql`): `ts DateTime64(3)`, `tag LowCardinality(String)`, `value
  Float64`, `ago_ms UInt32`, MergeTree ordered by `(tag, ts)`, TTL 90 days. One row per value: any number of tags,
  and Grafana groups by `tag`.
- **On failure** the samples stay for the next try: at most 60 samples (a minute at 1 s). When the store is full
  newer samples are dropped and counted (`N_DROP`). After an error the block closes the socket and waits 10 s.
  Time limits: 10 s to open, 10 s to send, 15 s for the answer.
- **The plant never waits for it.** The block takes a few socket calls a cycle and never blocks; the program
  uses nothing that comes back. A dead server shows on the page (batch age, errors), nothing else.

`FB_CH` inputs: `ENABLE`, `HOST` (an address), `PORT`, `USER`, `KEY`, `TABLE`, `N_TAGS` (1..16), `TAGS` / `VALS`
(arrays 1..16), `SAMPLE_S`, `SEND_S`, `QUERY`, `QUERY_S`, `TS` (the task cycle). Outputs: `STATE`, `PENDING`,
`N_ROWS`, `N_POST`, `N_ERR`, `N_DROP`, `HTTP_CODE`, `ERR_STATUS`, `OK_AGE`, `Q_VALS[1..24]`, `Q_N`, `Q_AGE`. The
comments at the top of its `Code.st` and `Variables.var` say the rest.

## Proven numbers

- One row per value and second, no gaps: 113 rows in 112 s for one tag.
- **The first version lost rows.** With 4 KB buffers a request held only 7 samples; at one request every 10 s the
  backlog grew by 3 samples each time until the store was full and rows were dropped. Fixed with 12 KB buffers
  (`FB_TXT.BUF`, `FB_CH.TXBUF`) and sending a backlog at once. After that: 0 errors, 0 dropped rows.
- Building a request costs time per character (`FB_TXT` looks each one up with `FIND`). So the tag names and the
  JSON pieces are turned into bytes once at the start, and a request is built at most 4 samples a cycle.

## Reading back (display only)

Every `QUERY_S` (60 s) the block sends `QUERY` with ` FORMAT TSV` added and reads the numbers of the answer, one
per line (or tab separated), into `Q_VALS[1..24]`; lines that are not numbers are skipped. The pump example asks
for the average speed of each of the last 24 minutes and shows them as bars (page History):

```sql
SELECT v FROM (SELECT toStartOfMinute(ts) AS m, round(avg(value), 1) AS v FROM plc.samples
  WHERE tag = 'SPEED_ACT_RPM' AND ts > now() - INTERVAL 24 MINUTE GROUP BY m
  ORDER BY m WITH FILL FROM toStartOfMinute(now() - INTERVAL 23 MINUTE) TO toStartOfMinute(now()) + 60 STEP 60)
ORDER BY m
```

`WITH FILL` gives a row (0) for a minute without data, so bar n is always minute n. In the ST literal the
quotes are written as `@` (FB_TXT's stand-in for `'`, below). **Proven**: an answer every 60 s, 24 values.

- The parser takes digits, `-` and `.`; no exponent, no `nan` / `inf` (`round` in the query keeps them out).
- Use it for a view, never for control: the answer can be a minute old or missing (`Q_AGE` says how old).

## Text in Structured Text (`FB_TXT`)

A string literal cannot hold a backslash or a `$` (escape), and no character-to-byte conversion was found
(`findings.md`, "Structured Text"). `FB_TXT` appends text to a byte buffer by looking each character up in a
table string of the characters 40 to 126. In template text (`CMD 1`) stand-ins give what a literal cannot hold:
`` ` `` for `"`, `@` for `'`, `^` for CR LF, `|` for LF (`~` for a space). Characters not in the table become
spaces: ``! " # $ % &`` and the quote. Raw text (`CMD 5`: names, user, password) is taken as it is, with the same
gap. Numbers: `CMD 2` (REAL, 3 decimals), `CMD 3` (whole number); `CMD 6` copies prepared bytes.

## Security

- **Plain HTTP only.** User, password and data cross the network in clear. Use it on a closed plant network, with a
  firewall that lets only the controller and the readers reach port 8123. `TLS_SOCKET_2` and relatives exist in
  the library (**untested**), as does ClickHouse's HTTPS port.
- **A user of its own** with `INSERT, SELECT, CREATE TABLE ON plc.*`, bound to the controller's address. Grafana and
  people get a second, read-only user (`SELECT ON plc.*`). Never the server's `default` user.
- **The password goes in at build time**: `KEY := '%%ENV:CLICKHOUSE_PASSWORD%%'` in the source; `pxproj.py`
  replaces the token with the environment variable's value (`env_tokens`) and stops when it is not set. Build
  through the secret manager's runner so the value reaches only that process. Not over REST: a variable written
  that way must be flagged `{ EHMI }`, and with the page's login off anyone who reaches the page interface can read
  it back (`pxe.sh read` needs no session).
- The built project file holds the password in clear, and so does the program on the controller (string
  constants of the compiled image: assume they can be read out). Keep `.plcnx2` files out of version control and
  do not pass them on; rotate the password when one has left your hands.
- `pxproj.py` refuses a value with `'`, `$`, `\` or a line break; FB_TXT turns characters below 40 into spaces.
  Pick the password from letters, digits and `( ) * + , - . / : ; < = > ? [ ] _ { } ~`.

## Grafana

The ClickHouse data source plugin (`grafana-clickhouse-datasource`) with the read-only user;
`examples/clickhouse-log/grafana/pump-p1.json` is the bench's dashboard over the pump example's tags. Queries are plain SQL with the plugin's macros:
`SELECT $__timeInterval(ts) AS time, tag, avg(value) AS v FROM plc.samples WHERE $__timeFilter(ts) AND tag IN (...)
GROUP BY time, tag ORDER BY time`. A stat panel with the age of the newest row shows at a glance whether the
controller still writes.

## Other ways, other databases (untested)

- **MQTT and a collector.** The firmware's own MQTT client publishes flagged ports once a second as JSON
  (`findings.md`, "MQTT"); a collector beside the broker (Telegraf, Node-RED, a small script) writes them into
  any database: InfluxDB, TimescaleDB / PostgreSQL, ClickHouse. Nothing to program on the controller, but one
  more service to run, and the time stamp is the collector's or the message's. Untested.
- **OPC UA** (`opcua.md`) polled by a collector: the same, with a client of your choice. Untested.
- **The DataLogger** keeps trends on the controller itself for the page's charts (`hmi-trends.md`); it is not a
  database to query from outside.
- Other databases with an HTTP insert (InfluxDB's line protocol, for one) could use `FB_CH` with a different
  request body. Untested.
