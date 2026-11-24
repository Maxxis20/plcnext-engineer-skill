# Step sequences in Structured Text

Proven on 2026-11-24 on two AXC F 2152 (firmware 2026.0.2) with PLCnext Engineer 2026.6: the pump start sequence
of `examples/pump-sequence` (four steps, interlocks, alarms, manual overrides) passed the 41 checks of its test
script against a simulated drive. This page is the pattern, and how the operator page shows it.

## Why not SFC

- **SFC needs a licence of its own** (a CodeMeter feature, "SFC Editor"), separate from Engineer's. Without it
  (**proven**): a project with an SFC function block gives `LIC001 No license for SFC found` and nothing else, the
  SFC editor does not open, and the licence check hides every other compiler message, so a compile proves nothing
  about the project, not even its ST parts.
- `pxproj.py` does not generate SFC. What is known of the format, for whoever has the licence (**vendor**: from
  Engineer's own template `SequencialFunctionChartTemplate.plcntx2` and its help; nothing compiled):
  - SFC exists only as a function block (`BaseType` `SFC_BASE`, or `SFC_BASE_COMPACT` with the parameters in one
    struct), called from a program. One chart per POU, one initial step.
  - The chart is `Code.sfc` in the POU folder: one line of XML with the element names of PLCopen TC6 2.01 without
    its namespace (`step`, `transition`, `actionBlock`, `jumpStep`, `selectionDivergence`, ...), positions in
    grid units as in an LD sheet.
  - Coded transitions, actions, a step's interlock and `_PreExecute` / `_PostExecute` are methods of the block, each
    a folder `<NAME>.method/` with its own `Metadata.meta` (`Type` Transition, Action, Interlock, ...),
    `Variables.var` and `Code.st`.
  - Control from outside through the block's own pins: `PRESET_OPERATING_MODE` (auto, halt, step, forced step),
    `PROCEED`, `STEP_ID` with `ACTIVATE_STEP` / `DEACTIVATE_STEP`, `ACKNOWLEDGE_ERROR`; step state through the
    outputs `STEP_STATES` and `STRUCTURE` (arrays of structs: copy into plain variables for a page). Min / max
    step time per step; a violation halts the chart.
  - Not known: how step times are stored, the action block sizes, whether a generated chart opens in the
    editor. Settle them by drawing one small chart in the licensed editor and comparing its files.
- An ST state machine compiles everywhere, every value the page needs is a plain program variable, and the
  rules that must stay above the chart (a safety chain) sit in the same code in plain sight. That is what the
  example does.

## The pattern

One INT is the step (`SQ_STEP`: 0 idle, 1..n). Every cycle, in this order:

1. **Commands** from the page: one INT (`SQ_CMD`) that the page writes and the program clears in the same cycle
   (1 Start, 2 Stop, 3 Continue, 4 Next, 5 Go to chosen, 6 Reset). A button writes a number; there is no edge to
   detect and a command cannot stick.
2. **Step entry**: `IF SQ_STEP <> SQ_PREV THEN` reset the step's timers and the cursor; `SQ_PREV := SQ_STEP`. Any
   way into a step (normal, Next, Go to, Reset) goes through it.
3. **Step data** in one `CASE`: per step the number of requirements, its settle time, its supervision time, and
   each requirement as a BOOL (`RQ1 := IL_PN; ...`). Requirements are interlock BOOLs computed earlier, never
   expressions only the step knows: the page shows the same BOOLs.
4. **The first requirement not met** (`FBAD`, or n + 1 when all are met), and a **cursor** (`RQ_AT`) that walks
   toward it one row per 0.5 s and jumps back at once to a row that is lost. The page shows the walk: the operator
   sees which check the sequence is on.
5. **Forced stop** outside the steps' logic: in the steps where the drive runs, a lost forced stop interlock raises
   the alarm at once, whatever the mode. Nothing below can override it.
6. **Automatic only** (Auto mode, no alarm): the supervision time runs while a requirement is not met; when it is
   up, alarm with the step and the requirement. When the cursor is through the list, the settle time runs, then
   the next step. A step that holds (RUNNING) has no settle time and supervises only while a requirement is lost.
7. **Outputs from the step and the interlocks**, after the sequence, in one place:
   `RUN_CMD := (SQ_STEP = 2 OR SQ_STEP = 3) AND FS_OK AND NOT SQ_ALARM;`. The steps only move the step number.

```
CASE SQ_STEP OF
1:  SQ_N := 5; SETTLE := 3.0; TMAX := 15.0;             (* PRECHECK *)
    RQ1 := IL_PN; RQ2 := IL_SIS; RQ3 := IL_RDY; RQ4 := IL_REM; RQ5 := IL_TEMP;
2:  SQ_N := 3; SETTLE := 1.0; TMAX := 10.0;             (* START DRIVE *)
    RQ1 := FS_OK; RQ2 := SPEED_ACT > 0; RQ3 := DRV_RUNNING;
...
END_CASE;
IF SQ_N >= 1 AND NOT RQ1 THEN FBAD := 1;
ELSIF SQ_N >= 2 AND NOT RQ2 THEN FBAD := 2;
...
ELSE FBAD := SQ_N + 1;
END_IF;
TICK := TICK + TS;
IF RQ_AT > FBAD THEN RQ_AT := FBAD;
ELSIF RQ_AT < FBAD AND TICK >= 0.5 THEN RQ_AT := RQ_AT + 1; TICK := 0.0;
END_IF;
IF SQ_MODE = 0 AND NOT SQ_ALARM THEN
    IF FBAD <= SQ_N THEN SUP_T := SUP_T + TS; END_IF;
    IF TMAX > 0.0 AND SUP_T >= TMAX THEN SQ_ALARM := TRUE; AL_STEP := SQ_STEP; AL_REQ := FBAD; END_IF;
    IF RQ_AT > SQ_N AND NOT SQ_ALARM THEN
        SETTLE_T := SETTLE_T + TS;
        IF SETTLE_T >= SETTLE THEN SQ_STEP := SQ_STEP + 1; END_IF;
    ELSE
        SETTLE_T := 0.0;
    END_IF;
END_IF;
```

The full code is `examples/pump-sequence/a/src/MAIN/Code.st`. Rules it keeps:

- **The alarm holds.** An alarm stops the sequence where it is (held, outputs safe) until **Reset** (alarm off,
  back to idle, a reset pulse to the drive) or **Continue** (alarm off, back to Auto, the supervision time starts
  again: the step is retried). It never clears itself when the cause goes away.
- **Manual holds too.** In Manual nothing advances by itself and nothing is supervised. **Next** forces the
  transition, **Go to** jumps to a chosen step; both count (`OV_CNT`). Both rank below the forced stop, which
  stays in force in every mode (**proven** by the test: a drive fault in a step reached by Go to raised the alarm
  and cut the run command).
- **Times by counting cycles**: `T := T + TS` with `TS` the task cycle. No `TON` needed; times stay plain REALs the
  page can show (`SETTLE_T` of `SETTLE`, `SUP_T` of `TMAX`, and their percentages for bars).
- **Codes, not texts**: the program gives numbers (`AL_STEP`, `AL_REQ`, 11.. for the forced stop causes); the page
  turns them into words. The page cannot index a table of strings.
- Two operating modes, kept apart: the **sequence's** mode (Auto / Manual: who advances the steps) and the
  **drive's** mode (Auto / Manual / Local: who commands the drive). The sequence runs only with the drive in Auto.

## On the page

Every element below is in `examples/pump-sequence/a/hmi.py`, page "Pump".

- **Step flow**: one rounded chip per step, side by side, joined by links. A chip's colour comes from one
  expression, `fill_by=("M.SQ_STEP - n", [(-9, white), (0, active colour), (1, done colour)])`: ahead, active,
  done. A red chip with the same shape on top, `visible` while the alarm is in that step. A number in a circle,
  replaced by a tick once the step is done.
- **Checklist of the active step**: up to five rows. Row i's fill follows `M.RQ_AT - i` the same way (not yet,
  checking, OK), and its text is the active step's requirement i: one text object per step and row, each
  `visible` only in its step. "OK" / "CHECKING" / "next" on the right, also by `RQ_AT`.
- **Settle and supervision**: two bars that grow with `SETTLE_PCT` and `SUP_PCT` (`rect(..., grow=(var, 0,
  100))`), with "time of time" beside them.
- **Alarm banner**: the top band turns red with `SQ_STATE`; the text is one object per (step, requirement) and
  per forced stop cause, `visible` by `AL_STEP` and `AL_REQ`. The same for the state in words (ready, starting,
  running, held, stopping).
- **Interlock ladder**: per group a left rail, one row per condition, a contact drawn with three rects (two
  plates and a green bar across them, `visible` while closed; a red outline in the gap while open), the row
  red while open, and the group's result as a coil (an ellipse, green / red by `FS_OK` / `PERM_OK`). Each
  condition is its own BOOL in the program, so the page needs no logic of its own.
- **Two-way switches** (Auto | Manual): two buttons that write 0 / 1, and over the active one a dark rect and a
  white text, `visible` by the variable. A page button cannot be disabled; where a button must not be used, a
  half transparent rect covers it (whether that stops a click is **untested**: let the program ignore the
  command in the wrong mode, as the example does).
- **A REAL set by steps of 0.5**: a button's step must be whole (`findings.md`, "HMI pages"). Keep the value as an
  INT x 10 (`TEMP_MAX10`), step it by 5, and let the program make the REAL.
- Trends of the speed and the room temperature on a second page (`hmi-trends.md`), a database view on a third
  (`clickhouse.md`).

## Testing it

Write each test as a series of REST writes and waits (`examples/pump-sequence/test_seq.sh`): bring both sides
to a clean state, `pxe.sh set M.SQ_CMD=1` (a page button does the same), `pxe.sh wait M.SQ_STEP 3 3 20`, switch a
fault on in the simulator, `wait` for the alarm and read the reason. The simulator on a second controller (or in
a function block of the same program) makes every fault repeatable: trip, safety chain, no feedback, an
interlock limit.
