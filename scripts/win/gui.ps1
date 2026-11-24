# gui.ps1 - mouse and keyboard in the desktop session. Commands, one per argument:
#   click x y | dclick x y | drag x1 y1 x2 y2 | rclick x y | move x y | keys <SendKeys string> | text <literal> | sleep <ms> | activate <title part> | minimize <process name> | windows
Add-Type -A System.Windows.Forms
Add-Type @'
using System; using System.Runtime.InteropServices;
public class Gui {
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int c);
 public static void Click(int x,int y,bool right,int n){ SetCursorPos(x,y); System.Threading.Thread.Sleep(80); for(int i=0;i<n;i++){ mouse_event(right?8u:2u,0,0,0,UIntPtr.Zero); mouse_event(right?16u:4u,0,0,0,UIntPtr.Zero); System.Threading.Thread.Sleep(90);} }
}
'@
[void][Gui]::SetProcessDPIAware()
foreach($c in $args){
  $p = $c -split ' ',2; $a = if($p.Count -gt 1){$p[1]}else{''}
  switch($p[0]){
    'click'  { $x,$y = $a -split ' '; [Gui]::Click([int]$x,[int]$y,$false,1) }
    'dclick' { $x,$y = $a -split ' '; [Gui]::Click([int]$x,[int]$y,$false,2) }
    'rclick' { $x,$y = $a -split ' '; [Gui]::Click([int]$x,[int]$y,$true,1) }
    'drag'   { $x1,$y1,$x2,$y2 = $a -split ' ' | % { [int]$_ }; [void][Gui]::SetCursorPos($x1,$y1); Start-Sleep -Milliseconds 150; [Gui]::mouse_event(2,0,0,0,[UIntPtr]::Zero); foreach($i in 1..12){ [void][Gui]::SetCursorPos([int]($x1+($x2-$x1)*$i/12),[int]($y1+($y2-$y1)*$i/12)); Start-Sleep -Milliseconds 40 }; Start-Sleep -Milliseconds 200; [Gui]::mouse_event(4,0,0,0,[UIntPtr]::Zero) }
    'move'   { $x,$y = $a -split ' '; [void][Gui]::SetCursorPos([int]$x,[int]$y) }
    'keys'   { [Windows.Forms.SendKeys]::SendWait($a) }
    'text'   { [Windows.Forms.SendKeys]::SendWait(($a -replace '([+^%~(){}\[\]])','{$1}')) }
    'sleep'  { Start-Sleep -Milliseconds ([int]$a) }
    'activate' { $w = Get-Process | ? { $_.MainWindowTitle -like "*$a*" } | select -First 1; if($w){ [void][Gui]::SetForegroundWindow($w.MainWindowHandle); "activated $($w.MainWindowTitle)" } else { "no window like $a" } }
    'minimize' { Get-Process $a -ea 0 | ? { $_.MainWindowHandle -ne 0 } | % { [void][Gui]::ShowWindow($_.MainWindowHandle,6) } }
    'windows' { Get-Process | ? { $_.MainWindowTitle } | % { "$($_.ProcessName): $($_.MainWindowTitle)" } }
    default  { "unknown command: $c" }
  }
  Start-Sleep -Milliseconds 150
}
