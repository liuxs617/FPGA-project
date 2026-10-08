set script_dir [file dirname [file normalize [info script]]]
set root [file normalize "$script_dir/../.."]
set project_dir "$root/build/vivado"
create_project -force lesion "$project_dir" -part xc7z020clg400-1
set_property target_language Verilog [current_project]
set_property ip_repo_paths [list "$root/upstream/ip" "$root/build/hls/lesion/solution1/impl/ip"] [current_project]
update_ip_catalog
create_bd_design lesion
source "$root/upstream/video_hierarchy.tcl"
source "$root/upstream/ps_preset.tcl"
set_property -dict [list CONFIG.PCW_USE_S_AXI_HP1 {1} CONFIG.PCW_USE_S_AXI_HP2 {0} CONFIG.PCW_USE_S_AXI_GP0 {0} CONFIG.PCW_USE_M_AXI_GP1 {0} CONFIG.PCW_USE_FABRIC_INTERRUPT {1} CONFIG.PCW_IRQ_F2P_INTR {1}] $ps7_0
foreach n {DDR FIXED_IO} {
  set pin [get_bd_intf_pins ps7_0/$n]
  create_bd_intf_port -mode Master -vlnv [get_property VLNV $pin] $n
  connect_bd_intf_net $pin [get_bd_intf_ports $n]
}
create_hier_cell_video / video
foreach {pin name} {TMDS_out hdmi_out TMDS_in hdmi_in DDC hdmi_in_ddc} {
  set obj [get_bd_intf_pins video/$pin]
  create_bd_intf_port -mode [get_property MODE $obj] -vlnv [get_property VLNV $obj] $name
  connect_bd_intf_net $obj [get_bd_intf_ports $name]
}
foreach n {hdmi_in_hpd hdmi_out_hpd} {
  create_bd_port -dir O -from 0 -to 0 $n
  connect_bd_net [get_bd_ports $n] [get_bd_pins video/$n]
}
create_bd_cell -type ip -vlnv lesion.org:hls:lesion_accel:1.0 lesion_accel_0
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 control
set_property CONFIG.NUM_MI 3 [get_bd_cells control]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 memory
set_property -dict [list CONFIG.NUM_SI 2 CONFIG.NUM_MI 1] [get_bd_cells memory]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_intc:4.1 system_interrupts
set_property -dict [list CONFIG.C_NUM_INTR_INPUTS 6 CONFIG.C_HAS_FAST 0] [get_bd_cells system_interrupts]
connect_bd_intf_net [get_bd_intf_pins ps7_0/M_AXI_GP0] [get_bd_intf_pins control/S00_AXI]
foreach {mi sink} {M00 video/S_AXI M01 lesion_accel_0/s_axi_control M02 system_interrupts/s_axi} {
  connect_bd_intf_net [get_bd_intf_pins control/${mi}_AXI] [get_bd_intf_pins $sink]
}
connect_bd_intf_net [get_bd_intf_pins video/M_AXI] [get_bd_intf_pins ps7_0/S_AXI_HP0]
connect_bd_intf_net [get_bd_intf_pins lesion_accel_0/m_axi_gmem] [get_bd_intf_pins memory/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins lesion_accel_0/m_axi_controlmem] [get_bd_intf_pins memory/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins memory/M00_AXI] [get_bd_intf_pins ps7_0/S_AXI_HP1]
connect_bd_net [get_bd_pins video/video_irq] [get_bd_pins system_interrupts/intr]
connect_bd_net [get_bd_pins system_interrupts/irq] [get_bd_pins ps7_0/IRQ_F2P]
for {set i 0} {$i<2} {incr i} {
  create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 reset$i
  connect_bd_net [get_bd_pins ps7_0/FCLK_CLK$i] [get_bd_pins reset$i/slowest_sync_clk]
  connect_bd_net [get_bd_pins ps7_0/FCLK_RESET0_N] [get_bd_pins reset$i/ext_reset_in]
}
connect_bd_net [get_bd_pins ps7_0/FCLK_RESET0_N] [get_bd_pins video/system_resetn]
foreach {clock pins} {
  FCLK_CLK0 {video/clk_100M ps7_0/M_AXI_GP0_ACLK ps7_0/S_AXI_HP1_ACLK lesion_accel_0/ap_clk system_interrupts/s_axi_aclk control/ACLK control/S00_ACLK control/M00_ACLK control/M01_ACLK control/M02_ACLK memory/ACLK memory/S00_ACLK memory/S01_ACLK memory/M00_ACLK}
  FCLK_CLK1 {video/clk_142M ps7_0/S_AXI_HP0_ACLK}
  FCLK_CLK2 {video/clk_200M}
} {
  foreach pin $pins { connect_bd_net [get_bd_pins ps7_0/$clock] [get_bd_pins $pin] }
}
foreach pin {video/ic_resetn_clk100M control/ARESETN memory/ARESETN} {
  connect_bd_net [get_bd_pins reset0/interconnect_aresetn] [get_bd_pins $pin]
}
foreach pin {video/periph_resetn_clk100M lesion_accel_0/ap_rst_n system_interrupts/s_axi_aresetn control/S00_ARESETN control/M00_ARESETN control/M01_ARESETN control/M02_ARESETN memory/S00_ARESETN memory/S01_ARESETN memory/M00_ARESETN} {
  connect_bd_net [get_bd_pins reset0/peripheral_aresetn] [get_bd_pins $pin]
}
connect_bd_net [get_bd_pins reset1/interconnect_aresetn] [get_bd_pins video/ic_resetn_clk142M]
connect_bd_net [get_bd_pins reset1/peripheral_aresetn] [get_bd_pins video/periph_resetn_clk142M]
assign_bd_address
validate_bd_design
save_bd_design
report_ip_status -file "$root/build/ip_status.rpt"
generate_target all [get_files lesion.bd]
set wrappers [make_wrapper -files [get_files lesion.bd] -top]
add_files -norecurse $wrappers
set_property top lesion_wrapper [current_fileset]
add_files -fileset constrs_1 "$root/upstream/video.xdc"
update_compile_order -fileset sources_1
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis failed"}
launch_runs impl_1 -to_step route_design -jobs 4
wait_on_run impl_1
if {![string match {*route_design Complete*} [get_property STATUS [get_runs impl_1]]]} {error "Implementation routing failed"}
open_run impl_1
source "$script_dir/finish.tcl"
exit
