# config.sh - settings shared by the scripts; sourced, not run.
#
# Where the scripts run:
#   - on the Windows machine that runs PLCnext Engineer, in Git Bash (what Claude Code uses there): nothing to set.
#   - on another machine, reaching a Windows VM on a Proxmox host through the qemu guest agent: PXE_TRANSPORT=proxmox
#     and PLCVM_NODE, PLCVM_NODE_IP, PLCVM_ID, PLCVM_USER (root ssh by key to the host).
# Settings come from the environment or from the file <work folder>/config (plain NAME=value lines, shell syntax);
# the work folder is ~/.plcnext-engineer (PXE_HOME).
#   PLC_HOST         the controller's address (default 192.168.1.10, the factory address)
#   PLC_SECRET       name of the environment variable that holds the controller's admin password (default PLC_PASSWORD)
#   PLC_SECRET_RUN   your secret manager's runner, put in front of the one process that reads the password,
#                    e.g. "op run --". Without it the variable must be set in the environment
#                    of the script (set it in your shell, never in the chat).
PXE_HOME=${PXE_HOME:-$HOME/.plcnext-engineer}
[ -f "$PXE_HOME/config" ] && . "$PXE_HOME/config"
PLC_HOST=${PLC_HOST:-192.168.1.10}
PLC_SECRET=${PLC_SECRET:-PLC_PASSWORD}
PLC_SECRET_RUN=${PLC_SECRET_RUN:-}
PXE_WORK=${PXE_WORK:-'C:\agentwork\plcnext'}            # work folder on the Engineer machine
if [ -z "${PXE_TRANSPORT:-}" ]; then
  case "$(uname -s)" in MINGW*|MSYS*|CYGWIN*) PXE_TRANSPORT=local;; *) PXE_TRANSPORT=proxmox;; esac
fi
PY=python3                                             # one that really runs: on Windows "python3" may be the Store's stub
for c in python3 python py; do "$c" -c 'import sys' >/dev/null 2>&1 && { PY=$c; break; }; done
export PXE_HOME PLC_HOST PLC_SECRET PLC_SECRET_RUN PXE_WORK PXE_TRANSPORT PY

secrets() {   # secrets NAME... : the values of those entries, one per line, on stdout (for a pipe, never for a terminal)
  local n miss=0
  if [ -n "$PLC_SECRET_RUN" ]; then
    $PLC_SECRET_RUN bash -c 'for n; do [ -n "${!n:-}" ] || exit 9; printf "%s\n" "${!n}"; done' _ "$@" 2>/dev/null \
      || { echo "secret: no value for one of: $* (through: $PLC_SECRET_RUN)" >&2; return 1; }
  else
    for n; do [ -n "${!n:-}" ] || { echo "secret: the environment variable $n is not set (see scripts/config.sh)" >&2; miss=1; }; done
    [ $miss = 0 ] || return 1
    for n; do printf '%s\n' "${!n}"; done
  fi
}
