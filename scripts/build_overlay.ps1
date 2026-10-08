param([string]$Tools='C:\AMDDesignTools\2025.2',[string]$Stage='C:\temp\lesion_fpga')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Copy-Item "$projectRoot\hardware\vivado\*.tcl" "$Stage\hardware\vivado" -Force
& "$Tools\Vivado\bin\vivado.bat" -mode batch -source "$Stage\hardware\vivado\build.tcl" -nolog -nojournal *> "$projectRoot\record\vivado_build.log"
$vivadoExit=$LASTEXITCODE
Copy-Item "$Stage\build\*.rpt" "$projectRoot\artifacts\hardware" -Force -ErrorAction SilentlyContinue
if($vivadoExit -ne 0){throw 'Vivado failed: record/vivado_build.log'}
Copy-Item "$Stage\release\*" "$projectRoot\artifacts\hardware" -Force
& "$projectRoot\.venv\Scripts\python.exe" "$projectRoot\scripts\finalize_hardware.py"
if($LASTEXITCODE -ne 0){throw 'Hardware manifest validation failed'}
