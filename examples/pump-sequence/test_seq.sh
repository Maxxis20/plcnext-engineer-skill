#!/usr/bin/env bash
# test_seq.sh [test ...] - the pump start sequence on A against the drive simulator on B, over REST (pxe.sh read,
# wait, set). Both projects written and running, B named on the network (README.md).
# A_HOST / B_HOST: the controllers (default 192.168.1.10 / 192.168.1.11).
# Tests: start stop estop nofb trip temp manual pnloss (default: all but pnloss). Each starts from idle with no alarm.
set -uo pipefail
P=$(cd "$(dirname "$0")/../../scripts" && pwd)/pxe.sh
A_HOST=${A_HOST:-192.168.1.10}; B_HOST=${B_HOST:-192.168.1.11}
A() { PLC_HOST=$A_HOST "$P" "$@"; }
B() { PLC_HOST=$B_HOST "$P" "$@"; }
pass=0; fail=0
ok()   { echo "  PASS $*"; pass=$((pass+1)); }
bad()  { echo "  FAIL $*"; fail=$((fail+1)); }
expect() {  # expect <inst.VAR> <low> <high> <seconds> <what>
  if A wait "$1" "$2" "$3" "$4" >/dev/null; then ok "$5"; else bad "$5 ($(A read "$1"))"; fi; }
clean() {   # B healthy, A idle, Auto, limit 30 C
  B set DRV.SIM_TRIP=false DRV.SIM_ESTOP=false DRV.SIM_NO_FB=false DRV.SIM_LOCAL=false >/dev/null
  A set M.SQ_MODE=0 M.DRV_MODE_REQ=0 M.TEMP_MAX10=300 >/dev/null; A set M.SQ_CMD=6 >/dev/null
  A wait M.SQ_STEP 0 0 20 >/dev/null; A wait M.DRV_READY 1 1 20 >/dev/null; A wait M.SPEED_ACT 0 0 30 >/dev/null; }
run_to_running() { A set M.SQ_CMD=1 >/dev/null; expect M.SQ_STEP 3 3 40 "reaches RUNNING"; }

t_start() { echo "start: normal start, then Stop"; clean
  A set M.SQ_CMD=1 >/dev/null
  expect M.SQ_STEP 1 1 10 "PRECHECK"
  expect M.RQ_AT 6 6 10 "cursor walks through 5 requirements"
  expect M.SQ_STEP 2 2 10 "START DRIVE after settle"
  expect M.SQ_STEP 3 3 20 "RUNNING"
  expect M.SPEED_ACT 590 610 10 "speed at setpoint 60 %"
  A set M.SQ_CMD=2 >/dev/null
  expect M.SQ_STEP 4 4 10 "STOP"
  expect M.SQ_STEP 0 0 30 "back to idle"
  expect M.SQ_ALARM 0 0 1 "no alarm"; }
t_estop() { echo "estop: safety chain opens while running"; clean; run_to_running
  B set DRV.SIM_ESTOP=true >/dev/null
  expect M.SQ_ALARM 1 1 5 "alarm"
  expect M.AL_REQ 12 12 2 "reason: safety chain"
  expect M.RUN_CMD 0 0 2 "run command off"
  if B wait DRV.SPEED_ACT 0 0 20 >/dev/null; then ok "drive stopped at B"; else bad "drive still turning at B"; fi
  B set DRV.SIM_ESTOP=false >/dev/null; A set M.SQ_CMD=6 >/dev/null
  expect M.SQ_STEP 0 0 10 "Reset: idle"; }
t_nofb() { echo "nofb: no running feedback"; clean; B set DRV.SIM_NO_FB=true >/dev/null
  A set M.SQ_CMD=1 >/dev/null
  expect M.SQ_STEP 2 2 15 "START DRIVE"
  expect M.SQ_ALARM 1 1 20 "alarm after supervision time"
  expect M.AL_STEP 2 2 1 "in step 2"; expect M.AL_REQ 3 3 1 "requirement 3: running feedback"
  expect M.RUN_CMD 0 0 2 "run command off, held"
  B set DRV.SIM_NO_FB=false >/dev/null; A set M.SQ_CMD=3 >/dev/null
  expect M.SQ_STEP 3 3 30 "Continue: retries and reaches RUNNING"
  A set M.SQ_CMD=2 >/dev/null; expect M.SQ_STEP 0 0 30 "stopped"; }
t_trip() { echo "trip: drive fault while running"; clean; run_to_running
  B set DRV.SIM_TRIP=true >/dev/null
  expect M.SQ_ALARM 1 1 5 "alarm"; expect M.AL_REQ 13 13 2 "reason: drive fault"
  B set DRV.SIM_TRIP=false >/dev/null
  expect M.DRV_FAULT 1 1 3 "fault latched at B"
  A set M.SQ_CMD=6 >/dev/null
  expect M.DRV_FAULT 0 0 10 "Reset clears the drive fault"
  expect M.SQ_STEP 0 0 5 "idle"; }
t_temp() { echo "temp: room temperature above the limit refuses the start"; clean
  A set M.TEMP_MAX10=100 >/dev/null
  expect M.IL_TEMP 0 0 5 "interlock open"
  A set M.SQ_CMD=1 >/dev/null
  expect M.RQ_AT 5 5 10 "cursor stops at requirement 5"
  expect M.SQ_ALARM 1 1 25 "alarm after 15 s"; expect M.AL_REQ 5 5 1 "requirement 5: room temperature"
  expect M.RUN_CMD 0 0 1 "drive never commanded"
  A set M.TEMP_MAX10=300 >/dev/null; A set M.SQ_CMD=6 >/dev/null; expect M.SQ_STEP 0 0 5 "Reset: idle"; }
t_manual() { echo "manual: overrides; safety stays above them"; clean
  A set M.SQ_MODE=1 >/dev/null; A set M.SQ_CMD=1 >/dev/null
  expect M.SQ_STEP 1 1 5 "Start in Manual: PRECHECK"
  sleep 8; expect M.SQ_STEP 1 1 1 "held in PRECHECK (no automatic advance)"
  A set M.SQ_CMD=4 >/dev/null; expect M.SQ_STEP 2 2 3 "Next: START DRIVE"
  A set M.SQ_SEL=3 >/dev/null; A set M.SQ_CMD=5 >/dev/null; expect M.SQ_STEP 3 3 3 "Selected: RUNNING"
  expect M.OV_CNT 2 30000 1 "overrides counted"
  B set DRV.SIM_TRIP=true >/dev/null
  expect M.SQ_ALARM 1 1 5 "drive fault still trips in Manual"; expect M.RUN_CMD 0 0 2 "run command off"
  B set DRV.SIM_TRIP=false >/dev/null; A set M.SQ_CMD=6 >/dev/null; A set M.SQ_MODE=0 >/dev/null
  expect M.SQ_STEP 0 0 5 "Reset: idle"; }
t_pnloss() { echo "pnloss: B's runtime restarts while running (untested)"; clean; run_to_running
  # B's admin password as in SKILL.md "Passwords": PLC_B_SECRET names its environment variable
  PLC_HOST=$B_HOST PLC_SECRET=${PLC_B_SECRET:-PLC_PASSWORD} PLC_TIMEOUT=150 "$(dirname "$P")/plc-ssh.sh" --sudo 'sudo -S -p "" /bin/systemctl restart plcnext' >/dev/null 2>&1 &
  expect M.SQ_ALARM 1 1 40 "alarm"; expect M.AL_REQ 11 11 1 "reason: Profinet link"
  expect M.RUN_CMD 0 0 1 "run command off"; wait
  expect M.B_ALIVE 1 1 120 "link back"
  A set M.SQ_CMD=6 >/dev/null; expect M.SQ_STEP 0 0 5 "Reset: idle"; }

tests=${*:-start estop nofb trip temp manual}
for t in $tests; do "t_$t"; done
echo "passed $pass, failed $fail"; [ "$fail" = 0 ]
