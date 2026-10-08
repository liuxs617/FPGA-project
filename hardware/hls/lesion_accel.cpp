#include "lesion_accel.hpp"

static const int PIN=8, POUT=8, TILE=8;

static int8_t rq(int32_t x, int32_t multiplier, int shift, bool relu=false) {
#pragma HLS INLINE off
#pragma HLS PIPELINE II=1
    int64_t z=int64_t(x)*multiplier;
    int64_t y=((z<0?-z:z)+(int64_t(1)<<(shift-1)))>>shift;
    if(z<0)y=-y;
    if(y>127)y=127;
    if(y<(relu?0:-128))y=relu?0:-128;
    return int8_t(y);
}

static void convolution(int8_t* mem, const int32_t* p, const int d[16]) {
    int h=d[1],w=d[2],ci=d[3],co=d[4],k=d[5];
    int32_t acc[TILE*TILE][POUT];
    int8_t pixels[TILE+2][TILE+2][PIN];
    int8_t weights[POUT][PIN][3][3];
#pragma HLS ARRAY_PARTITION variable=acc complete dim=2
#pragma HLS ARRAY_PARTITION variable=pixels complete dim=3
#pragma HLS ARRAY_PARTITION variable=weights complete dim=1
#pragma HLS ARRAY_PARTITION variable=weights complete dim=2
    for(int oc=0;oc<co;oc+=POUT)
      for(int ty=0;ty<h;ty+=TILE)
        for(int tx=0;tx<w;tx+=TILE) {
          for(int s=0;s<TILE*TILE;s++) {
#pragma HLS PIPELINE II=1
            for(int o=0;o<POUT;o++) {
#pragma HLS UNROLL
              acc[s][o]=(oc+o<co)?p[d[10]+oc+o]:0;
            }
          }
          for(int ic=0;ic<ci;ic+=PIN) {
            // Burst-friendly CHW loads, then parallel banked computation.
            for(int c=0;c<PIN;c++)
              for(int y=0;y<TILE+k-1;y++)
                for(int x=0;x<TILE+k-1;x++) {
#pragma HLS PIPELINE II=1
                  int iy=ty+y-k/2,ix=tx+x-k/2;
                  pixels[y][x][c]=(ic+c<ci && iy>=0 && iy<h && ix>=0 && ix<w)
                    ?mem[d[6]+((ic+c)*h+iy)*w+ix]:0;
                }
            for(int o=0;o<POUT;o++)
              for(int c=0;c<PIN;c++)
                for(int y=0;y<k;y++)
                  for(int x=0;x<k;x++) {
#pragma HLS PIPELINE II=1
                    weights[o][c][y][x]=(oc+o<co && ic+c<ci)
                      ?mem[d[9]+(((oc+o)*ci+ic+c)*k+y)*k+x]:0;
                  }
            for(int ky=0;ky<k;ky++)
              for(int kx=0;kx<k;kx++)
                for(int s=0;s<TILE*TILE;s++) {
#pragma HLS PIPELINE II=1
                  for(int o=0;o<POUT;o++) {
#pragma HLS UNROLL
                    int32_t sum=0;
                    for(int c=0;c<PIN;c++) {
#pragma HLS UNROLL
                      int16_t product=int16_t(pixels[s/TILE+ky][s%TILE+kx][c])*int16_t(weights[o][c][ky][kx]);
                      sum+=product;
                    }
                    acc[s][o]+=sum;
                  }
                }
          }
          for(int o=0;o<POUT;o++)
            for(int y=0;y<TILE;y++)
              for(int x=0;x<TILE;x++) {
#pragma HLS PIPELINE II=1
                if(oc+o<co && ty+y<h && tx+x<w)
                  mem[d[8]+((oc+o)*h+ty+y)*w+tx+x]=rq(acc[y*TILE+x][o],d[11],d[12],d[13]!=0);
              }
        }
}

extern "C" int lesion_accel(int8_t* arena, int32_t* params) {
#pragma HLS INTERFACE m_axi port=arena offset=slave bundle=gmem depth=8388608 max_read_burst_length=64 max_write_burst_length=64
#pragma HLS INTERFACE m_axi port=params offset=slave bundle=controlmem depth=4096
#pragma HLS INTERFACE s_axilite port=arena bundle=control
#pragma HLS INTERFACE s_axilite port=params bundle=control
#pragma HLS INTERFACE s_axilite port=return bundle=control
    int d[16];
    for(int i=0;i<16;i++)d[i]=params[i];
    int op=d[0],h=d[1],w=d[2],ci=d[3],co=d[4];
    if(op==0)return 0x0100; // ABI 1 probe
    if(h<1||h>256||w<1||w>256||ci<1||ci>256||co<1||co>256)return -1;
    if(d[6]<0||d[7]<0||d[8]<0||d[9]<0||d[10]<0)return -2;
    if((op==1||op==4)&&(d[12]<1||d[12]>31||d[11]<=0))return -3;
    if(op==1) {
        if(d[5]!=1&&d[5]!=3)return -4;
        convolution(arena,params,d);
    } else if(op==2) {
        if(h%2||w%2)return -5;
        for(int c=0;c<ci;c++)for(int y=0;y<h/2;y++)for(int x=0;x<w/2;x++) {
#pragma HLS PIPELINE off
            int8_t v=-128;
            for(int dy=0;dy<2;dy++)for(int dx=0;dx<2;dx++) {
                int8_t a=arena[d[6]+(c*h+2*y+dy)*w+2*x+dx];if(a>v)v=a;
            }
            arena[d[8]+(c*(h/2)+y)*(w/2)+x]=v;
        }
    } else if(op==3) {
        if(h>128||w>128)return -6;
        for(int c=0;c<ci;c++)for(int y=0;y<h*2;y++)for(int x=0;x<w*2;x++) {
#pragma HLS PIPELINE off
            arena[d[8]+(c*h*2+y)*w*2+x]=arena[d[6]+(c*h+y/2)*w+x/2];
        }
    } else if(op==4) {
        if(co!=ci+d[13]||d[14]<=0)return -7;
        for(int c=0;c<co;c++)for(int i=0;i<h*w;i++) {
#pragma HLS PIPELINE off
            int src=c<ci?d[6]+c*h*w+i:d[7]+(c-ci)*h*w+i;
            arena[d[8]+c*h*w+i]=rq(arena[src],c<ci?d[11]:d[14],d[12]);
        }
    } else if(op==5) {
        for(int i=0;i<h*w;i++) {
#pragma HLS PIPELINE off
            arena[d[8]+i]=(arena[d[6]+i]>=d[13] && arena[d[7]+i]!=0)?1:0;
        }
    } else if(op==6||op==7) {
        // Frame-memory neighbourhood operation; explicit zero border.
        for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
            bool value=op==6;
            for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++) {
#pragma HLS PIPELINE off
                bool v=y+dy>=0&&y+dy<h&&x+dx>=0&&x+dx<w&&arena[d[6]+(y+dy)*w+x+dx]!=0;
                value=op==6?(value&&v):(value||v);
            }
            arena[d[8]+y*w+x]=value;
        }
    } else if(op==8) {
        // Input/output RGB bytes are CHW; output quantized tensor d[8].
        // d[7] receives exact processed uint8 image for display.
        for(int c=0;c<3;c++)for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
            int value=0;
            if(d[13]) {
                for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++) {
#pragma HLS PIPELINE off
                    int yy=y+dy,xx=x+dx;
                    yy=yy<0?0:(yy>=h?h-1:yy);xx=xx<0?0:(xx>=w?w-1:xx);
                    value+=uint8_t(arena[d[6]+(c*h+yy)*w+xx])*(dy==0?2:1)*(dx==0?2:1);
                }
                value=(value+8)/16;
            } else value=uint8_t(arena[d[6]+(c*h+y)*w+x]);
            arena[d[7]+(c*h+y)*w+x]=int8_t(value);
            arena[d[8]+(c*h+y)*w+x]=int8_t((value*127+127)/255);
        }
    } else if(op==9) {
        uint64_t sums[6]={0,0,0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=sums complete
        for(int y=0;y<h;y++)for(int x=0;x<w;x++) {
#pragma HLS PIPELINE off
            if(arena[d[6]+y*w+x]) {
                sums[0]++;sums[1]+=x;sums[2]+=y;sums[3]+=x*x;sums[4]+=x*y;sums[5]+=y*y;
            }
        }
        for(int i=0;i<6;i++) {params[32+2*i]=int32_t(sums[i]);params[33+2*i]=int32_t(sums[i]>>32);}
    } else return -8;
    return 0;
}
