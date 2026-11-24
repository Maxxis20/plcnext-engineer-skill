# Trend charts on an eHMI page

Proven on 2026-11-24 on an AXC F 2152 (firmware 2026.0) with PLCnext Engineer 2026.6. A generated project with two
DataLogger sessions and two charts on their own page was written with Write and Start. One start/stop cycle of a
pump showed up in the chart, and the history was still there after a page reload. The example is
`examples/pump-sequence/a` (page "Trends" in `hmi.py`, picture `img/trends.png`).

## What it takes

- **A DataLogger session of type TSDB.** The chart shows only what such a session has recorded on the controller.
  It has no live mode that reads variables directly. The session is part of the project (PLANT > PLCnext > Data
  Logger Sessions), not a setting on the controller.
- **Ports only.** A session records only IN or OUT ports (or globals) of an elementary type. An `EHMI` variable is
  not enough. Add a copy as a port and write it every cycle:

  ```
  VAR
      TR_SPEED_ACT : INT { OutputPort };    (* = SPEED_ACT, for the trend *)
  END_VAR
  ```
  ```
  TR_SPEED_ACT := SPEED_ACT;
  ```

  The pen is labelled with the port's name (`M.TR_SPEED_ACT`), so pick names that read well. The copy needs no
  `EHMI`. Copies leave the existing page variables as they are; flagging the original as a port would move it
  into the program's port block.
- **Variables of a cyclic task** (the HMI compiler rejects idle and event tasks).
- Nothing on the controller: **Write and Start starts the sessions**, with no restart. Arp.log then has
  `Session '<name>': Session started logging of N variables.`

## program.json

```json
"datalogger": [
  {"name": "Speed", "sampling_ms": 1000, "variables": ["M.TR_SPEED_OUT", "M.TR_SPEED_ACT"]},
  {"name": "Room",  "sampling_ms": 1000, "variables": ["M.TR_TEMP", "M.TR_TEMP_MAX"]}
]
```

- `name`: letters, digits, `_ - . +`, unique. One session per chart is simplest. A chart must list every variable
  of its session.
- `variables`: `<instance>.<port>`. The generator stops with a clear message when a name is not a port of an
  instance.
- `sampling_ms`: the sampling interval (default 1000). `publish_ms` defaults to 200, as Engineer sets it.
- It fills the empty DataLogger document that every base project has. The rest is as Engineer writes a fresh TSDB
  session: `Destination` `/opt/plcnext/logs/datalogger/<name>`, file size 5 MB, no trigger. The file has CRLF line
  endings and no BOM. Engineer reads it and saves it back unchanged.

## hmi.py

```python
p.chart("SpCh", 40, 134, 1200, 246, "Speed",
        [("M.TR_SPEED_OUT", "#FF263340", "Left"), ("M.TR_SPEED_ACT", "#FF0F8B8D", "Left")],
        minutes=15, sampling_ms=1000, left=(0, 1000))
p.button("GoTrends", 930, 100, 110, 32, "Trends  ›", page="Trends")     # page switch
```

`chart(id, x, y, w, h, session, pens, minutes=15, sampling_ms=1000, mode="Raw", left=(0, 0), right=(0, 0), zoom=False)`

- `pens`: `(variable, colour, "Left" | "Right")`, **one per variable of the session, in the session's order**. If
  the pens and the session differ, Engineer throws the pens away and makes new ones with its default colours. The
  colour may be `#AARRGGBB` like everywhere in pxhmi: the alpha is dropped, because Engineer stores `#RRGGBB`.
- `left` / `right`: `(min, max)` of the axis; `(0, 0)` means automatic. The right axis is shown only when a pen
  uses it.
- `sampling_ms` must be the session's sampling interval. Engineer stores it in the chart, and in `Raw` mode it
  fixes the time range.
- The chart draws its own frame, axes and legend; it has no title. Put a `text` above it.

`button(..., page="<name>")`: Engineer's Action on Click > Load page, `LoadPageAction` with the target page's id.
pxproj puts the id in and stops when no page has that name. It works in the browser (proven both ways between
two pages).

## Time range and points

| Mode | Points per pen | Time range |
|---|---|---|
| `Raw` (default here) | every sample, **at most 1000** | samples × sampling interval; Engineer recomputes it so |
| `Downsample` | **at most 100** over the range (LTTB) | any (`minutes`) |

At 1 s sampling, `Raw` covers at most 16 min 40 s at full resolution. `minutes=15` gives 900 samples. For longer
windows, either sample slower or use `Downsample` and accept one drawn point per range/100 (15 min → every 9 s).
A fast event (a 3 s ramp) is only a few pixels wide in a 15-minute window: the data is there, but the window is too
wide to show its shape.

## The XML (as Engineer 2026.6 writes it)

The DataLogger document lives in `Hardware/CFG_.../PLCnext/<guid>.L7_1.datalogger`. The chart is an
`<HmiObject xsi:type="HmiChart">` with the usual attributes and **no `<Fill>`**. Its child elements are, in order:
`Trends/Trend` (`VariablePath`, `IsIncluded`, `LineColor`, `Placement`), `DataLoggerSessionRef` (`InstanceName`,
`Paths/string`), `MinimumInterval`, `DataMode`, `TrendSampleSize`, `AllAvailableOnTimeRange`, `XScaleDisplayMode`
(`MM:SS`), `PreloadData`, `AllowZoom`, `LeftAxis`, `RightAxis`, `HorizontalAxis` and `TimeRange` (`hhh:mm:ss.fff`).
`Page.chart()` in `pxhmi.py` writes exactly this.

## Not tried

Zoom and the reset-zoom action, `Downsample` on the controller, a pen hidden with `IsIncluded=false`, history across
a controller restart, and how much history the store keeps on the SD card over days.

## Time axis: 12-hour clock only (seen in the page code, firmware 2026.0.2)

The chart's time labels are drawn by the controller's own page code (`hmiapp.min.js`), not by the project:
clock times use the fixed format `%I:%M:%S %p` (`06:07:00 PM`; over a day `%b %d %I:%M:%S %p`), whatever the
browser's locale. The only other mode is `XScaleDisplayMode` = `M`: ticks counted back from now (`-16:00`).
Engineer writes `MM:SS`, which gives the clock labels. A 24-hour axis is not possible in the chart; where 24-hour
times matter, draw the labels yourself (the History page of `examples/pump-sequence` builds `HH:MM` strings in the
program and shows them under its bars).

