#!/usr/bin/env bash
# plc-ssh.sh [--out <file on the Engineer machine> | --in <file there>] [--sudo] '<command>' - run a shell command on
# the controller (admin@PLC_HOST) from the machine that runs Engineer, which is the one that reaches the controller.
#
# The admin password goes: environment (or your secret manager, scripts/config.sh) -> stdin of one PowerShell
# process on the Engineer machine -> environment of one ssh process there (SSH_ASKPASS). It is never printed, never
# in argv, never on disk on either side.
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd); . "$S/config.sh"; PLC=$PLC_HOST
OUT=""; [ "${1:-}" = --out ] && { OUT=$2; shift 2; }   # --out <file on the Engineer machine>: the command's output, byte for byte, into that file (backups)
IN=""; [ "${1:-}" = --in ] && { IN=$2; shift 2; }       # --in <file on the Engineer machine>: that file, byte for byte, on the command's stdin (restore, upload)
SUDO=0; [ "${1:-}" = --sudo ] && { SUDO=1; shift; }      # --sudo: the password is also on the command's stdin, for 'sudo -S -p : <allowed command>' lines in it
CMD_B64=$(printf '%s' "${1:?usage: plc-ssh.sh [--sudo] '<command>'}" | base64 | tr -d '\n')
read -r -d '' PS <<PSEOF || true
\$env:PLCPW = [Console]::In.ReadToEnd().TrimEnd("\`r","\`n")
\$d = '$PXE_WORK\\run'; New-Item -ItemType Directory -Force \$d | Out-Null
Set-Content "\$d\\askpass.cmd" '@powershell -NoProfile -Command "[Console]::Out.Write(\$env:PLCPW)"' -Encoding ASCII
\$env:SSH_ASKPASS = "\$d\\askpass.cmd"; \$env:SSH_ASKPASS_REQUIRE = 'force'; \$env:DISPLAY = 'x'
\$c = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('$CMD_B64'))
\$o = '-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=NUL','-o','LogLevel=ERROR','-o','ConnectTimeout=8','-o','PubkeyAuthentication=no','-o','NumberOfPasswordPrompts=1'
if ('$IN' -ne '') { cmd /c "ssh.exe \$(\$o -join ' ') admin@$PLC ""echo $CMD_B64 | base64 -d > /tmp/.plc-cmd.sh; sh /tmp/.plc-cmd.sh; rm -f /tmp/.plc-cmd.sh"" < ""$IN"" 2>&1" | Out-String }
elseif ('$OUT' -ne '') { cmd /c "ssh.exe \$(\$o -join ' ') admin@$PLC ""echo $CMD_B64 | base64 -d | sh"" > ""$OUT"""; "exit \$LASTEXITCODE, \$((Get-Item '$OUT').Length) bytes in $OUT" }
elseif ($SUDO -eq 1) { \$env:PLCPW | & ssh.exe @o admin@$PLC 'echo $CMD_B64 | base64 -d > /tmp/.plc-cmd.sh; sh /tmp/.plc-cmd.sh; rm -f /tmp/.plc-cmd.sh' 2>&1 | Out-String }
else { & ssh.exe @o admin@$PLC \$c 2>&1 | Out-String }
exit \$LASTEXITCODE
PSEOF
secrets "$PLC_SECRET" >/dev/null || exit 1                 # no password: say so before anything is started
secrets "$PLC_SECRET" | "$S/vm.sh" pipe "${PLC_TIMEOUT:-60}" "$PS"
