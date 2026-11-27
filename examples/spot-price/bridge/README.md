# Spot price bridge

`spotd.py` fetches day-ahead electricity prices and serves them as retained MQTT messages and as a Modbus TCP
server, so that a controller can use them without speaking HTTPS and JSON itself and **without reaching the
internet**. What it serves: [CONTRACT.md](CONTRACT.md). Python 3.9 or newer, standard library only (on Windows add
the `tzdata` package for the time zones).

```bash
cp config.example.json config.json      # areas, time zone, broker, Modbus port
python3 spotd.py config.json --once     # fetch and print, nothing served
python3 spotd.py config.json            # run (MQTT password: environment variable named in "password_env")
```

- Areas: DK1 DK2 EE FI LT LV NO1-NO5 SE1-SE4 from api.spot-hinta.fi (open, no key, one request per minute per
  address; the bridge asks once an hour per area, every 10 minutes in the afternoon until tomorrow's prices are
  there). FI falls back to api.porssisahko.net. Check the terms of the source before using it commercially.
  Other European zones would need another source (ENTSO-E, with a token): not built.
- Area selection in a controller project: the MQTT topic `spot/<AREA>/...` or the Modbus unit id (1 = first
  area of the list in the config).
- Where to run it: on a machine between the networks. Only the bridge needs the internet (outbound HTTPS to the
  price source); the controllers open their connection to the bridge or to the broker, nothing is opened towards
  them. With a broker: give the bridge the right to write `spot/#` and the controllers read-only access.
- Tests: `"source": "fake"` with a price file and a settable clock (head of `spotd.py`); the file is read again
  every 10 s, so a test changes prices, clock and "source dead" while the bridge runs.
- macOS: the python.org Python has no root certificates until its "Install Certificates" step has run.

Checked: live fetch for FI; a fake day with negative prices over MQTT and Modbus TCP; tomorrow arriving; dead
source -> `valid` 0; a controller reading it over Modbus TCP (this example). The MQTT side was checked against a
test receiver and one broker, not with this example's controller program.
