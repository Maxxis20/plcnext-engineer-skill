#!/usr/bin/env bash
# plc-opcua-client.sh <program dir> - put the OPC UA client connections of program.json ("opcua_client", connections
# with "password_secret") on the controller as the firmware's own configuration file, then restart the runtime.
# For connections whose password must not stand in a project file.
#
# File on the controller: /opt/plcnext/projects/Default/Services/OpcUA/Modules/Client/Configs/clientconnections.xml
# (the form Engineer compiles a project's client connections to). The passwords go secret store -> stdin of one
# process on the Engineer machine -> stdin of ssh -> that file (mode 640). Never printed, never in argv, on no other disk.
#   PLC_HOST, PLC_SECRET (the controller's admin password) as for plc-ssh.sh; "password_secret" of a connection is
#   looked up the same way (scripts/config.sh).   --remove: take the file away
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd); . "$S/config.sh"; PLC=$PLC_HOST
F=/opt/plcnext/projects/Default/Services/OpcUA/Modules/Client/Configs/clientconnections.xml
if [ "${1:-}" = --remove ]; then
  "$S/plc-ssh.sh" --sudo "rm -f $F; sudo -S -p : /bin/systemctl restart plcnext 2>/dev/null; sleep 40; systemctl is-active plcnext"; exit; fi
DIR=${1:?usage: plc-opcua-client.sh <program dir>}
XML=$("$PY" - "$DIR/program.json" <<'PY'
import json, sys
spec = json.load(open(sys.argv[1]))["opcua_client"]
ns = "http://phoenixcontact.com/OpcUA/PLCnext/GlobalDataSpace/"
mode = {"SignAndEncrypt": "SignAndEncrypt_3", "Sign": "Sign_2", "None": "None_1"}
index = {c["name"]: n for n, c in enumerate(spec["connections"], start=1)}
x = ['<?xml version="1.0" encoding="utf-8"?>',
     '<eUAClientConfigurationDocument xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:uax="http://opcfoundation.org/UA/2008/02/Types.xsd" xmlns="http://phoenixcontact.com/OpcUA/PLCnext/UAClientConfig/Types.xsd">',
     ' <eUAClientConfiguration>', '  <Name>ClientConnectionsConfiguration</Name>',
     '  <NamespaceArray><uax:String>%s</uax:String></NamespaceArray>' % ns, '  <ServerConnections>']
for n, c in enumerate(spec["connections"], start=1):
    x += ['   <eUAClientServerConnection>', '    <EncodingMask>3</EncodingMask>',
          '    <Endpoint><uax:EndpointUrl>%s</uax:EndpointUrl><uax:SecurityMode>%s</uax:SecurityMode></Endpoint>'
          % (c["url"], mode[c.get("security_mode", "SignAndEncrypt")]),
          '    <UserTokenType>UserName_1</UserTokenType>', '    <UserName>%s</UserName>' % c["user"],
          '    <Password>@@PW@@</Password>', '   </eUAClientServerConnection>']
x += ['  </ServerConnections>', '  <VariableGroups>']
for g in spec["groups"]:
    x += ['   <eUAClientVariableGroup>', '    <GroupType>%s</GroupType>' % {"Subscribe": "Subscribe_0", "Write": "Write_1"}[g["type"]],
          '    <CycleTime>%d</CycleTime>' % g.get("cycle_ms", 500), '    <NodeMappings>']
    for local, remote in g["map"].items():
        x.append('     <eUAClientNodeMapping><LocalVariable><uax:Identifier>ns=1;s=Arp.Plc.Eclr/%s</uax:Identifier></LocalVariable>'
                 '<RemoteVariableDescriptor><EncodingMask>2</EncodingMask><ServerIndex>%d</ServerIndex><NodeId><uax:Identifier>ns=1;s=Arp.Plc.Eclr/%s'
                 '</uax:Identifier></NodeId></RemoteVariableDescriptor></eUAClientNodeMapping>' % (local, index[g["server"]], remote))
    x += ['    </NodeMappings>', '   </eUAClientVariableGroup>']
x += ['  </VariableGroups>', ' </eUAClientConfiguration>', '</eUAClientConfigurationDocument>']
print("\n".join(x))
PY
)
SECRETS=$("$PY" -c 'import json,sys; print(" ".join(c["password_secret"] for c in json.load(open(sys.argv[1]))["opcua_client"]["connections"]))' "$DIR/program.json")
read -r -d '' REMOTE <<REOF || true
esc() { local s=\$1 o= c i; for ((i=0; i<\${#s}; i++)); do c=\${s:i:1}; case "\$c" in '&') o+='&amp;';; '<') o+='&lt;';; '>') o+='&gt;';; *) o+=\$c;; esac; done; printf '%s' "\$o"; }
N=$(echo $SECRETS | wc -w | tr -d " "); PWS=(); for ((k=0; k<N; k++)); do IFS= read -r p; PWS+=("\$(esc "\${p%\$'\\r'}")"); done
umask 027; k=0
while IFS= read -r line; do line=\${line%\$'\\r'}
  case "\$line" in *@@PW@@*) printf '%s%s%s\\n' "\${line%%@@PW@@*}" "\${PWS[k]}" "\${line#*@@PW@@}"; k=\$((k+1));; *) printf '%s\\n' "\$line";; esac
done > $F
chmod 640 $F; echo "written: \$(wc -l < $F) lines, \$(grep -c '<Password>' $F) connection(s), empty passwords: \$(grep -c '<Password></Password>' $F)"
REOF
CMD_B64=$(printf '%s' "$REMOTE" | base64 | tr -d '\n')
read -r -d '' PS <<PSEOF || true
\$all = [Console]::In.ReadToEnd(); \$i = \$all.IndexOf("\`n"); \$env:PLCPW = \$all.Substring(0, \$i).TrimEnd("\`r"); \$rest = \$all.Substring(\$i + 1)
\$d = '$PXE_WORK\\run'; New-Item -ItemType Directory -Force \$d | Out-Null
Set-Content "\$d\\askpass.cmd" '@powershell -NoProfile -Command "[Console]::Out.Write(\$env:PLCPW)"' -Encoding ASCII
\$env:SSH_ASKPASS = "\$d\\askpass.cmd"; \$env:SSH_ASKPASS_REQUIRE = 'force'; \$env:DISPLAY = 'x'
\$o = '-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=NUL','-o','LogLevel=ERROR','-o','ConnectTimeout=8','-o','PubkeyAuthentication=no','-o','NumberOfPasswordPrompts=1'
\$rest | & ssh.exe @o admin@$PLC 'echo $CMD_B64 | base64 -d > /tmp/.plc-cmd.sh; bash /tmp/.plc-cmd.sh; rm -f /tmp/.plc-cmd.sh' 2>&1 | Out-String
PSEOF
secrets "$PLC_SECRET" $SECRETS >/dev/null || exit 1
{ secrets "$PLC_SECRET" $SECRETS; printf '%s\n' "$XML"; } | "$S/vm.sh" pipe 60 "$PS"
"$S/plc-ssh.sh" --sudo 'sudo -S -p : /bin/systemctl restart plcnext 2>/dev/null; sleep 45; systemctl is-active plcnext; grep -a "OpcUAServer.Client.Internal.RemoteSession" /opt/plcnext/logs/Arp.log | tail -3 | cut -c1-230' 2>&1 | grep -v 'ssh.exe\|At line\|~~~\|Category\|FullyQ\|PLCPW'
