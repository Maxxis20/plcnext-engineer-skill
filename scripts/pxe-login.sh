#!/usr/bin/env bash
# pxe-login.sh [user] - fill Engineer's "Secure device login" dialog (it must be showing: press Connect first) from
# the secret store, tick "Remember credentials" and press OK. Needed once per controller; later connects come
# filled.
#
# The password goes: environment (or your secret manager, scripts/config.sh) -> stdin of one PowerShell process on the Engineer machine ->
# a named pipe (readable by the desktop user, open for one read, at most 60 s) -> keystrokes into the password
# box. It is never printed, never in argv, never on disk.
# Which password: scripts/config.sh (PLC_SECRET, PLC_SECRET_RUN).
set -euo pipefail
S=$(cd "$(dirname "$0")" && pwd); . "$S/config.sh"; USER_=${1:-admin}
read -r -d '' PS <<PSEOF || true
\$pw = [Console]::In.ReadToEnd().TrimEnd("\`r","\`n")
\$sec = New-Object IO.Pipes.PipeSecurity
\$sec.AddAccessRule((New-Object IO.Pipes.PipeAccessRule('${PLCVM_USER:-INTERACTIVE}','Read,Synchronize','Allow')))
\$sec.AddAccessRule((New-Object IO.Pipes.PipeAccessRule([Security.Principal.WindowsIdentity]::GetCurrent().Name,'FullControl','Allow')))
\$sec.AddAccessRule((New-Object IO.Pipes.PipeAccessRule('SYSTEM','FullControl','Allow')))
\$s = New-Object IO.Pipes.NamedPipeServerStream('pxelogin',[IO.Pipes.PipeDirection]::Out,1,[IO.Pipes.PipeTransmissionMode]::Byte,[IO.Pipes.PipeOptions]::Asynchronous,0,0,\$sec)
\$r = \$s.BeginWaitForConnection(\$null,\$null)
if (\$r.AsyncWaitHandle.WaitOne(60000)) { \$s.EndWaitForConnection(\$r); \$b=[Text.Encoding]::UTF8.GetBytes(\$pw); \$s.Write(\$b,0,\$b.Length); \$s.WaitForPipeDrain(); 'sent' } else { 'nobody read it' }
\$s.Dispose()
PSEOF
secrets "$PLC_SECRET" >/dev/null || exit 1
secrets "$PLC_SECRET" | "$S/vm.sh" pipe 90 "$PS" | sed 's/^/pipe: /' >&2 &
sleep 4
"$S/vm.sh" ui - 60 <<UIEOF
Add-Type -A UIAutomationClient,UIAutomationTypes,System.Windows.Forms
\$AE=[Windows.Automation.AutomationElement]; \$TS=[Windows.Automation.TreeScope]
function ById(\$id){ \$AE::RootElement.FindFirst(\$TS::Descendants,(New-Object Windows.Automation.PropertyCondition(\$AE::AutomationIdProperty,\$id))) }
Add-Type @'
using System; using System.Runtime.InteropServices;
public class LMouse { [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y); [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
 public static void Click(int x,int y){ SetCursorPos(x,y); System.Threading.Thread.Sleep(150); mouse_event(2,0,0,0,UIntPtr.Zero); mouse_event(4,0,0,0,UIntPtr.Zero); System.Threading.Thread.Sleep(300); } }
'@
function Mid(\$e){ \$r=\$e.Current.BoundingRectangle; [LMouse]::Click([int](\$r.Left+\$r.Width/2),[int](\$r.Top+\$r.Height/2)) }
\$pb = ById 'AID_PasswordBox'
if(-not \$pb){ 'login: no login dialog showing'; exit 1 }
\$c = New-Object IO.Pipes.NamedPipeClientStream('.','pxelogin',[IO.Pipes.PipeDirection]::In)
\$c.Connect(30000); \$pw = (New-Object IO.StreamReader(\$c)).ReadToEnd(); \$c.Dispose()
if(-not \$pw){ 'login: no password arrived'; exit 1 }
Mid (ById 'AID_Username'); [Windows.Forms.SendKeys]::SendWait('^a'); [Windows.Forms.SendKeys]::SendWait('$USER_')
Mid \$pb; [Windows.Forms.SendKeys]::SendWait('^a'); [Windows.Forms.SendKeys]::SendWait((\$pw -replace '([+^%~(){}\[\]])','{\$1}')); \$pw = \$null
\$cb = ById 'AID_RememberCredentials'; \$o=\$null
if(\$cb.TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern,[ref]\$o) -and \$o.Current.ToggleState -ne 'On'){ Mid \$cb }
Start-Sleep -Milliseconds 500
\$ok = ById 'AID_ButtonOK'
if(\$ok.Current.IsEnabled){ Mid \$ok; 'login: sent' } else { 'login: OK stays disabled' }
UIEOF
wait
