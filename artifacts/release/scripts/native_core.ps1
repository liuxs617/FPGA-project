$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
New-Item -ItemType Directory -Force "$projectRoot\build\native" | Out-Null
& 'C:\mingw64\bin\g++.exe' -O2 -std=c++14 -shared "$projectRoot\hardware\hls\lesion_accel.cpp" -o "$projectRoot\build\native\lesion.dll"
if ($LASTEXITCODE -ne 0) {throw 'Native core compilation failed'}
& 'C:\mingw64\bin\g++.exe' -O2 -std=c++14 "$projectRoot\hardware\hls\lesion_accel.cpp" "$projectRoot\hardware\hls\testbench.cpp" -o "$projectRoot\build\native\smoke.exe"
if ($LASTEXITCODE -ne 0) {throw 'Testbench compilation failed'}
& "$projectRoot\build\native\smoke.exe"
if ($LASTEXITCODE -ne 0) {throw 'Native testbench failed'}
