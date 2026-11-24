#!/usr/bin/env bash
# vm.sh - reach the machine that runs PLCnext Engineer. Two transports (scripts/config.sh):
#   local    the scripts run on that Windows machine itself, in Git Bash: PowerShell is started directly
#   proxmox  the machine is a Windows VM on a Proxmox host, reached through the qemu guest agent (no password, no RDP)
#
#   vm.sh ps  '<powershell>' | -      run PowerShell, no desktop needed (proxmox: as SYSTEM). '-' = script on stdin
#   vm.sh ui  '<powershell>' | - [s]  run in the logged-on user's desktop session, wait up to s seconds (120)
#   vm.sh pipe <s> '<powershell>'     run PowerShell with this command's stdin as its stdin (passwords travel this way)
#   vm.sh put <local> <win path>      copy a file to the Engineer machine
#   vm.sh get <win path> <local>      copy a file from it
#   vm.sh shot [png]                  screenshot of the whole screen; prints the path, Read it
#   vm.sh gui 'click x y' 'keys {F5}' ...   mouse/keyboard on the desktop (see win/gui.ps1), then a screenshot path
#   vm.sh uia 'invoke <id>' 'find <regex>' ...  Engineer controls by UI Automation id (see win/uia.ps1)
#   vm.sh key <qemu key> ...          proxmox only: console keys, e.g. ret, esc, ctrl-alt-delete
#
# 'ui' needs a user logged on at the screen. One ui command at a time.
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd); . "$S/config.sh"
WORK=$PXE_WORK

if [ "$PXE_TRANSPORT" = local ]; then            # ---- on the Engineer machine itself ---------------------------------
  w() { cygpath -w "$1" 2>/dev/null || printf '%s\n' "$1"; }
  u() { cygpath -u "$1" 2>/dev/null || printf '%s\n' "$1"; }
  script() { local s=${1:-}; [ "$s" = - ] && s=$(cat); printf '%s' "$s"; }
  runps() { local t; t=$(mktemp); mv "$t" "$t.ps1"; printf '\xef\xbb\xbftry { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}\n%s\n' "$1" > "$t.ps1"   # with BOM: read as UTF-8
            powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(w "$t.ps1")" </dev/null | tr -d '\r'; local rc=${PIPESTATUS[0]}; rm -f "$t.ps1"; return $rc; }
  case "${1:-}" in
    ps|ui) runps "$(script "${2:-}")" ;;
    pipe)  powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand "$(printf '%s' "$3" | iconv -f utf-8 -t utf-16le | base64 | tr -d '\n')" | tr -d '\r' ;;
    put)   mkdir -p "$(dirname "$(u "$3")")"; cp "$2" "$(u "$3")" ;;
    get)   cp "$(u "$2")" "$3" ;;
    shot)  out=${2:-${TMPDIR:-/tmp}/pxe-$(date +%H%M%S).png}
           powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(w "$S/win/shot.ps1")" "$(w "$out")" </dev/null >/dev/null; echo "$out" ;;
    gui)   shift; powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(w "$S/win/gui.ps1")" "$@" </dev/null | tr -d '\r'; sleep 1
           "$0" shot "${PLCVM_SHOT:-${TMPDIR:-/tmp}/pxe-gui.png}" ;;
    uia)   shift; powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$(w "$S/win/uia.ps1")" "$@" </dev/null | tr -d '\r' ;;
    key)   echo "vm.sh key: only with the proxmox transport" >&2; exit 2 ;;
    *) sed -n 2,16p "$0"; exit 2 ;;
  esac
  exit
fi

# ---- a Windows VM on a Proxmox host, through the guest agent ---------------------------------------------------------
: "${PLCVM_NODE_IP:?set PLCVM_NODE_IP (and PLCVM_NODE, PLCVM_ID, PLCVM_USER) in $PXE_HOME/config, see scripts/config.sh}"
NODE=${PLCVM_NODE:?PLCVM_NODE: name of the Proxmox node}; VMID=${PLCVM_ID:?PLCVM_ID: number of the VM}; WUSER=${PLCVM_USER:?PLCVM_USER: Windows user at the screen}; IP=$PLCVM_NODE_IP
SSH=(ssh -o BatchMode=yes -o ControlMaster=auto -o "ControlPath=/tmp/plcvm-%r@%h" -o ControlPersist=120 "root@$IP")   # one connection, reused

# guest exec with stdin, prints stdout, stderr to stderr, returns the guest exit code
gx() { # gx <timeout> <command...>   (stdin is passed to the command)
  local t=$1 in out err try; shift; in=$(cat); err=$(mktemp)
  for try in 1 2 3 4 5 6; do          # a guest agent that is not running was not given the command: asking again is safe
    out=$(printf '%s' "$in" | "${SSH[@]}" "qm guest exec $VMID --pass-stdin 1 --timeout $t -- $*" 2>"$err") && break
    grep -q "guest agent is not running" "$err" || break
    [ $try = 6 ] || sleep 10
  done
  if [ -z "$out" ] && [ -s "$err" ] && ! grep -q "guest agent is not running" "$err"; then
    echo "vm.sh: guest exec failed: $(head -1 "$err")" >&2; rm -f "$err"; return 1; fi
  grep -v "guest agent is not running" "$err" >&2 || true; rm -f "$err"
  printf '%s' "$out" | python3 -c '
import sys, json
try: d = json.load(sys.stdin)
except ValueError: sys.exit("vm.sh: the Engineer machine does not answer (guest agent not running for a minute: the VM is off, starting or hung)")
sys.stdout.write(d.get("out-data", "").replace("\r\n", "\n"))
e = "\n".join(l for l in d.get("err-data", "").splitlines() if not l.startswith(("#< CLIXML", "<Objs")))
if e.strip(): sys.stderr.write(e + "\n")
if d.get("out-truncated") or d.get("err-truncated"): sys.stderr.write("vm.sh: OUTPUT TRUNCATED by the guest agent\n")
sys.exit(d.get("exitcode", 1))'
}

enc() { printf '%s' "$1" | iconv -f utf-8 -t utf-16le | base64 | tr -d '\n'; }
pse() { echo "powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $(enc "$1")"; }

put() { # put <local> <win path>: base64 over stdin in 700 kB pieces
  local src=$1 dst=$2 first=1 part
  local tmp; tmp=$(mktemp -d); split -b 700000 "$src" "$tmp/p."   # the guest agent takes 1 MiB of input per call: 700 kB is 933 kB as base64
  for part in "$tmp"/p.*; do
    local mode; [ $first = 1 ] && mode=Create || mode=Append; first=0
    base64 < "$part" | tr -d '\n' | gx 120 "$(pse "\$d=[Convert]::FromBase64String([Console]::In.ReadToEnd()); New-Item -ItemType Directory -Force (Split-Path '$dst') | Out-Null; \$f=[IO.File]::Open('$dst','$mode'); \$f.Write(\$d,0,\$d.Length); \$f.Close()")"
  done
  [ $first = 1 ] && : | gx 60 "$(pse "New-Item -ItemType File -Force '$dst' | Out-Null")"
  rm -rf "$tmp"
}
get() { # get <win path> <local>: base64 in 240 kB pieces
  local src=$1 dst=$2 off=0 n=240000 len   # small pieces: the guest agent drops larger outputs
  len=$(: | gx 60 "$(pse "(Get-Item -LiteralPath '$src').Length")" | tr -d '\r\n ')
  : > "$dst"
  while [ "$off" -lt "$len" ]; do
    : | gx 120 "$(pse "\$f=[IO.File]::OpenRead('$src'); \$null=\$f.Seek($off,'Begin'); \$b=New-Object byte[] $n; \$r=\$f.Read(\$b,0,$n); \$f.Close(); [Convert]::ToBase64String(\$b,0,\$r)")" | base64 -d >> "$dst"
    off=$((off + n))
  done
}
once() { # once <local> <win path>: put, unless this exact file went up in the last hour
  local h m; h=$(shasum "$1" | cut -c1-16); m="/tmp/plcvm-$VMID-$(basename "$1")-$h"
  [ -n "$(find "$m" -mmin -60 2>/dev/null)" ] && return 0
  put "$1" "$2" && touch "$m"
}
script() { local s=${1:-}; [ "$s" = - ] && s=$(cat); printf '%s' "$s"; }

case "${1:-}" in
  ps)  s=$(script "${2:-}")
       printf '%s' "$s" | base64 | tr -d '\n' | gx "${3:-120}" "$(pse '$w="C:\agentwork\plcnext\run"; New-Item -ItemType Directory -Force $w | Out-Null; [IO.File]::WriteAllText("$w\sys.ps1", [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadToEnd())), (New-Object Text.UTF8Encoding $true)); & "$w\sys.ps1"; exit $LASTEXITCODE')" ;;
  ui)  s=$(script "${2:-}")                        # the script travels on stdin of the same guest call that runs it
       wrap=$(sed -e "s/@USER@/$WUSER/" -e "s/@SECS@/${3:-120}/" <<'PS'
$w='C:\agentwork\plcnext\run'; New-Item -ItemType Directory -Force $w | Out-Null
Remove-Item "$w\ui.out","$w\ui.done" -ErrorAction SilentlyContinue
[IO.File]::WriteAllText("$w\ui.ps1", [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String([Console]::In.ReadToEnd())), (New-Object Text.UTF8Encoding $true))
if(-not (Get-ScheduledTask -TaskName 'plcnext-agent-ui' -ErrorAction SilentlyContinue)){
  # hidden through wscript: a visible console would take the focus and sit on top of what the script clicks
  Set-Content "$w\ui.vbs" ('CreateObject("WScript.Shell").Run "cmd /c " & WScript.Arguments(0), 0, True') -Encoding ASCII
  Set-Content "$w\ui.cmd" ('powershell -NoProfile -ExecutionPolicy Bypass -File "' + $w + '\ui.ps1" > "' + $w + '\ui.out" 2>&1 & echo done > "' + $w + '\ui.done"') -Encoding ASCII
  $a = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('//B //Nologo "' + $w + '\ui.vbs" "' + $w + '\ui.cmd"')
  $p = New-ScheduledTaskPrincipal -UserId '@USER@' -LogonType Interactive -RunLevel Highest
  Register-ScheduledTask -TaskName 'plcnext-agent-ui' -Action $a -Principal $p -Force | Out-Null
}
Start-ScheduledTask -TaskName 'plcnext-agent-ui'
$end=(Get-Date).AddSeconds(@SECS@)
while(-not (Test-Path "$w\ui.done") -and (Get-Date) -lt $end){ Start-Sleep -Milliseconds 150 }
if(Test-Path "$w\ui.out"){ Get-Content "$w\ui.out" }
if(-not (Test-Path "$w\ui.done")){ 'TIMEOUT (still running in the desktop session)'; exit 124 }
PS
)
       printf '%s' "$s" | base64 | tr -d '\n' | gx $(( ${3:-120} + 30 )) "$(pse "$wrap")" ;;
  pipe) gx "$2" "$(pse "$3")" ;;                   # caller's stdin -> the PowerShell process
  put) put "$2" "$3" ;;
  get) get "$2" "$3" ;;
  shot) out=${2:-${TMPDIR:-/tmp}/vm$VMID-$(date +%H%M%S).png}
       "${SSH[@]}" "pvesh create /nodes/$NODE/qemu/$VMID/monitor --command 'screendump /tmp/vm$VMID.ppm' >/dev/null && cat /tmp/vm$VMID.ppm" \
         | python3 -c 'import sys,PIL.Image as I; I.open(sys.stdin.buffer).save(sys.argv[1])' "$out"; echo "$out" ;;
  gui) shift; S=$(cd "$(dirname "$0")" && pwd); once "$S/win/gui.ps1" "$WORK\\run\\gui.ps1"
       args=""; for a in "$@"; do args="$args '${a//\'/\'\'}'"; done
       "$0" ui "& '$WORK\\run\\gui.ps1' $args" 90; sleep 1
       "$0" shot "${PLCVM_SHOT:-${TMPDIR:-/tmp}/vm$VMID-gui.png}" ;;
  uia) shift; S=$(cd "$(dirname "$0")" && pwd); once "$S/win/uia.ps1" "$WORK\\run\\uia.ps1"
       args=""; for a in "$@"; do args="$args '${a//\'/\'\'}'"; done
       "$0" ui "& '$WORK\\run\\uia.ps1' $args" 90 ;;
  key) shift; for k in "$@"; do "${SSH[@]}" "qm sendkey $VMID $k"; done ;;
  *) sed -n 2,16p "$0"; exit 2 ;;
esac
