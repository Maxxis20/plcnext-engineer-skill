# web.ps1 - a web page in its own browser window (no tabs, no address bar) over the other windows.
#   web.ps1 open <url> <x> <y> <w> <h>   show the page in a window at that place; an open window with the same url is
#                                        brought back and reloaded, not started again (no blank screen in between).
#                                        Prints "rect x y w h": where the page itself is on the screen.
#   web.ps1 back                         take the window out of the way (minimise); the page stays loaded
param([string]$cmd, [string]$url, [int]$x = 200, [int]$y = 150, [int]$w = 1200, [int]$h = 800)
Add-Type -A UIAutomationClient, UIAutomationTypes, System.Windows.Forms
Add-Type @'
using System; using System.Runtime.InteropServices;
public class WebWin {
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr a, int x, int y, int w, int hh, uint f);
 [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
 [DllImport("user32.dll")] public static extern void keybd_event(byte k, byte s, uint f, UIntPtr e);
 // Windows lets a background process take the foreground only right after input: tap Alt, then lift the window over the rest
 public static void Front(IntPtr h, int x, int y, int w, int hh){ keybd_event(0x12,0,0,UIntPtr.Zero); keybd_event(0x12,0,2,UIntPtr.Zero);
   SetWindowPos(h,(IntPtr)(-1),x,y,w,hh,0x0040); SetWindowPos(h,(IntPtr)(-2),x,y,w,hh,0x0040); SetForegroundWindow(h); }
}
'@
[void][WebWin]::SetProcessDPIAware()
# a Chromium browser that is installed (Edge is on every Windows 11), in a profile of its own: the windows of the
# person's own browser are never touched
$exe = @("${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe", "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
         "$env:ProgramFiles\Google\Chrome\Application\chrome.exe", "$env:ProgramFiles\BraveSoftware\Brave-Browser\Application\brave.exe") | ? { Test-Path $_ } | select -First 1
if (-not $exe) { 'no Chromium browser found (Edge, Chrome or Brave)'; exit 1 }
$run = Split-Path $PSCommandPath; $mark = "$run\web.url"; $prof = "$run\browser"; $name = [IO.Path]::GetFileNameWithoutExtension($exe)
function Ours { Get-CimInstance Win32_Process -Filter "Name='$name.exe'" | ? { $_.CommandLine -like "*$prof*" } | % { $_.ProcessId } }
function Win { $ids = @(Ours); Get-Process $name -ea 0 | ? { $_.MainWindowHandle -ne 0 -and $ids -contains $_.Id } | select -First 1 }
if ($cmd -eq 'back') { $p = Win; if ($p) { [void][WebWin]::ShowWindow($p.MainWindowHandle, 6); 'back' } else { 'no window' }; exit }
$p = Win; $same = (Test-Path $mark) -and ((Get-Content $mark -Raw).Trim() -eq $url)
if ($p -and -not $same) { Ours | % { Stop-Process -Id $_ -Force -ea 0 }; Start-Sleep 1; $p = $null }
if (-not $p) {
  Start-Process $exe "--app=$url --user-data-dir=`"$prof`" --no-first-run --no-default-browser-check --window-position=$x,$y --window-size=$w,$h --test-type --ignore-certificate-errors --disable-session-crashed-bubble --hide-crash-restore-bubble"
  Set-Content $mark $url
  for ($i = 0; $i -lt 40 -and -not $p; $i++) { Start-Sleep -Milliseconds 500; $p = Win }
  if (-not $p) { 'no browser window'; exit 1 }
  Start-Sleep 4
} else {
  [void][WebWin]::ShowWindow($p.MainWindowHandle, 9)
}
[WebWin]::Front($p.MainWindowHandle, $x, $y, $w, $h)
if ($same) { Start-Sleep -Milliseconds 300; [Windows.Forms.SendKeys]::SendWait('{F5}'); Start-Sleep 3 }
$root = [Windows.Automation.AutomationElement]::FromHandle($p.MainWindowHandle)
$doc = $null; for ($i = 0; $i -lt 6 -and -not $doc; $i++) { if ($i) { Start-Sleep 1 }; $doc = $root.FindFirst([Windows.Automation.TreeScope]::Descendants, (New-Object Windows.Automation.PropertyCondition([Windows.Automation.AutomationElement]::ControlTypeProperty, [Windows.Automation.ControlType]::Document))) }
if ($doc) { $r = $doc.Current.BoundingRectangle; "rect $([int]$r.X) $([int]$r.Y) $([int]$r.Width) $([int]$r.Height)" } else { "rect $($x+8) $($y+32) $($w-16) $($h-40)" }
