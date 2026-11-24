#!/usr/bin/env bash
# plc-mqtt.sh <broker ip> <topic> [client id] [port] - point the controller's own MQTT client (firmware 2024.0 and
# later) at a broker, then reboot the controller (the settings file is read at start only; 2.5 minutes).
# plc-mqtt.sh off - back to the factory file (no MQTT), reboot.
#
# What gets published: program variables declared { OutputPort, PROFICLOUD }, all in one JSON message on <topic>,
# once a second. Plain TCP, no user: for a bench network. Findings, section MQTT. Uses plc-ssh.sh for the shell.
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd); C=/opt/plcnext/projects/Default/Services/ProfiCloudV3/ProfiCloudV3.config
if [ "${1:-}" = off ]; then
  "$S/plc-ssh.sh" --sudo "[ -f $C.factory ] && cp $C.factory $C && echo 'factory file back'; sudo -S -p : /sbin/reboot"; exit 0
fi
H=${1:?usage: plc-mqtt.sh <broker ip> <topic> [client id] [port] | off}; T=${2:?topic}; ID=${3:-plcnext}; P=${4:-1883}
case "$H$T$ID$P" in *[!A-Za-z0-9_./-]*) echo "plain letters, digits and . _ / - only" >&2; exit 1;; esac
"$S/plc-ssh.sh" --sudo "set -e
[ -f $C.factory ] || cp -p $C $C.factory
sed -e 's|<ProfiCloud enabled=\"false\"|<ProfiCloud enabled=\"true\" location=\"Mqtt\" anycloudTls=\"false\" anycloudHost=\"$H\" anycloudPort=\"$P\" anycloudPath=\"\" anycloudClientId=\"$ID\" anycloudUsername=\"\" anycloudPassword=\"\" anycloudMqttTopic=\"$T\"|' \
    -e 's|<TimeSeriesData enabled=\"false\"|<TimeSeriesData enabled=\"true\"|' $C.factory > /tmp/pc.config
grep -c 'location=\"Mqtt\"' /tmp/pc.config >/dev/null && cp /tmp/pc.config $C && echo \"mqtt: $H:$P topic $T client $ID, rebooting\"
sudo -S -p : /sbin/reboot"
