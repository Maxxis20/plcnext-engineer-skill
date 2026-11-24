# timer.ps1 - stopwatch shown over the taskbar clock (bottom right of the primary screen), always on top, never
# takes focus. Counts from its own start, plus -Offset seconds (to go on from an earlier reading). A file timer.stop
# beside it freezes the reading. Started by Timer-Start.
param([double]$Offset = 0)
Add-Type -AssemblyName System.Windows.Forms, System.Drawing
Add-Type -ReferencedAssemblies System.Windows.Forms, System.Drawing @"
using System; using System.Windows.Forms; using System.Runtime.InteropServices;
public class NoActForm : Form {
  protected override bool ShowWithoutActivation { get { return true; } }
  protected override CreateParams CreateParams { get { CreateParams p = base.CreateParams; p.ExStyle |= 0x08000000 | 0x00000008 | 0x00000080; return p; } }
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  public void Raise() { SetWindowPos(Handle, new IntPtr(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010); }
}
"@
[void][NoActForm]::SetProcessDPIAware()
$stop = Join-Path $PSScriptRoot 'timer.stop'; Remove-Item $stop -ErrorAction SilentlyContinue
$s = [Windows.Forms.Screen]::PrimaryScreen.Bounds; $w = 132; $h = $s.Height - [Windows.Forms.Screen]::PrimaryScreen.WorkingArea.Height; if ($h -lt 30) { $h = 48 }
$f = New-Object NoActForm; $f.FormBorderStyle = 'None'; $f.StartPosition = 'Manual'; $f.ShowInTaskbar = $false; $f.TopMost = $true
$f.BackColor = [Drawing.Color]::FromArgb(20, 20, 20); $f.Bounds = New-Object Drawing.Rectangle(($s.Width - $w), ($s.Height - $h), $w, $h)
$l = New-Object Windows.Forms.Label; $l.Dock = 'Fill'; $l.TextAlign = 'MiddleCenter'; $l.ForeColor = [Drawing.Color]::FromArgb(61, 205, 88)
$l.Font = New-Object Drawing.Font('Consolas', 19, [Drawing.FontStyle]::Bold); $l.Text = '00:00.0'; $f.Controls.Add($l)
$sw = [Diagnostics.Stopwatch]::StartNew()
$t = New-Object Windows.Forms.Timer; $t.Interval = 100
$t.Add_Tick({
  if ($sw.IsRunning -and (Test-Path $stop)) { $sw.Stop(); $l.ForeColor = [Drawing.Color]::White }
  $e = $sw.Elapsed + [TimeSpan]::FromSeconds($Offset); $l.Text = '{0:00}:{1:00}.{2}' -f [int][Math]::Floor($e.TotalMinutes), $e.Seconds, [int][Math]::Floor($e.Milliseconds / 100)
  $f.Raise()
})
$t.Start(); [Windows.Forms.Application]::Run($f)
