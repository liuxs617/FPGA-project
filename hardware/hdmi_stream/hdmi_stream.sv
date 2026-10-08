// HDMI packet insertion for the existing PYNQ 720p60 video stream.
// Packet/ECC/TMDS modules are from hdl-util/hdmi (MIT; see hdmi_probe/LICENSE-MIT).
module hdmi_stream(
 input wire PixelClk, SerialClk, aRst_n,
 input wire [23:0] vid_pData, // Digilent interface packs R,B,G
 input wire vid_pVDE, vid_pHSync, vid_pVSync,
 output wire TMDS_Clk_p, TMDS_Clk_n,
 output wire [2:0] TMDS_Data_p, TMDS_Data_n
);
 (* ASYNC_REG="TRUE" *) reg [3:0] reset_pipe=4'hf;
 always @(posedge PixelClk or negedge aRst_n)
   if(!aRst_n) reset_pipe<=4'hf; else reset_pipe<={reset_pipe[2:0],1'b0};
 wire reset=reset_pipe[3];
 reg [11:0] de_pipe=0, hs_pipe=0, vs_pipe=0;
 reg [23:0] rgb_pipe[0:11];
 always @(posedge PixelClk) begin
   if(reset) begin de_pipe<=0; hs_pipe<=0; vs_pipe<=0; end
   else begin
     de_pipe<={de_pipe[10:0],vid_pVDE};
     hs_pipe<={hs_pipe[10:0],vid_pHSync};
     vs_pipe<={vs_pipe[10:0],vid_pVSync};
   end
   rgb_pipe[0]<={vid_pData[23:16],vid_pData[7:0],vid_pData[15:8]};
   for(integer i=1;i<12;i=i+1) rgb_pipe[i]<=rgb_pipe[i-1];
 end
 // Twelve pixels of lookahead allow eight preamble and two guard symbols
 // immediately before every active line, without changing the input timing.
 wire video_guard=!de_pipe[11] && de_pipe[9];
 wire video_preamble=!de_pipe[9] && de_pipe[1];
 reg [9:0] blank_count=0;
 always @(posedge PixelClk)
   if(reset || de_pipe[11]) blank_count<=0;
   else if(blank_count!=1023) blank_count<=blank_count+1'b1;
 // 720p has 370 blank pixels per active line. Ten 32-pixel packets fit,
 // including both preambles, guard bands and the required control periods.
 wire island= !de_pipe[11] && blank_count>=14 && blank_count<334;
 wire island_guard=!de_pipe[11] &&
   ((blank_count>=12 && blank_count<14)||(blank_count>=334 && blank_count<336));
 wire island_preamble=!de_pipe[11] && blank_count>=4 && blank_count<12;
 wire packet_enable=!de_pipe[11] && blank_count>=13 && blank_count<333 &&
   blank_count[4:0]==13;
 reg last_vsync=0;
 always @(posedge PixelClk) last_vsync<=vs_pipe[11];
 wire [15:0] silence[1:0];
 assign silence[0]=0; assign silence[1]=0;
 wire [23:0] header;
 wire [55:0] sub[3:0];
 wire [4:0] packet_counter;
 wire [8:0] packet_data;
 packet_picker #(.VIDEO_ID_CODE(4),.VIDEO_RATE(74250000.0),.IT_CONTENT(1),
   .AUDIO_RATE(44100),.AUDIO_BIT_WIDTH(16),.VENDOR_NAME({"PYNQ-Z2",8'd0}),
   .PRODUCT_DESCRIPTION({"Lesion HDMI",40'd0})) picker
   (.clk_pixel(PixelClk),.clk_audio(1'b0),.reset(reset),
    .video_field_end(vs_pipe[11] && !last_vsync),.packet_enable(packet_enable),
    .packet_pixel_counter(packet_counter),.audio_sample_word(silence),.header(header),.sub(sub));
 packet_assembler assembler(.clk_pixel(PixelClk),.reset(reset),
   .data_island_period(island),.header(header),.sub(sub),.packet_data(packet_data),.counter(packet_counter));
 reg [2:0] mode=0;
 reg [23:0] video_data=0;
 reg [5:0] control_data=0;
 reg [11:0] island_data=0;
 always @(posedge PixelClk) begin
   mode<=reset ? 0 : de_pipe[11] ? 1 : video_guard ? 2 : island_guard ? 4 : island ? 3 : 0;
   video_data<=rgb_pipe[11];
   control_data<={1'b0,island_preamble,1'b0,video_preamble||island_preamble,vs_pipe[11],hs_pipe[11]};
   island_data<={packet_data[8:1],1'b1,packet_data[0],vs_pipe[11],hs_pipe[11]};
 end
 wire [9:0] symbols[2:0];
 for(genvar c=0;c<3;c=c+1) begin: encode
   tmds_channel #(.CN(c)) channel(.clk_pixel(PixelClk),.video_data(video_data[c*8+:8]),
     .data_island_data(island_data[c*4+:4]),.control_data(control_data[c*2+:2]),.mode(mode),.tmds(symbols[c]));
 end
 wire [2:0] serial_data;
 wire serial_clock;
 serializer #(.NUM_CHANNELS(3),.VIDEO_RATE(74250000.0)) serialize
   (.clk_pixel(PixelClk),.clk_pixel_x5(SerialClk),.reset(reset),
    .tmds_internal(symbols),.tmds(serial_data),.tmds_clock(serial_clock));
 OBUFDS #(.IOSTANDARD("TMDS_33")) clock_out(.I(serial_clock),.O(TMDS_Clk_p),.OB(TMDS_Clk_n));
 for(genvar c=0;c<3;c=c+1) begin: outputs
   OBUFDS #(.IOSTANDARD("TMDS_33")) data_out(.I(serial_data[c]),.O(TMDS_Data_p[c]),.OB(TMDS_Data_n[c]));
 end
endmodule
