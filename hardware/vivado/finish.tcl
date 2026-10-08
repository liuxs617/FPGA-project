# Shared post-route signoff. The external serializer clock is driven by the
# dynclk MMCM through BUFIO, not by its sibling BUFR /5 PixelClk output.
set serial_source [get_pins -hier -filter {NAME =~ *axi_dynclk*BUFIO_inst/I}]
set serial_sink [get_pins lesion_i/video/hdmi_out/frontend/rgb2dvi_0/U0/SerialClk]
if {[llength $serial_source] != 1 || [llength $serial_sink] != 1} {error "Serializer clock pins not unique"}
create_generated_clock -name lesion_i/video/hdmi_out/frontend/rgb2dvi_0/U0/SerialClk -source $serial_source -divide_by 1 $serial_sink
# Upstream rounds its nominal 120 MHz input period up to 8.334 ns,
# putting the receiver MMCM just below its 600 MHz VCO lower bound.
# Round toward the tighter constraint instead; HDMI input is retained for
# PYNQ hierarchy compatibility and is not the application's image source.
create_clock -name hdmi_in_clk_p -period 8.333 [get_ports hdmi_in_clk_p]
phys_opt_design -directive AggressiveExplore
report_methodology -file "$root/build/methodology.rpt"
report_timing_summary -check_timing_verbose -file "$root/build/timing_summary.rpt"
report_utilization -file "$root/build/utilization.rpt"
report_drc -file "$root/build/drc.rpt"
report_bus_skew -file "$root/build/bus_skew.rpt"
report_cdc -details -file "$root/build/cdc.rpt"
report_power -file "$root/build/power_estimate.rpt"
foreach type {max min} {
  if {[get_property SLACK [get_timing_paths -delay_type $type -max_paths 1]] < 0} {error "Timing $type not met; release blocked"}
}
if {[llength [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]]} {error "DRC errors/critical warnings; release blocked"}
file mkdir "$root/release"
write_checkpoint -force "$root/build/signed_off.dcp"
write_bitstream -force "$root/release/lesion.bit"
# XSA export locates the bitstream by the implementation run's top name.
# Publish exactly the signed-off bitstream there; do not regenerate from the
# earlier route_design checkpoint, which precedes the clock fixes and physopt.
set impl_dir [get_property DIRECTORY [get_runs impl_1]]
set impl_top [get_property TOP [current_fileset]]
file copy -force "$root/release/lesion.bit" "$impl_dir/$impl_top.bit"
file copy -force "$project_dir/lesion.gen/sources_1/bd/lesion/hw_handoff/lesion.hwh" "$root/release/lesion.hwh"
write_hw_platform -fixed -include_bit -force "$root/release/lesion.xsa"

