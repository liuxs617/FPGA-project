set here [file dirname [file normalize [info script]]]
set root [file normalize "$here/../.."]
open_project "$root/build/hls/lesion"
open_solution solution1
csim_design
cosim_design -rtl verilog
exit
