`timescale 1ns/1ps
module stream_tb;
 reg clk=0; always #5 clk=~clk;
 reg rst_n=0;
 integer x=0,y=0;
 always @(negedge clk) if(rst_n) begin
   if(x==1649) begin x=0; y=y==749?0:y+1; end else x=x+1;
 end
 wire de=x<1280 && y<720;
 wire hs=x>=1390 && x<1430;
 wire vs=y>=725 && y<730;
 wire [23:0] rgb={8'(x),8'(y),8'(x^y)};
 hdmi_stream dut(.PixelClk(clk),.SerialClk(clk),.aRst_n(rst_n),
   .vid_pData({rgb[23:16],rgb[7:0],rgb[15:8]}),.vid_pVDE(de),.vid_pHSync(hs),.vid_pVSync(vs),
   .TMDS_Clk_p(),.TMDS_Clk_n(),.TMDS_Data_p(),.TMDS_Data_n());
 integer active=0,guards=0,avi=0,checksum;
 reg [7:0] decoded;
 reg [23:0] expected_pixel;
 reg [2:0] expected_mode;
 reg [12:0] input_de_history=0;
 reg [23:0] input_rgb_history[0:12];
 integer observed_cycles=0;
 // Verify actual TMDS video symbols decode to the matching RGB pixel.
 always @(posedge clk) begin
   expected_pixel=dut.video_data; expected_mode=dut.mode;
   input_de_history={input_de_history[11:0],de};
   for(integer i=12;i>0;i=i-1) input_rgb_history[i]=input_rgb_history[i-1];
   input_rgb_history[0]=rgb;
   observed_cycles=observed_cycles+1;
   #1;
   if(observed_cycles>30) begin
     if((dut.mode==1)!==input_de_history[12]) $fatal(1,"Video-enable pipeline mismatch");
     if(dut.mode==1 && dut.video_data!==input_rgb_history[12]) $fatal(1,"Input pixel alignment mismatch");
   end
   if(expected_mode==1) for(integer c=0;c<3;c=c+1) begin
     decoded[0]=dut.symbols[c][9] ? ~dut.symbols[c][0] : dut.symbols[c][0];
     for(integer b=1;b<8;b=b+1)
       decoded[b]=dut.symbols[c][8] ? (dut.symbols[c][b]^dut.symbols[c][b-1]) : ~(dut.symbols[c][b]^dut.symbols[c][b-1]);
     if(decoded!==expected_pixel[c*8+:8]) $fatal(1,"TMDS RGB mismatch");
   end
 end
 initial begin
   repeat(5) @(negedge clk); #1; rst_n=1;
   repeat(1650*750) @(negedge clk);
   repeat(1650*750) begin
     #2;
     if($isunknown({dut.symbols[0],dut.symbols[1],dut.symbols[2]})) $fatal(1,"Unknown TMDS");
     if(dut.mode==1) active=active+1;
     if(dut.mode==2) guards=guards+1;
     if(dut.island && dut.packet_counter==0 && dut.header==24'h0d0282) begin
       avi=avi+1; checksum='h82+2+13;
       for(integer b=0;b<14;b=b+1) checksum=checksum+((dut.sub[b/7]>>((b%7)*8))&255);
       if((checksum&255)!=0 || dut.sub[0][39:32]!=4) $fatal(1,"AVI invalid");
     end
     if(dut.island && (dut.video_guard||dut.video_preamble||dut.de_pipe[11])) $fatal(1,"Packet overlaps video");
     @(negedge clk);
   end
   if(active!=921600 || guards!=1440 || avi!=1) $fatal(1,"Bad counts %0d %0d %0d",active,guards,avi);
   $display("HDMI_STREAM_PASS active=%0d guard=%0d avi=%0d RGB_decode=PASS",active,guards,avi);
   $finish;
 end
endmodule
module OBUFDS #(parameter IOSTANDARD="TMDS_33")(input I,output O,OB);
 assign O=I; assign OB=~I;
endmodule
