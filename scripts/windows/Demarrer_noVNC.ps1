param(
    [ValidatePattern('^[A-Za-z0-9.:-]+$')]
    [string]$PiAddress = '172.20.10.3',
    [ValidatePattern('^[a-z_][a-z0-9_-]*$')]
    [string]$PiUser = 'pi-os'
)
$ErrorActionPreference = 'Stop'
$keyPath = Join-Path $env:USERPROFILE '.ssh\id_ed25519_novnc'
$sshExe = (Get-Command ssh.exe -ErrorAction Stop).Source
$logPath = Join-Path $PSScriptRoot 'derniere_erreur_ssh.log'
$outputPath = Join-Path $PSScriptRoot 'sortie_ssh.log'
$page = 'http://127.0.0.1:16080/vnc.html?autoconnect=true&reconnect=true&reconnect_delay=3000&resize=scale'
$created = $false
$mutex = [System.Threading.Mutex]::new($true, 'Local\noVNC-Pi-Automatique', [ref]$created)
if (-not $created) {
    Write-Host 'Le lanceur noVNC est deja actif dans cette session Windows.'
    $mutex.Dispose()
    exit 0
}
$tunnel = $null

function Test-VncReady {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $connection = $client.ConnectAsync('127.0.0.1', 16081)
        if (-not $connection.Wait(1500)) { return $false }
        $connection.GetAwaiter().GetResult()
        $networkStream = $client.GetStream()
        $networkStream.ReadTimeout = 2000
        $buffer = New-Object byte[] 12
        $received = 0
        while ($received -lt 12) {
            $count = $networkStream.Read($buffer, $received, 12 - $received)
            if ($count -eq 0) { return $false }
            $received += $count
        }
        return ([System.Text.Encoding]::ASCII.GetString($buffer) -match '^RFB [0-9]{3}\.[0-9]{3}')
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

try {
    if (-not (Test-Path -LiteralPath $keyPath)) {
        throw 'Cree la cle id_ed25519_novnc et ajoute-la a ssh-agent avant de lancer ce script.'
    }
    Write-Host "Attente de $PiUser@$PiAddress. Laisse ce lanceur ouvert (il peut etre reduit)."
    Write-Host "Les erreurs SSH sont disponibles dans $logPath. Ctrl+C pour arreter."
    while ($true) {
        $occupied = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
            Where-Object { $_.Port -eq 16080 -or $_.Port -eq 16081 }
        if ($occupied) {
            Write-Host 'Ports locaux 16080/16081 occupes. Ferme un ancien tunnel ou consulte les ports Windows.'
            Start-Sleep -Seconds 5
            continue
        }
        # Arguments construits sans shell ; seuls hostname/utilisateur valides sont acceptes.
        $sshArguments = '-N -T -i "' + $keyPath + '"' +
            ' -o BatchMode=yes -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes' +
            ' -o ExitOnForwardFailure=yes -o ConnectTimeout=5' +
            ' -o ServerAliveInterval=15 -o ServerAliveCountMax=2 -o ForwardAgent=no' +
            ' -L 127.0.0.1:16080:127.0.0.1:6080 -L 127.0.0.1:16081:127.0.0.1:5900 ' +
            $PiUser + '@' + $PiAddress
        $tunnel = Start-Process -FilePath $sshExe -ArgumentList $sshArguments -PassThru -WindowStyle Hidden `
            -RedirectStandardError $logPath -RedirectStandardOutput $outputPath
        $opened = $false
        while (-not $tunnel.HasExited) {
            if (-not $opened -and (Test-VncReady)) {
                try {
                    $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:16080/vnc.html' -TimeoutSec 2
                    if ($response.StatusCode -eq 200 -and $response.Content -match 'noVNC') {
                        Start-Process -FilePath $page | Out-Null
                        $opened = $true
                        Write-Host 'Bureau disponible : navigateur ouvert, tunnel SSH actif.'
                    }
                } catch {
                    # Le serveur web peut etre pret quelques secondes apres VNC.
                }
            }
            Start-Sleep -Seconds 2
            $tunnel.Refresh()
        }
        $tunnel.Dispose()
        $tunnel = $null
        Write-Host 'Raspberry inaccessible ou tunnel interrompu. Nouvelle tentative dans 5 secondes.'
        Start-Sleep -Seconds 5
    }
} finally {
    if ($null -ne $tunnel) {
        if (-not $tunnel.HasExited) { $tunnel.Kill() }
        $tunnel.Dispose()
    }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
