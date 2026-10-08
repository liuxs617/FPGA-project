param([string]$Tools='C:\AMDDesignTools\2025.2',[string]$Stage='C:\temp\lesion_fpga')
$ErrorActionPreference='Stop'
$projectRoot=Split-Path $PSScriptRoot -Parent
Push-Location "$Stage\upstream\ip\hls"
try {
  foreach($coreName in @('color_convert','pixel_pack','pixel_unpack')) {
    & "$Tools\Vitis\bin\vitis-run.bat" --mode hls --tcl "build_$coreName.tcl" *> "$projectRoot\record\video_$coreName.log"
    if($LASTEXITCODE -ne 0){throw "Video IP failed: $coreName"}
  }
} finally {Pop-Location}
