set root [file normalize "[file dirname [info script]]/../.."]
set project_dir "$root/build/vivado"
open_project "$project_dir/lesion.xpr"
open_run impl_1
source "$root/hardware/vivado/finish.tcl"
exit
