# wins.ps1 - all visible top-level windows of the desktop session: process, class, rectangle, title
Add-Type @'
using System; using System.Text; using System.Runtime.InteropServices; using System.Collections.Generic;
public class WinList { public delegate bool CB(IntPtr h, IntPtr l);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
 [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
 [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 public static List<string> All(){ var r=new List<string>(); IntPtr fg=GetForegroundWindow(); EnumWindows((h,l)=>{ if(!IsWindowVisible(h)) return true; uint p; GetWindowThreadProcessId(h,out p); var t=new StringBuilder(256); var c=new StringBuilder(256); GetWindowText(h,t,256); GetClassName(h,c,256); RECT q; GetWindowRect(h,out q); if(q.R-q.L<2) return true; string n="?"; try{ n=System.Diagnostics.Process.GetProcessById((int)p).ProcessName; }catch{} r.Add((h==fg?"* ":"  ")+n+" ["+q.L+","+q.T+" "+(q.R-q.L)+"x"+(q.B-q.T)+"] "+c+" | "+t); return true; }, IntPtr.Zero); return r; } }
'@
[WinList]::All()
