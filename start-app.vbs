' firstep hidden launcher: runs start-app.bat with no visible console window.
' Double-click the firstep shortcut -> browser opens directly, no black window.
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
Set ws = CreateObject("WScript.Shell")
ws.Run "cmd /c """ & scriptDir & "\start-app.bat""", 0, False
