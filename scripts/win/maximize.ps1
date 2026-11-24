# maximize.ps1 - restore and maximize the Engineer window (after a resolution change it keeps its old size)
Add-Type @'
using System; using System.Runtime.InteropServices;
public class SW { [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c); }
'@
$h=(Get-Process PLCNENG64).MainWindowHandle; [void][SW]::ShowWindow($h,9); Start-Sleep 1; [void][SW]::ShowWindow($h,3); 'maximized'
