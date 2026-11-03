param([Parameter(Mandatory=$true)][string]$Exe,[Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -Name CandidateKeys -Namespace UnderlineTest -MemberDefinition '[System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool PostMessage(System.IntPtr h,uint m,System.IntPtr w,System.IntPtr l); [System.Runtime.InteropServices.DllImport("user32.dll")] public static extern System.IntPtr GetForegroundWindow(); [System.Runtime.InteropServices.DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(System.IntPtr h,out uint p); public delegate bool EnumProc(System.IntPtr h,System.IntPtr p); [System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc cb,System.IntPtr ptr); [System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool IsWindowVisible(System.IntPtr h); [System.Runtime.InteropServices.DllImport("user32.dll", CharSet=System.Runtime.InteropServices.CharSet.Unicode)] public static extern int GetWindowTextLength(System.IntPtr h); [System.Runtime.InteropServices.DllImport("user32.dll")] public static extern bool SetForegroundWindow(System.IntPtr h); public static System.IntPtr[] Visible(uint pid){var list=new System.Collections.Generic.List<System.IntPtr>();EnumWindows(delegate(System.IntPtr h,System.IntPtr ignored){uint current;GetWindowThreadProcessId(h,out current);if(current==pid && IsWindowVisible(h) && GetWindowTextLength(h)>0)list.Add(h);return true;},System.IntPtr.Zero);return list.ToArray();}'
function Get-OwnWindow([int]$ownerPid, [IntPtr]$exclude=[IntPtr]::Zero) {
    $candidateProcess=Get-Process -Id $ownerPid -ErrorAction SilentlyContinue
    if($candidateProcess -and $exclude -eq [IntPtr]::Zero){
        $handle=$candidateProcess.MainWindowHandle
        if($handle -ne [IntPtr]::Zero){return [System.Windows.Automation.AutomationElement]::FromHandle($handle)}
    }
    foreach($visible in [UnderlineTest.CandidateKeys]::Visible([uint32]$ownerPid)){
        if($visible -ne $exclude){return [System.Windows.Automation.AutomationElement]::FromHandle($visible)}
    }
    $condition=[System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty,$ownerPid)
    $matches=[System.Windows.Automation.AutomationElement]::RootElement.FindAll(
        [System.Windows.Automation.TreeScope]::Children,$condition)
    foreach($element in $matches){
        $handle=[IntPtr]$element.Current.NativeWindowHandle
        if($handle -ne [IntPtr]::Zero -and $handle -ne $exclude -and -not $element.Current.IsOffscreen){return $element}
    }
}
function Send-OwnKey([IntPtr]$handle,[int]$ownerPid,[int]$key) {
    [uint32]$id=0
    [void][UnderlineTest.CandidateKeys]::GetWindowThreadProcessId($handle,[ref]$id)
    if($id -ne $ownerPid){throw 'Refused a keyboard event outside the candidate process'}
    if(-not [UnderlineTest.CandidateKeys]::PostMessage($handle,0x100,[IntPtr]$key,[IntPtr]1)){throw 'Key down failed'}
    if(-not [UnderlineTest.CandidateKeys]::PostMessage($handle,0x101,[IntPtr]$key,[IntPtr](-1073741823))){throw 'Key up failed'}
}
$env:QT_QPA_PLATFORM='windows'
$env:QT_ACCESSIBILITY='1'
$process=Start-Process -FilePath $Exe -WindowStyle Normal -PassThru
$rows=@()
try {
    $window=$null
    for($index=0;$index -lt 150 -and $null -eq $window;$index++){
        Start-Sleep -Milliseconds 100
        $window=Get-OwnWindow $process.Id
    }
    if($null -eq $window){throw "No visible candidate window for process $($process.Id); exited=$($process.HasExited)"}
    Write-Output ("Candidate window "+$window.Current.Name+" handle="+$window.Current.NativeWindowHandle)
    $conditions=[System.Windows.Automation.OrCondition]::new(
        [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty,'Edit project motor parameters'),
        [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::NameProperty,'编辑工程发动机参数'))
    $button=$window.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$conditions)
    if($null -eq $button){throw 'Motor properties button unavailable'}
    $button.SetFocus()
    $invoke=$button.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern)
    $invoke.Invoke()
    $dialog=$null
    for($index=0;$index -lt 100 -and $null -eq $dialog;$index++){
        Start-Sleep -Milliseconds 100
        $candidate=Get-OwnWindow $process.Id ([IntPtr]$window.Current.NativeWindowHandle)
        if($candidate -and $candidate.Current.NativeWindowHandle -ne $window.Current.NativeWindowHandle){$dialog=$candidate}
    }
    if($null -eq $dialog){throw 'Motor properties did not open'}
    $editCondition=[System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Edit)
    $edits=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,$editCondition)
    if($edits.Count -ne 7){throw "Expected seven motor fields, found $($edits.Count)"}
    [void][UnderlineTest.CandidateKeys]::SetForegroundWindow([IntPtr]$dialog.Current.NativeWindowHandle)
    $edits[0].SetFocus()
    for($index=0;$index -lt $edits.Count;$index++){
        if($index -gt 0){Send-OwnKey ([IntPtr]$dialog.Current.NativeWindowHandle) $process.Id 9}
        Start-Sleep -Milliseconds 90
        $focus=[System.Windows.Automation.AutomationElement]::FocusedElement
        if(-not [System.Windows.Automation.Automation]::Compare($focus,$edits[$index])){throw "Unexpected Tab target $index"}
        $rows+=@{index=$index;name=$focus.Current.Name;automation_id=$focus.Current.AutomationId}
    }
    Send-OwnKey ([IntPtr]$dialog.Current.NativeWindowHandle) $process.Id 27
    Start-Sleep -Milliseconds 200
    if((Get-OwnWindow $process.Id).Current.NativeWindowHandle -ne $window.Current.NativeWindowHandle){throw 'Esc did not return to the project'}
    [pscustomobject]@{exe=(Get-FileHash -LiteralPath $Exe).Hash;exit=0;tab_order=$rows;escape_returned=$true} |
        ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $Output -Encoding utf8
} finally {
    if(-not $process.HasExited){
        [void]$process.CloseMainWindow()
        if(-not $process.WaitForExit(3000)){Stop-Process -Id $process.Id -ErrorAction SilentlyContinue}
    }
}
