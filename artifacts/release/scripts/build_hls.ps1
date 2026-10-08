param([string]$Tools='C:\AMDDesignTools\2025.2', [string]$Stage='C:\temp\lesion_fpga', [switch]$Cosim)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
if ($Stage.Contains(' ')) { throw 'HLS stage must not contain spaces' }
New-Item -ItemType Directory -Force -Path "$Stage\hardware\hls" | Out-Null
Copy-Item -LiteralPath "$projectRoot\hardware\hls\lesion_accel.cpp","$projectRoot\hardware\hls\lesion_accel.hpp","$projectRoot\hardware\hls\testbench.cpp","$projectRoot\hardware\hls\build.tcl" -Destination "$Stage\hardware\hls" -Force
$env:LESION_COSIM=if($Cosim){'1'}else{'0'}
& "$Tools\Vitis\bin\vitis-run.bat" --mode hls --tcl "$Stage\hardware\hls\build.tcl" *> "$projectRoot\record\hls_build.log"
if ($LASTEXITCODE -ne 0) { throw "HLS failed; inspect record/hls_build.log" }
New-Item -ItemType Directory -Force -Path "$projectRoot\artifacts\hardware" | Out-Null
Copy-Item "$Stage\build\hls\lesion\solution1\syn\report\*" "$projectRoot\artifacts\hardware" -Force
Write-Output "HLS IP: $Stage\build\hls\lesion\solution1\impl\ip"
