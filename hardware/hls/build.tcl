set here [file dirname [file normalize [info script]]]
set root [file normalize "$here/../.."]
open_project -reset "$root/build/hls/lesion"
set_top lesion_accel
add_files "$here/lesion_accel.cpp" -cflags "-std=c++14"
add_files -tb "$here/testbench.cpp" -cflags "-std=c++14"
open_solution -reset solution1 -flow_target vivado
set_part xc7z020clg400-1
create_clock -period 10 -name default
csim_design
csynth_design
if {[info exists ::env(LESION_COSIM)] && $::env(LESION_COSIM) eq "1"} { cosim_design -rtl verilog }
export_design -format ip_catalog -rtl verilog -vendor lesion.org -library hls -version 1.0
exit
