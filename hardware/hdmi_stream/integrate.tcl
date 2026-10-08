# Incremental replacement of only the HDMI output IP in the signed-off design.
set stage C:/temp/lesion_hdmi_full
set core_dir $stage/custom_ip/rgb2hdmi/src
set root [file normalize [file join [file dirname [info script]] ../..]]
if {[lindex $argv 0] ni {reuse_encoder reuse_linked}} {
create_project -in_memory -part xc7z020clg400-1
read_verilog -sv [glob $core_dir/*.sv]
read_vhdl $core_dir/rgb2dvi.vhd
read_verilog -sv $stage/build/vivado/lesion.gen/sources_1/bd/lesion/ip/lesion_rgb2dvi_0_0/synth/lesion_rgb2dvi_0_0.sv
synth_design -top lesion_rgb2dvi_0_0 -part xc7z020clg400-1 -mode out_of_context
write_checkpoint -force $stage/encoder.dcp
close_project
}
set cell lesion_i/video/hdmi_out/frontend/rgb2dvi_0
if {[lindex $argv 0] eq "reuse_linked"} {
open_checkpoint $stage/linked.dcp
} else {
open_checkpoint C:/temp/lesion_fpga/build/signed_off.dcp
if {[llength [get_cells $cell]]!=1} {error "HDMI output cell not unique"}
update_design -cell $cell -black_box
read_checkpoint -cell $cell $stage/encoder.dcp
write_checkpoint -force $stage/linked.dcp
}
# Re-establish the external 5x clock at the replacement's input, from the
# real BUFIO source rather than deriving it from the divided PixelClk branch.
set serial_source [get_pins -hier -filter {NAME =~ *axi_dynclk*BUFIO_inst/I}]
set serial_sink [get_pins $cell/SerialClk]
if {[llength $serial_source]!=1 || [llength $serial_sink]!=1} {error "Serializer clock not unique"}
create_generated_clock -name hdmi_stream_serial -source $serial_source -divide_by 1 $serial_sink
# Discard prior physical implementation, while retaining fixed board pins.
route_design -unroute
place_design -unplace
opt_design
write_checkpoint -force $stage/optimized.dcp
place_design
phys_opt_design -directive AggressiveExplore
route_design
phys_opt_design -directive AggressiveExplore
write_checkpoint -force $stage/routed_candidate.dcp
file mkdir $stage/build
foreach {command file} {report_methodology methodology report_timing_summary timing_summary report_utilization utilization report_drc drc report_bus_skew bus_skew report_cdc cdc} {
    $command -file $stage/build/$file.rpt
}
foreach kind {max min} {
    if {[get_property SLACK [get_timing_paths -delay_type $kind -max_paths 1]]<0} {error "Negative $kind slack"}
}
if {[llength [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]]} {error "DRC failed"}
write_checkpoint -force $stage/build/signed_off.dcp
file mkdir $stage/release
write_bitstream -force $stage/release/lesion.bit
file copy -force $stage/build/vivado/lesion.gen/sources_1/bd/lesion/hw_handoff/lesion.hwh $stage/release/lesion.hwh
puts "STREAM_HDMI_INTEGRATION_OK"
