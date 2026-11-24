# disp.ps1 <w> <h>: set the desktop resolution of the current session
param([int]$w=1920,[int]$h=1080)
Add-Type -IgnoreWarnings @'
using System; using System.Runtime.InteropServices;
public class Disp {
 [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Ansi)] public struct DEVMODE { [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)] public string dmDeviceName; public short dmSpecVersion, dmDriverVersion, dmSize, dmDriverExtra; public int dmFields; public int dmPositionX, dmPositionY, dmDisplayOrientation, dmDisplayFixedOutput; public short dmColor, dmDuplex, dmYResolution, dmTTOption, dmCollate; [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)] public string dmFormName; public short dmLogPixels; public int dmBitsPerPel, dmPelsWidth, dmPelsHeight, dmDisplayFlags, dmDisplayFrequency, a,b,c,d,e,f,g,h; }
 [DllImport("user32.dll")] public static extern bool EnumDisplaySettings(string n, int i, ref DEVMODE d);
 [DllImport("user32.dll")] public static extern int ChangeDisplaySettings(ref DEVMODE d, int f);
 public static string Set(int w,int h){ DEVMODE d=new DEVMODE(); d.dmSize=(short)Marshal.SizeOf(d); for(int i=0;EnumDisplaySettings(null,i,ref d);i++){ if(d.dmPelsWidth==w&&d.dmPelsHeight==h&&d.dmBitsPerPel==32){ return "set rc="+ChangeDisplaySettings(ref d,1); } } return "mode not found"; }
}
'@
[Disp]::Set($w,$h)
