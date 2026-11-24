#!/usr/bin/env bash
# plc-backup.sh backup [name]          - the controller's project, settings and network files into a local archive
# plc-backup.sh restore <archive> [--force]   - put the project of such an archive back on a controller, restart
# plc-backup.sh check <archive>        - is an archive complete (checksum of the project as on the controller)
#
# backup: tar of /opt/plcnext (without logs), /etc/plcnext and /etc/systemd/network, read through the normal paths
#   (never from the overlay's storage /media/rfs/rw/upperdir: files come out empty there, without an error). Saved as
#   <work folder>/backup/<name or address-date>.tgz with a .info beside it (firmware, file count, checksum of the
#   project folder), then checked against that .info. About 3 MB, under a minute.
# restore: only the project (/opt/plcnext/projects/PCWE) is put back: the present one is moved aside as
#   PCWE.before-<date-time>, the runtime is restarted (a minute) and the checksum compared again. Refused when the
#   archive's firmware differs from the controller's (a project compiled for one firmware does not load on another;
#   --force to try anyway). Settings outside the project (services, network, users) are in the archive but are not
#   put back: take them out of it by hand if needed.
# Controller and password as for plc-ssh.sh (PLC_HOST, PLC_SECRET; scripts/config.sh). The firmware itself is not in
# a backup; admin cannot read about 10 entries (keys, the user database): they are left out with a note.
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd); . "$S/config.sh"
B="$PXE_HOME/backup"; mkdir -p "$B"
P=/opt/plcnext/projects/PCWE
SUM="cd $P && find . -type f -exec md5sum {} + | LC_ALL=C sort -k2 | md5sum | cut -c1-32; find . -type f | wc -l; find . -type f -size 0 | wc -l"
info() { "$S/plc-ssh.sh" "head -1 /etc/plcnext/arpversion | sed 's/^[^:]*: *//'; $SUM" | tr -d '\r' | grep -v '^$'; }
local_sum() {   # local_sum <archive>: the same three lines as the controller gives, computed from the archive
  "$PY" - "$1" <<'PY'
import sys, tarfile, hashlib
lines, n, empty = [], 0, 0
with tarfile.open(sys.argv[1]) as t:
    for m in t.getmembers():
        if m.isfile() and m.name.startswith("opt/plcnext/projects/PCWE/"):
            rel = "./" + m.name[len("opt/plcnext/projects/PCWE/"):]
            lines.append((rel.encode(), hashlib.md5(t.extractfile(m).read()).hexdigest()))
            n += 1; empty += m.size == 0
text = b"".join(h.encode() + b"  " + r + b"\n" for r, h in sorted(lines))
print(hashlib.md5(text).hexdigest()); print(n); print(empty)
PY
}
check() {   # check <archive>: compare with its .info
  local a=$1 want got; want=$(sed -n 2,4p "${a%.tgz}.info"); got=$(local_sum "$a")
  if [ "$want" = "$got" ]; then echo "check: ok ($(sed -n 3p "${a%.tgz}.info") project files, checksum $(sed -n 2p "${a%.tgz}.info" | cut -c1-12))"
  else echo "check: FAILED - archive does not match the controller (controller / archive: checksum, files, empty files):"; paste <(echo "$want") <(echo "$got"); return 1; fi
}
case "${1:-}" in
  backup)
    name=${2:-$PLC_HOST-$(date +%Y%m%d-%H%M)}; a="$B/$name.tgz"; w="$PXE_WORK\\backup\\$name.tgz"
    info > "${a%.tgz}.info"; [ "$(wc -l < "${a%.tgz}.info")" -ge 4 ] || { echo "backup: controller does not answer"; exit 1; }
    "$S/vm.sh" ps "New-Item -ItemType Directory -Force '$PXE_WORK\\backup' | Out-Null" >/dev/null
    "$S/plc-ssh.sh" --out "$w" 'cd / && tar czf - --exclude=opt/plcnext/logs opt/plcnext etc/plcnext etc/systemd/network 2>/tmp/.bk.err; grep -c "Permission denied" /tmp/.bk.err >&2; rm -f /tmp/.bk.err' >/dev/null 2>&1 || true
    "$S/vm.sh" get "$w" "$a"
    [ -s "$a" ] || { echo "backup: no archive arrived"; exit 1; }
    echo "backup: $a ($(du -k "$a" | cut -f1) kB), firmware $(head -1 "${a%.tgz}.info")"
    check "$a" ;;
  check) check "${2:?archive}" ;;
  restore)
    a=${2:?usage: plc-backup.sh restore <archive> [--force]}; [ -f "$a" ] || { echo "restore: no file $a"; exit 1; }
    [ -f "${a%.tgz}.info" ] || { echo "restore: ${a%.tgz}.info is missing (made by plc-backup.sh backup)"; exit 1; }
    check "$a" >/dev/null || { echo "restore: the archive does not match its .info; not used"; exit 1; }
    fw_a=$(head -1 "${a%.tgz}.info"); fw_c=$("$S/plc-ssh.sh" "head -1 /etc/plcnext/arpversion | sed 's/^[^:]*: *//'" | tr -d '\r' | head -1)
    [ "${fw_a%.*}" = "${fw_c%.*}" ] || [ "${3:-}" = --force ] || { echo "restore: archive is firmware $fw_a, controller $PLC_HOST has $fw_c: refused (--force to try)"; exit 1; }
    w="$PXE_WORK\\backup\\restore.tgz"; "$S/vm.sh" put "$a" "$w"
    stamp=$(date +%Y%m%d-%H%M%S)
    "$S/plc-ssh.sh" --in "$w" "set -e; rm -rf /tmp/.rs; mkdir /tmp/.rs; tar xzf - -C /tmp/.rs opt/plcnext/projects/PCWE
      [ -d /tmp/.rs$P ] || { echo 'restore: no project in the archive'; exit 1; }
      mv $P $P.before-$stamp && mv /tmp/.rs$P $P && chmod -R g+w $P && rm -rf /tmp/.rs
      echo \"restore: project in place, the one before is $P.before-$stamp\"" | tr -d '\r' | grep -v '^$'
    PLC_TIMEOUT=150 "$S/plc-ssh.sh" --sudo 'sudo -S -p "" /bin/systemctl restart plcnext' >/dev/null 2>&1 || true
    echo "runtime: $("$S/plc-ssh.sh" 'sleep 15; systemctl is-active plcnext' | tr -d '\r' | tail -1)"
    got=$("$S/plc-ssh.sh" "$SUM" | tr -d '\r' | grep -v '^$'); want=$(sed -n 2,4p "${a%.tgz}.info")
    if [ "$got" = "$want" ]; then echo "restore: ok, the project on $PLC_HOST matches the archive"
    else echo "restore: FAILED, the project on $PLC_HOST does not match the archive"; exit 1; fi
    bad=$("$S/plc-ssh.sh" "grep -a -c 'integrity check' /opt/plcnext/logs/Arp.log 2>/dev/null || true" | tr -d '\r' | tail -1)
    [ "${bad:-0}" = 0 ] || echo "restore: note: the runtime log mentions 'integrity check' ($bad lines): look at /opt/plcnext/logs/Arp.log" ;;
  *) sed -n 2,4p "$0"; exit 2 ;;
esac
