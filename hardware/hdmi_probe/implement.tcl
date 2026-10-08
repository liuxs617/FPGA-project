set stage C:/temp/lesion_hdmi_probe
set runs $stage/project/hdmi_probe.runs
# Explicitly link the three successful OOC checkpoints. This avoids relying
# on Vivado's module-reference export cache for the custom video module.
open_checkpoint $runs/synth_1/probe_wrapper.dcp
foreach {cell run top} {ps7_0 probe_ps7_0_0_synth_1 probe_ps7_0_0 clocks probe_clocks_0_synth_1 probe_clocks_0 video probe_video_0_synth_1 probe_video_0} {
    read_checkpoint -cell probe_i/$cell $runs/$run/$top.dcp
}
set ipdir $stage/project/hdmi_probe.gen/sources_1/bd/probe/ip
read_xdc -cells probe_i/ps7_0 $ipdir/probe_ps7_0_0/probe_ps7_0_0.xdc
read_xdc -cells probe_i/clocks $ipdir/probe_clocks_0/probe_clocks_0.xdc
read_xdc [list [file join [file dirname [file normalize [info script]]] pins.xdc]]
opt_design
place_design
route_design
report_timing_summary -file $stage/timing.rpt
report_drc -file $stage/drc.rpt
report_utilization -file $stage/utilization.rpt
if {[llength [get_clocks]] < 3} {error "Missing fabric/pixel/serial timing clocks"}
foreach kind {max min} {
    set paths [get_timing_paths -delay_type $kind -max_paths 1]
    if {[llength $paths] && [get_property SLACK $paths] < 0} {error "Negative $kind slack"}
}
if {[llength [get_drc_violations -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]]} {error "DRC failed"}
write_checkpoint -force $stage/routed.dcp
write_bitstream -force $stage/hdmi_probe.bit
file copy -force $stage/project/hdmi_probe.gen/sources_1/bd/probe/hw_handoff/probe.hwh $stage/hdmi_probe.hwh
puts "HDMI_PROBE_BUILD_OK"
