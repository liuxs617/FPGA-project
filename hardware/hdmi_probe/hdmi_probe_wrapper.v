// Vivado block-design module references require a Verilog top-level file.
module hdmi_probe_wrapper (
 input wire clk_pixel, input wire clk_pixel_x5, input wire locked,
 output wire [2:0] hdmi_data_p, output wire [2:0] hdmi_data_n,
 (* X_INTERFACE_IGNORE = "TRUE" *) output wire hdmi_clk_p,
 (* X_INTERFACE_IGNORE = "TRUE" *) output wire hdmi_clk_n
);
 hdmi_probe core (.clk_pixel(clk_pixel), .clk_pixel_x5(clk_pixel_x5),
  .locked(locked), .hdmi_data_p(hdmi_data_p), .hdmi_data_n(hdmi_data_n),
  .hdmi_clk_p(hdmi_clk_p), .hdmi_clk_n(hdmi_clk_n));
endmodule
