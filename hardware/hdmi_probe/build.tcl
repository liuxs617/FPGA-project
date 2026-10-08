set root [file normalize [lindex $argv 0]]
set stage C:/temp/lesion_hdmi_probe
file mkdir $stage
create_project hdmi_probe $stage/project -part xc7z020clg400-1 -force
set_property target_language Verilog [current_project]
set_property source_mgmt_mode All [current_project]
set sources [glob $root/third_party/hdl-util-hdmi/src/*.sv]
# Use the reviewed local Xilinx serializer, preserving upstream source verbatim.
set sources [lsearch -all -inline -not -glob $sources */serializer.sv]
set sources [lsearch -all -inline -not -glob $sources */packet_picker.sv]
add_files $sources
add_files [list $root/hardware/hdmi_probe/packet_picker.sv]
add_files [list $root/hardware/hdmi_probe/serializer.sv]
add_files [list $root/hardware/hdmi_probe/hdmi_probe.sv]
add_files [list $root/hardware/hdmi_probe/hdmi_probe_wrapper.v]
add_files -fileset constrs_1 [list $root/hardware/hdmi_probe/pins.xdc]
create_bd_design probe
source C:/temp/lesion_fpga/upstream/ps_preset.tcl
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP0 {0} CONFIG.PCW_USE_S_AXI_HP0 {0} CONFIG.PCW_USE_S_AXI_HP1 {0} CONFIG.PCW_USE_S_AXI_HP2 {0} CONFIG.PCW_USE_S_AXI_HP3 {0} CONFIG.PCW_EN_CLK1_PORT {0} CONFIG.PCW_EN_CLK2_PORT {0} CONFIG.PCW_EN_CLK3_PORT {0} CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100}] $ps7_0
make_bd_intf_pins_external [get_bd_intf_pins ps7_0/DDR]
make_bd_intf_pins_external [get_bd_intf_pins ps7_0/FIXED_IO]
set clocks [create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 clocks]
set_property -dict [list CONFIG.PRIM_IN_FREQ {100} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {74.250} CONFIG.CLKOUT2_USED {true} CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {371.250} CONFIG.RESET_TYPE {ACTIVE_LOW}] $clocks
set_property -dict [list CONFIG.PCW_USE_M_AXI_GP1 {0} CONFIG.PCW_USE_S_AXI_GP0 {0}] $ps7_0
create_bd_cell -type module -reference hdmi_probe_wrapper video
connect_bd_net [get_bd_pins ps7_0/FCLK_CLK0] [get_bd_pins clocks/clk_in1]
connect_bd_net [get_bd_pins ps7_0/FCLK_RESET0_N] [get_bd_pins clocks/resetn]
connect_bd_net [get_bd_pins clocks/clk_out1] [get_bd_pins video/clk_pixel]
connect_bd_net [get_bd_pins clocks/clk_out2] [get_bd_pins video/clk_pixel_x5]
connect_bd_net [get_bd_pins clocks/locked] [get_bd_pins video/locked]
foreach name {hdmi_data_p hdmi_data_n hdmi_clk_p hdmi_clk_n} {
    if {[string match hdmi_data* $name]} {
        create_bd_port -dir O -from 2 -to 0 $name
    } else {
        create_bd_port -dir O $name
    }
    connect_bd_net [get_bd_pins video/$name] [get_bd_ports $name]
}
validate_bd_design
save_bd_design
generate_target all [get_files probe.bd]
add_files [make_wrapper -files [get_files probe.bd] -top]
set_property top probe_wrapper [current_fileset]
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 8
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
close_project
source $root/hardware/hdmi_probe/implement.tcl

