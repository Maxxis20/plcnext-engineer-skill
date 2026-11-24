# shot.ps1 <png> - screenshot of the whole primary screen (for the scripts running on this machine).
param([string]$out)
Add-Type -A System.Windows.Forms, System.Drawing
Add-Type 'using System.Runtime.InteropServices; public class ShotDpi { [DllImport("user32.dll")] public static extern bool SetProcessDPIAware(); }'
[void][ShotDpi]::SetProcessDPIAware()
$b = [Windows.Forms.Screen]::PrimaryScreen.Bounds
$bmp = New-Object Drawing.Bitmap $b.Width, $b.Height
$g = [Drawing.Graphics]::FromImage($bmp); $g.CopyFromScreen($b.Location, [Drawing.Point]::Empty, $b.Size); $g.Dispose()
$bmp.Save($out, [Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose(); $out
