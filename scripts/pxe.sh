#!/usr/bin/env bash
# pxe.sh - PLCnext Engineer on the machine that runs it, one verb per step. Controls are found by UI Automation id,
# not by screen position. Engineer must be running in the desktop session (start: pxe.sh start).
#
#   pxe.sh check                 what is ready: Engineer machine, Engineer, PLC reachable
#   pxe.sh start                 start Engineer if it is not running (about 2.5 minutes)
#   pxe.sh build <program dir>   make <dir>/<name>.plcnx2 from the sources (pxproj.py), on this machine
#   pxe.sh open <file.plcnx2>    copy the project to the Engineer machine under a fresh name and open it; prints the error count
#   pxe.sh disconnect            go offline (open does it by itself)
#   pxe.sh errors                the error list of the open project
#   pxe.sh write                 connect to the controller (login from Engineer's password store) and Write and Start;
#                                waits until the controller runs this project
#   pxe.sh coldstart             start a program that is loaded but stopped (seen after the first write to the simulation)
#   pxe.sh state                 connection, project on the controller, LEDs text, memory and CPU load
#   pxe.sh read <inst.VAR> ...   current values from the controller (REST), e.g. read M.TE1 M.TV1; no screen needed
#   pxe.sh set <inst.VAR>=<v> ... write values over REST (variables with { EHMI }), e.g. set M.SQ_CMD=1
#   pxe.sh wait <inst.VAR> <low> <high> [s]   block until the value is inside low..high (default 120 s at most)
#   pxe.sh hmi [png]             the controller's operator page in a browser window over Engineer, screenshot of the desktop
#   pxe.sh mqtt [s] [topic]     what the broker on the Engineer machine receives in s seconds (default 6, all topics), "topic payload" lines
#   pxe.sh fuxa <project.json> [png]   load a FUXA project (pxfuxa.py) into the FUXA on the Engineer machine, show it in a browser window, screenshot
#   pxe.sh tap <x> <y> ...       click on the operator page at PAGE coordinates (those of hmi.py), then nothing else
#   pxe.sh show <instance>       Engineer in front with the program instance's code and its live values (when connected)
#   pxe.sh timer start|stop|off  stopwatch on the desktop over the taskbar clock (for recorded runs)
#   pxe.sh shot [png]            screenshot of the whole desktop
#   pxe.sh click <x> <y> ...     mouse clicks at SCREEN coordinates
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd); . "$S/config.sh"; V="$S/vm.sh"; PLC=$PLC_HOST
CTRL=${PXE_CONTROLLER:-}      # the controller's node in PLANT; found by itself when not set (its label follows the station name)
uia() { "$V" uia "$@"; }
front() { "$V" gui 'minimize brave' 'minimize msedge' 'minimize chrome' 'activate PLCnext Engineer' >/dev/null; }   # nothing on top of Engineer; the browser window keeps its page
title() { uia wins | sed -n "s/.*name='PLCnext Engineer - \(.*\)'.*/\1/p" | head -1; }
cockpit() {   # the Cockpit editor of the controller; its tab is a toggle, so click it only when the editor is not showing
  uia 'state AID_Connect / Disconnect' | grep -q "^Button" && return 0
  [ -n "$CTRL" ] || CTRL=$(uia 'expand ^AID_Project$' 'find ^AID_Project_[^_]+ : ' | sed -n "s/^TreeItem.* id='\([^']*\)'.*/\1/p" | head -1)
  [ -n "$CTRL" ] || { echo "no controller in the PLANT tree (is a project open?)" >&2; return 1; }
  uia 'expand ^AID_Project$' "dclick $CTRL" >/dev/null; sleep 3
  uia 'state AID_Connect / Disconnect' | grep -q "^Button" || { uia 'click AID_Description_Cockpit' >/dev/null; sleep 2; }
}
state() {
  uia 'state AID_Connect / Disconnect' 'texts .' | awk -F'[][,]' '
    /toggle=On/ {print "connected: yes"} /toggle=Off/ {print "connected: no"}
    / AID_Label = / {lab=$0; sub(/.* AID_Label = /,"",lab); y=$3; next}
    / = / {v=$0; sub(/^[^=]*= ?/,"",v); if (v!="" && lab!="" && $3>=y-8 && $3<=y+8) {print lab " " v; lab=""}}' > /tmp/pxe-state.$$ || true
  grep -q "Project name" /tmp/pxe-state.$$ || echo "Project name: (none)" >> /tmp/pxe-state.$$
  grep -E "connected|Project name|Memory|CPU load" /tmp/pxe-state.$$ || true; rm -f /tmp/pxe-state.$$
}
browse() {   # browse <url>: the page in its own window over Engineer (not full screen), reused when it is already open
  local S2; S2=$(cygpath -w "$S" 2>/dev/null || echo "$S"); read -r SW SH <<< "${PXE_SCREEN:-$("$V" ui 'Add-Type -A System.Windows.Forms; Add-Type "using System.Runtime.InteropServices; public class Dp { [DllImport(\"user32.dll\")] public static extern bool SetProcessDPIAware(); }"; [void][Dp]::SetProcessDPIAware(); $b=[Windows.Forms.Screen]::PrimaryScreen.Bounds; "$($b.Width) $($b.Height)"' | tr -d '\r' | tail -1)}"
  local X=$((SW/8)) Y=$((SH/9)) W=$((SW*3/4)); [ "${2:-0}" -gt 1300 ] && { X=10; Y=40; W=$((SW-20)); }   # a wide page gets the whole width
  local H=$((SH*3/4)); [ -n "${2:-}" ] && H=$(( (W - 16) * $3 / $2 + 40 ))        # window as high as a page of that size needs: no bars
  [ $H -gt $((SH-Y-60)) ] && H=$((SH-Y-60))
  "$V" put "$S/win/web.ps1" "$PXE_WORK\\run\\web.ps1" >/dev/null
  local r; r=$("$V" ui "& '$PXE_WORK\\run\\web.ps1' open '$1' $X $Y $W $H" 60 | tr -d '\r' | sed -n 's/^rect //p' | tail -1)
  [ -n "$r" ] || { echo "browser: no window"; exit 1; }
  echo "$r" > "$PXE_HOME/web-rect"; sleep 2
}
case "${1:-}" in
  check) H=$PXE_HOME; b=$(ls "$H/base" 2>/dev/null | sed -n 's/\.plcnx2$//p' | tr '\n' ' ')
         echo "base projects in $H/base: ${b:-NONE (see reference/findings.md, Base project)}"
         "$V" ps '"engineer machine: ok"; if(Get-Process PLCNENG64 -ea 0){"engineer: running"}else{"engineer: NOT running (pxe.sh start)"}; if(Test-Connection '"$PLC"' -Count 1 -Quiet){"plc '"$PLC"': answers"}else{"plc '"$PLC"': NO answer"}' ;;
  click) shift; a=(); while [ $# -ge 2 ]; do a+=("click $1 $2" "sleep 700"); shift 2; done; "$V" gui "${a[@]}" >/dev/null; echo "clicked" ;;
  start) "$V" ui 'if(-not (Get-Process PLCNENG64 -ea 0)){ Start-Process (gci "C:\Program Files\PHOENIX CONTACT\PLCnext Engineer*\PLCNENG64.exe" | sort FullName | select -Last 1).FullName; "starting" } else { "already running" }' 30
         for i in $(seq 1 30); do t=$(uia wins 2>/dev/null | grep -c "PLCnext Engineer" || true); [ "$t" -ge 1 ] && { echo "engineer: up"; exit 0; }; sleep 8; done; echo "engineer: not up after 4 minutes"; exit 1 ;;
  build) "$PY" "$S/pxproj.py" "$2" ;;
  disconnect) front; cockpit; uia 'state AID_Connect / Disconnect' | grep -q "toggle=On" && uia 'click AID_Connect / Disconnect' >/dev/null; sleep 2; echo "disconnected" ;;
  open)  front; f=$2;
         # while Engineer is connected to the controller it ignores File > Open, without a message: go offline first
         case "$(title)" in *.plcnx2*) cockpit       # the Connect button is only there while the Cockpit shows
           if uia 'state AID_Connect / Disconnect' | grep -q "toggle=On"; then uia 'click AID_Connect / Disconnect' >/dev/null; sleep 3; fi;; esac
         n=$(basename "$f" .plcnx2)_$(date +%H%M%S); w="$PXE_WORK\\proj\\$n.plcnx2"
         "$V" put "$f" "$w"
         # the toolbar's Open button by its id, not by screen position (Ctrl+O does nothing on the start page)
         uia 'click AID_Open Project...' >/dev/null
         "$V" gui 'sleep 2500' "text $w" 'sleep 300' 'keys {ENTER}' 'sleep 3000' >/dev/null
         uia 'press ^No$' >/dev/null || true                       # "save the current project?" -> No
         for i in $(seq 1 12); do case "$(title)" in *"$n"*) break;; esac; sleep 4; done
         e1=; for i in 1 2 3 4 5 6; do sleep 4; e2=$(uia 'texts errors, ' | sed 's/.*= //'); [ -n "$e2" ] && [ "$e1" = "$e2" ] && break; e1=$e2; done   # background compile done
         case "$(title)" in *"$n"*) ;; *) echo "open: FAILED, Engineer still shows $(title) (expected $n)"; exit 1;; esac
         echo "open: $(title)"; echo "$e2" ;;
  errors) uia 'press ^AID_Log_Messages$' >/dev/null 2>&1 || true; uia 'texts errors, |CellElement_[0-9]+_[35] = .{12}' | sed 's/^\[[^]]*\] //; s/^[A-Za-z_0-9]* = //' ;;
  write) front; cockpit
         connect() {   # no-op when connected; the login dialog only appears when Engineer has no session
           uia 'state AID_Connect / Disconnect' | grep -q "toggle=On" && return 0
           uia 'click AID_Connect / Disconnect' 'wait 20 ^AID_ButtonOK' | grep -q "id='AID_ButtonOK'" && uia 'press ^AID_ButtonOK$' >/dev/null
           for i in 1 2 3 4 5 6 7 8; do uia 'state AID_Connect / Disconnect' | grep -q "toggle=On" && return 0; sleep 3; done; return 1
         }
         connect || { echo "write: cannot connect"; uia 'texts CellElement_[0-9]+_5' | tail -2; exit 1; }
         want=$(title); want=${want%\*}; want=$(basename "${want//\\//}" .plcnx2)   # "*" = changed, after the extension
         uia 'click AID_Write and start combined_ActionButton' >/dev/null
         # the controller restarts its runtime on a download; Engineer often loses the connection then: reconnect and look
         for i in 1 2 3 4 5 6 7 8; do sleep 8; connect || continue
           s=$(state); echo "$s" | grep -q "Project name: $want" && { echo "write: ok"; echo "$s"; exit 0; }
           # still connected and nothing arrived: the click did not take (too soon after the login), press again once
           [ "$i" = 3 ] && uia 'click AID_Write and start combined_ActionButton' >/dev/null; done
         echo "write: controller does not report $want"; state; exit 1 ;;
  coldstart) front; cockpit; uia 'click AID_Start combined_ActionButton' >/dev/null; sleep 8; state ;;   # program loaded but stopped
  state) front; cockpit; state ;;
  read)  shift; paths=$(IFS=,; echo "$*")
         "$V" ps '& curl.exe -sk -m 8 "https://'"$PLC"'/_pxc_api/api/variables?pathPrefix=Arp.Plc.Eclr/&paths='"$paths"'"' | "$PY" -c '
import sys, json
try: d = json.load(sys.stdin)["variables"]
except Exception: sys.exit("read: no answer (if a vm.sh line stands above: the Engineer machine; else the controller: no project running, REST off in program.json, or unreachable)")
for v in d:
    val = round(v["value"], 3) if isinstance(v.get("value"), float) else v.get("value")
    print(v["path"].split("/", 1)[1], "=", val if "error" not in v else "ERROR " + v["error"]["reason"] + " (name wrong, or no { EHMI } flag)")' ;;
  set)   # set <inst.VAR>=<value> ...: write values over REST (the variables need { EHMI }), like a page button does
         shift; body=$("$PY" -c '
import sys, json
v = [{"path": a.split("=", 1)[0], "value": a.split("=", 1)[1], "valueType": "Constant"} for a in sys.argv[1:] if "=" in a]
print(json.dumps({"pathPrefix": "Arp.Plc.Eclr/", "variables": v}))' "$@")
         printf '%s' "$body" | "$V" pipe 30 '$b=[Console]::In.ReadToEnd(); $f=[IO.Path]::GetTempFileName(); [IO.File]::WriteAllText($f,$b)
& curl.exe -sk -m 8 -X PUT -H "Content-Type: application/json" --data-binary "@$f" "https://'"$PLC"'/_pxc_api/api/variables"; Remove-Item $f' | "$PY" -c '
import sys, json
try: d = json.load(sys.stdin)["variables"]
except Exception: sys.exit("set: no answer from the controller")
for v in d:
    print(v["path"].split("/", 1)[1], ":=", v.get("value") if "error" not in v else "ERROR " + v["error"]["reason"])' ;;
  wait)  # wait <inst.VAR> <low> <high> [seconds]: until the value is inside low..high (BOOL: 0 or 1), at most seconds (120)
         "$V" ps '$end=(Get-Date).AddSeconds('"${5:-120}"'); $v=$null
while((Get-Date) -lt $end){ $j = & curl.exe -sk -m 6 "https://'"$PLC"'/_pxc_api/api/variables?pathPrefix=Arp.Plc.Eclr/&paths='"$2"'" | ConvertFrom-Json
  $v=$j.variables[0].value; if($v -is [bool]){ $v=[int]$v }
  if($null -ne $v -and [double]$v -ge '"$3"' -and [double]$v -le '"$4"'){ "'"$2"' = $([math]::Round([double]$v,3))  (inside '"$3"'..'"$4"')"; exit 0 }
  Start-Sleep 2 }
"'"$2"' = $v  TIMEOUT: not inside '"$3"'..'"$4"' after '"${5:-120}"' s"; exit 1' $(( ${5:-120} + 20 )) ;;
  hmi)   read -r PW PH <<< "$(tr -d '\r' < "$PXE_HOME/page-size" 2>/dev/null)" ; [ -n "${PH:-}" ] || { PW=1280; PH=800; }
         browse "https://$PLC/ehmi/hmiapp.html" "$PW" "$PH"; "$V" shot ${2:-} ;;
  mqtt)  # mosquitto_sub -W does not end by itself when started without a console, so a job with a deadline does the listening
         "$V" ps '$j=Start-Job { & "C:\Program Files\mosquitto\mosquitto_sub.exe" -h 127.0.0.1 -t "'"${3:-#}"'" -v }; Wait-Job $j -Timeout '"${2:-6}"' | Out-Null; Receive-Job $j | % { if($_.Length -gt 400){ $_.Substring(0,400)+" ..." } else { $_ } }; Stop-Job $j; Remove-Job $j -Force' $(( ${2:-6} + 40 )) ;;
  fuxa)  "$V" put "$2" 'C:\agentwork\fuxa\project.json' >/dev/null
         c=$("$V" ps "curl.exe -s -o NUL -w '%{http_code}' -X POST -H 'Content-Type: application/json' --data-binary '@C:\agentwork\fuxa\project.json' http://127.0.0.1:1881/api/project" | tr -d '\r\n ')
         [ "$c" = 200 ] || { echo "fuxa: project not accepted (http $c); is FUXA running on the Engineer machine?"; exit 1; }
         echo "fuxa: project loaded"; sleep 4; browse "http://127.0.0.1:1881/"; sleep 4; "$V" shot ${3:-} ;;
  tap)   shift; read -r PW PH <<< "$(tr -d '\r' < "$PXE_HOME/page-size" 2>/dev/null)"
         read -r RX RY RW RH < "$PXE_HOME/web-rect" || { echo "tap: run pxe.sh hmi first"; exit 1; }
         a=(); while [ $# -ge 2 ]; do a+=("click $("$PY" -c "
pw,ph,rx,ry,rw,rh,x,y=map(float,'$PW $PH $RX $RY $RW $RH $1 $2'.split()); k=min(rw/pw,rh/ph)   # the page is scaled to fit its window and centred
print(round(rx+(rw-pw*k)/2+x*k), round(ry+(rh-ph*k)/2+y*k))")" "sleep 700"); shift 2; done
         "$V" gui "${a[@]}" >/dev/null; echo "tapped" ;;
  show)  front; cockpit
         uia 'state AID_Connect / Disconnect' | grep -q "toggle=On" || { echo "show: not connected (pxe.sh write first)"; exit 1; }
         uia 'state AID_Debug On / Off' | grep -q "toggle=On" || uia 'click AID_Debug On / Off' >/dev/null   # live values need debug mode
         uia 'expand ^AID_Project$' 'expand ^AID_Project_[^_]*$' 'expand _PLCnext$' 'expand _ESM[0-9]$' 'expand _ESM[0-9]_[^_]*$' >/dev/null
         id=$(uia "find _ESM[0-9]_[^_]*_$2 : " | sed -n "s/.*id='\([^']*\)'.*/\1/p" | head -1)
         [ -n "$id" ] || { echo "show: no program instance $2 in the PLANT tree"; exit 1; }
         uia "dclick $id" >/dev/null; sleep 4
         uia "find ^AID_EditorGroup_${2}_TabItem" | grep -q TabItem && echo "show: $2 open with live values" || { echo "show: the editor of $2 did not open"; exit 1; } ;;
  timer) S2=$(cygpath -w "$S" 2>/dev/null || echo "$S")       # timer start | stop (freeze) | off: stopwatch over the taskbar clock
         case "${2:-}" in
           start) "$V" put "$S/win/timer.ps1" "$PXE_WORK\\run\\timer.ps1" && "$V" ui 'Get-CimInstance Win32_Process | ? { $_.Name -eq "powershell.exe" -and $_.CommandLine -match "timer.ps1" } | % { Stop-Process -Id $_.ProcessId -Force }; Remove-Item C:\agentwork\plcnext\run\timer.stop -ea 0; Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File C:\agentwork\plcnext\run\timer.ps1"; "timer started"' 30 ;;
           stop)  "$V" ps 'Set-Content C:\agentwork\plcnext\run\timer.stop x; "timer stopped"' ;;
           off)   "$V" ps 'Get-CimInstance Win32_Process | ? { $_.Name -eq "powershell.exe" -and $_.CommandLine -match "timer.ps1" } | % { Stop-Process -Id $_.ProcessId -Force }; "timer off"' ;;
           *) echo "timer start|stop|off"; exit 2 ;;
         esac ;;
  shot)  "$V" shot ${2:-} ;;
  *) sed -n 2,22p "$0"; exit 2 ;;
esac
