param(
    [ValidatePattern('^[A-Za-z0-9.:-]+$')]
    [string]$PiAddress = '172.20.10.3',
    [ValidatePattern('^[a-z_][a-z0-9_-]*$')]
    [string]$PiUser = 'pi-os'
)
$ErrorActionPreference = 'Stop'
$launcher = Join-Path $PSScriptRoot 'Demarrer_noVNC.ps1'
if (-not (Test-Path -LiteralPath $launcher)) { throw 'Demarrer_noVNC.ps1 est absent.' }
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'Bureau Raspberry par SSH.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = (Get-Command powershell.exe).Source
$shortcut.Arguments = '-NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "' + $launcher +
    '" -PiAddress "' + $PiAddress + '" -PiUser "' + $PiUser + '"'
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.WindowStyle = 7
$shortcut.Description = 'Attend la Raspberry et ouvre noVNC par un tunnel SSH chiffre.'
$shortcut.Save()
Write-Host 'Demarrage automatique installe pour ta session Windows.'
Write-Host 'Ne deplace pas ce dossier. Pour retirer : Win+R, shell:startup, supprimer Bureau Raspberry par SSH.'
Start-Process -FilePath $shortcutPath
