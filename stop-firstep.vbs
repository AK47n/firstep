' firstep stop helper (hidden): kills the process listening on port 8000.
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set ws = CreateObject("WScript.Shell")
ws.Run "cmd /c """ & scriptDir & "\stop-firstep.bat""", 0, False
