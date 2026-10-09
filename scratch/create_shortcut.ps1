$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [System.Environment]::GetFolderPath('Desktop')
$ShortcutPath = Join-Path $Desktop "Antigrav Bot.lnk"
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "c:\Users\dakot\Desktop\Antigrav\screen_monitor_bot\.venv\Scripts\pythonw.exe"
$Shortcut.Arguments = "`"c:\Users\dakot\Desktop\Antigrav\screen_monitor_bot\main.py`" --gui"
$Shortcut.WorkingDirectory = "c:\Users\dakot\Desktop\Antigrav\screen_monitor_bot"
$Shortcut.IconLocation = "c:\Users\dakot\Desktop\Antigrav\screen_monitor_bot\assets\bot_icon.ico,0"
$Shortcut.Description = "Antigrav Rotation Bot & Prioritization Engine"
$Shortcut.Save()

Write-Host "Shortcut created successfully at: $ShortcutPath"
Write-Host "Exists: $(Test-Path $ShortcutPath)"
