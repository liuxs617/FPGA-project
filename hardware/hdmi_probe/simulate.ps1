$ErrorActionPreference='Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$vivado='C:/AMDDesignTools/2025.2/Vivado/bin'
Push-Location $root
try {
    $sources=@(Get-ChildItem third_party/hdl-util-hdmi/src/*.sv |
        Where-Object { $_.Name -notin @('serializer.sv','packet_picker.sv') } |
        ForEach-Object FullName)
    & "$vivado/xvlog.bat" -sv @sources hardware/hdmi_probe/packet_picker.sv hardware/hdmi_probe/protocol_tb.sv
    if($LASTEXITCODE -ne 0){throw 'HDL compile failed'}
    & "$vivado/xelab.bat" protocol_tb -s hdmi_protocol_sim -timescale 1ns/1ps
    if($LASTEXITCODE -ne 0){throw 'Simulation elaboration failed'}
    $result = & "$vivado/xsim.bat" hdmi_protocol_sim -runall 2>&1
    $result | Set-Content record/sessions/20260930_hdmi/protocol_sim.log
    if(($result -join "`n") -notmatch 'HDMI_PROTOCOL_PASS'){throw 'HDMI protocol test failed'}
    $result | Select-String 'HDMI_PROTOCOL_PASS'
} finally {Pop-Location}
