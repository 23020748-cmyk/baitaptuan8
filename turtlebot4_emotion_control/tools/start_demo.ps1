param([string]$Python = "$env:USERPROFILE\miniconda3\python.exe")
$ErrorActionPreference = 'Stop'
$workspacePath = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent
$parts = $workspacePath.TrimStart('\').Split('\')
if ($parts[0] -notin @('wsl.localhost', 'wsl$')) { throw 'Run this script from the WSL workspace path.' }
$distro = $parts[1]
$linuxWorkspace = '/' + (($parts | Select-Object -Skip 2) -join '/')
$runtimeDir = Join-Path $env:USERPROFILE 'Downloads\turtlebot4_emotion_runtime'
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null

# Stop this demo's camera and ROS processes before creating a new session.
$oldCameras = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
    $_.CommandLine -match 'windows_camera_bridge.py' -and $_.CommandLine -match 'turtlebot4_emotion_runtime'
}
$oldCameras | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
& wsl.exe -d $distro --exec /usr/bin/python3 "$linuxWorkspace/src/turtlebot4_emotion_control/tools/stop_demo_processes.py"
if ($LASTEXITCODE -ne 0) { throw 'Could not stop the previous ROS session.' }
& $Python "$PSScriptRoot\download_models.py" --model-dir "$runtimeDir\models"
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the expression models.' }

$cameraProcess = Start-Process -FilePath $Python -ArgumentList @(
    "$PSScriptRoot\windows_camera_bridge.py", '--output', "$runtimeDir\camera.frame", '--fps', '15'
) -WindowStyle Hidden -RedirectStandardOutput "$runtimeDir\camera_stdout.log" -RedirectStandardError "$runtimeDir\camera_stderr.log" -PassThru
$cameraProcess.Id | Set-Content -LiteralPath "$runtimeDir\camera.pid"
$linuxRuntime = '/mnt/' + $runtimeDir.Substring(0,1).ToLower() + $runtimeDir.Substring(2).Replace('\','/')
$launcher = Start-Process -FilePath 'wsl.exe' -ArgumentList @(
    '-d', $distro, '--exec', '/bin/bash',
    "$linuxWorkspace/src/turtlebot4_emotion_control/tools/run_demo.sh",
    "camera_source:=file://$linuxRuntime/camera.frame", "model_dir:=$linuxRuntime/models", 'gui:=false'
) -WindowStyle Hidden -RedirectStandardOutput "$runtimeDir\demo_stdout.log" -RedirectStandardError "$runtimeDir\demo_stderr.log" -PassThru
$launcher.Id | Set-Content -LiteralPath "$runtimeDir\launcher.pid"
Write-Output "Started one webcam + Gazebo session. Camera PID=$($cameraProcess.Id), launcher PID=$($launcher.Id)"
