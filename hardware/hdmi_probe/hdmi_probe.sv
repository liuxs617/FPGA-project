// Standalone diagnostic; does not replace the inference overlay.
module hdmi_probe (
    input wire clk_pixel,
    input wire clk_pixel_x5,
    input wire locked,
    output wire [2:0] hdmi_data_p,
    output wire [2:0] hdmi_data_n,
    output wire hdmi_clk_p,
    output wire hdmi_clk_n
);
    (* ASYNC_REG = "TRUE" *) reg [3:0] reset_pipe = 4'hf;
    always @(posedge clk_pixel or negedge locked)
        if (!locked) reset_pipe <= 4'hf;
        else reset_pipe <= {reset_pipe[2:0], 1'b0};
    wire reset = reset_pipe[3];
    wire [10:0] cx;
    wire [9:0] cy;
    reg [23:0] rgb = 0;
    // Full-range RGB eight-bar pattern, one cycle ahead of the encoder.
    always @(posedge clk_pixel) begin
        if      (cx < 160)  rgb <= 24'hffffff;
        else if (cx < 320)  rgb <= 24'hffff00;
        else if (cx < 480)  rgb <= 24'h00ffff;
        else if (cx < 640)  rgb <= 24'h00ff00;
        else if (cx < 800)  rgb <= 24'hff00ff;
        else if (cx < 960)  rgb <= 24'hff0000;
        else if (cx < 1120) rgb <= 24'h0000ff;
        else               rgb <= 24'h000000;
    end
    wire [15:0] silence [1:0];
    assign silence[0] = 0;
    assign silence[1] = 0;
    wire [2:0] serial_data;
    wire serial_clock;
    // No audio sample clock: this test is for video and HDMI InfoFrames.
    hdmi #(.VIDEO_ID_CODE(4), .VIDEO_REFRESH_RATE(60.0), .DVI_OUTPUT(0),
           .VENDOR_NAME({"PYNQ-Z2",8'd0}),
           .PRODUCT_DESCRIPTION({"HDMI probe",48'd0})) encoder (
        .clk_pixel(clk_pixel), .clk_pixel_x5(clk_pixel_x5),
        .clk_audio(1'b0), .reset(reset), .rgb(rgb),
        .audio_sample_word(silence), .tmds(serial_data), .tmds_clock(serial_clock),
        .cx(cx), .cy(cy), .frame_width(), .frame_height(),
        .screen_width(), .screen_height()
    );
    OBUFDS #(.IOSTANDARD("TMDS_33")) clock_out
        (.I(serial_clock), .O(hdmi_clk_p), .OB(hdmi_clk_n));
    for (genvar i=0; i<3; i=i+1) begin: differential_output
        OBUFDS #(.IOSTANDARD("TMDS_33")) data_out
            (.I(serial_data[i]), .O(hdmi_data_p[i]), .OB(hdmi_data_n[i]));
    end
endmodule
