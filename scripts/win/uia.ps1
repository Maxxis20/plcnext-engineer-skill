# uia.ps1 - PLCnext Engineer controls by UI Automation (no screen positions). Commands, one per argument:
#   invoke <AutomationId>        press a button
#   state <AutomationId>         enabled / toggle state
#   find <regex>                 controls whose id, name or help text match: type, enabled, position, id, name
#   texts [regex]                visible text of the main window (Text and Edit controls), optionally filtered
#   wins                         top-level windows of the Engineer process (dialogs)
#   click <AutomationId> | dclick <AutomationId>   real mouse click in the middle of that control
#   press <regex>                real mouse click on the first enabled Button whose name or id matches
#   expand <regex>               expand the tree items whose id matches (PLANT and COMPONENTS trees)
#   wait <seconds> <regex>       wait until some control's id or name matches (prints it), else 'timeout'
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch {}   # names with umlauts survive a pipe
Add-Type -A UIAutomationClient,UIAutomationTypes
Add-Type @'
using System; using System.Runtime.InteropServices;
public class UMouse {
 [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y);
 [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 public static void Click(int x,int y,int n){ SetCursorPos(x,y); System.Threading.Thread.Sleep(120); for(int i=0;i<n;i++){ mouse_event(2,0,0,0,UIntPtr.Zero); mouse_event(4,0,0,0,UIntPtr.Zero); System.Threading.Thread.Sleep(90);} }
}
'@
$AE=[Windows.Automation.AutomationElement]; $TS=[Windows.Automation.TreeScope]
$p = Get-Process PLCNENG64 -ErrorAction SilentlyContinue | select -First 1
if(-not $p){ 'PLCnext Engineer is not running'; exit 1 }
$root=$AE::RootElement
$pc=New-Object Windows.Automation.PropertyCondition($AE::ProcessIdProperty,$p.Id)
function Tops { $root.FindAll($TS::Children,$pc) }
function ById($id){ foreach($w in Tops){ $e=$w.FindFirst($TS::Descendants,(New-Object Windows.Automation.PropertyCondition($AE::AutomationIdProperty,$id))); if($e){ return $e } } }
function Line($e){ $r=$e.Current.BoundingRectangle; "{0,-10} en={1,-5} [{2:f0},{3:f0} {4:f0}x{5:f0}] id='{6}' name='{7}'" -f $e.Current.ControlType.ProgrammaticName.Replace('ControlType.',''),$e.Current.IsEnabled,$r.Left,$r.Top,$r.Width,$r.Height,$e.Current.AutomationId,$e.Current.Name }
foreach($c in $args){
  $q = $c -split ' ',2; $a = if($q.Count -gt 1){$q[1]}else{''}
  switch($q[0]){
    'invoke' { $e=ById $a; if(-not $e){ "not found: $a" } elseif(-not $e.Current.IsEnabled){ "disabled: $a" } else {
                 $o=$null
                 if($e.TryGetCurrentPattern([Windows.Automation.InvokePattern]::Pattern,[ref]$o)){ $o.Invoke(); "invoked $a" }
                 elseif($e.TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern,[ref]$o)){ $o.Toggle(); "toggled $a" }
                 elseif($e.TryGetCurrentPattern([Windows.Automation.SelectionItemPattern]::Pattern,[ref]$o)){ $o.Select(); "selected $a" }
                 elseif($e.TryGetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$o)){ $o.Expand(); "expanded $a" }
                 else { "no pattern: $a" } } }
    'state'  { $e=ById $a; if(-not $e){ "not found: $a" } else { $o=$null; $t=''; if($e.TryGetCurrentPattern([Windows.Automation.TogglePattern]::Pattern,[ref]$o)){ $t=' toggle='+$o.Current.ToggleState }; (Line $e)+$t } }
    'find'   { foreach($w in Tops){ foreach($e in $w.FindAll($TS::Descendants,[Windows.Automation.Condition]::TrueCondition)){ if(($e.Current.AutomationId+'|'+$e.Current.Name+'|'+$e.Current.HelpText) -match $a){ Line $e } } } }
    'texts'  { foreach($w in Tops){ $cond=New-Object Windows.Automation.OrCondition((New-Object Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[Windows.Automation.ControlType]::Text)),(New-Object Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[Windows.Automation.ControlType]::Edit)))
                 foreach($e in $w.FindAll($TS::Descendants,$cond)){ $n=$e.Current.Name; $o=$null; if($e.TryGetCurrentPattern([Windows.Automation.ValuePattern]::Pattern,[ref]$o)){ $n=$n+' = '+$o.Current.Value }
                   if($n -and (-not $a -or $n -match $a) -and -not $e.Current.IsOffscreen){ $r=$e.Current.BoundingRectangle; "[{0:f0},{1:f0}] {2}" -f $r.Left,$r.Top,$n } } } }
    'wins'   { foreach($w in Tops){ Line $w } }
    { $_ -in 'click','dclick' } { $e=ById $a; if(-not $e){ "not found: $a" } else { [void][UMouse]::SetForegroundWindow($p.MainWindowHandle); $r=$e.Current.BoundingRectangle
                 if($e.Current.ControlType -eq [Windows.Automation.ControlType]::TreeItem){   # a tree row is as wide as the panel: aim at its label
                   $t=$e.FindFirst($TS::Descendants,(New-Object Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[Windows.Automation.ControlType]::Text)))
                   if($t){ $r=$t.Current.BoundingRectangle } }
                 [UMouse]::Click([int]($r.Left+[Math]::Min($r.Width/2,60)),[int]($r.Top+$r.Height/2),$(if($q[0] -eq 'dclick'){2}else{1})); "$($q[0]) $a" } }
    'press'  { $bc=New-Object Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[Windows.Automation.ControlType]::Button); $done=$false
               foreach($w in Tops){ foreach($e in $w.FindAll($TS::Descendants,$bc)){ if(-not $done -and $e.Current.IsEnabled -and (($e.Current.AutomationId -match $a) -or ($e.Current.Name -match $a))){ $r=$e.Current.BoundingRectangle
                 [UMouse]::Click([int]($r.Left+$r.Width/2),[int]($r.Top+$r.Height/2),1); "pressed $($e.Current.Name) $($e.Current.AutomationId)"; $done=$true } } }
               if(-not $done){ "no button: $a" } }
    'expand' { $tc=New-Object Windows.Automation.PropertyCondition($AE::ControlTypeProperty,[Windows.Automation.ControlType]::TreeItem)
               foreach($w in Tops){ foreach($e in $w.FindAll($TS::Descendants,$tc)){ if($e.Current.AutomationId -match $a){ $o=$null
                 if($e.TryGetCurrentPattern([Windows.Automation.ExpandCollapsePattern]::Pattern,[ref]$o)){ if($o.Current.ExpandCollapseState -ne 'Expanded'){ $o.Expand() }; "expanded $($e.Current.AutomationId)" } } } } }
    'wait'   { $w2=$a -split ' ',2; $end=(Get-Date).AddSeconds([int]$w2[0]); $hit=$null
               while(-not $hit -and (Get-Date) -lt $end){ foreach($w in Tops){ foreach($e in $w.FindAll($TS::Descendants,[Windows.Automation.Condition]::TrueCondition)){ if(($e.Current.AutomationId+'|'+$e.Current.Name) -match $w2[1]){ $hit=$e; break } }; if($hit){break}; if($w.Current.Name -match $w2[1]){ $hit=$w; break } }; if(-not $hit){ Start-Sleep -Milliseconds 700 } }
               if($hit){ Line $hit } else { 'timeout' } }
    default  { "unknown command: $c" }
  }
}
