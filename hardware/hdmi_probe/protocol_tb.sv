`timescale 1ns/1ps
// Checks complete raster and HDMI packet signaling, before physical SERDES.
module protocol_tb;
    reg clk=0;
    always #5 clk=~clk;
    reg reset=1;
    wire [10:0] x;
    wire [9:0] y;
    wire [15:0] silence[1:0];
    assign silence[0]=0;
    assign silence[1]=0;
    hdmi #(.VIDEO_ID_CODE(4), .VIDEO_REFRESH_RATE(60.0), .DVI_OUTPUT(0)) dut
      (.clk_pixel(clk), .clk_pixel_x5(clk), .clk_audio(1'b0), .reset(reset),
       .rgb(24'hff0000), .audio_sample_word(silence), .cx(x), .cy(y),
       .tmds(), .tmds_clock(), .frame_width(), .frame_height(),
       .screen_width(), .screen_height());
    integer pixels=0, active=0, islands=0, guards=0, avi=0, checksum=0;
    initial begin
        repeat(5) @(negedge clk);
        reset=0;
        // Warm up a frame so registered periods have settled.
        repeat(1650*750) @(negedge clk);
        repeat(1650*750) begin
            if(x>=1650 || y>=750) $fatal(1,"Raster out of bounds");
            if($isunknown({dut.tmds_internal[0],dut.tmds_internal[1],dut.tmds_internal[2]}))
                $fatal(1,"Unknown TMDS symbol");
            pixels=pixels+1;
            if(dut.mode==1) active=active+1;
            if(dut.mode==3) islands=islands+1;
            if(dut.mode==2 || dut.mode==4) guards=guards+1;
            if(dut.true_hdmi_output.packet_pixel_counter==0 &&
               dut.true_hdmi_output.data_island_period &&
               dut.true_hdmi_output.header==24'h0d0282) begin
                avi=avi+1;
                checksum='h82+2+13;
                for(integer b=0;b<14;b=b+1)
                    checksum=checksum+((dut.true_hdmi_output.sub[b/7] >> ((b%7)*8)) & 255);
                if((checksum & 255)!=0) $fatal(1,"AVI checksum invalid");
                if(dut.true_hdmi_output.sub[0][39:32]!=4) $fatal(1,"Wrong VIC");
                if(dut.true_hdmi_output.sub[0][14:13]!=0) $fatal(1,"Not RGB");
            end
            @(negedge clk);
        end
        if(active!=1280*720 || islands==0 || guards==0 || avi==0)
            $fatal(1,"Counts active=%0d islands=%0d guards=%0d avi=%0d",active,islands,guards,avi);
        $display("HDMI_PROTOCOL_PASS pixels=%0d active=%0d islands=%0d guards=%0d avi=%0d",pixels,active,islands,guards,avi);
        $finish;
    end
endmodule
// Physical outputs are checked by implementation DRC and hardware capture.
module serializer #(parameter NUM_CHANNELS=3, parameter real VIDEO_RATE=0)
 (input clk_pixel,clk_pixel_x5,reset,input [9:0] tmds_internal[NUM_CHANNELS-1:0],
 output [2:0] tmds,output tmds_clock);
 assign tmds=0;
 assign tmds_clock=clk_pixel;
endmodule
