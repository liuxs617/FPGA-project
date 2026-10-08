#include "lesion_accel.hpp"
#include <vector>
#include <cassert>
#include <iostream>
int main() {
    std::vector<int8_t> a(8388608,0);std::vector<int32_t> p(4096,0);
    assert(lesion_accel(a.data(),p.data())==0x100);
    // 3x3 all-ones convolution on 4x4; independent scalar expected value.
    p[0]=1;p[1]=4;p[2]=4;p[3]=1;p[4]=1;p[5]=3;p[6]=0;p[8]=256;
    p[9]=512;p[10]=64;p[11]=1<<24;p[12]=24;
    for(int i=0;i<16;i++)a[i]=i-8;
    for(int i=0;i<9;i++)a[512+i]=1;
    assert(lesion_accel(a.data(),p.data())==0);
    for(int y=0;y<4;y++)for(int x=0;x<4;x++) {
        int sum=0;
        for(int dy=-1;dy<=1;dy++)for(int dx=-1;dx<=1;dx++)
            if(y+dy>=0&&y+dy<4&&x+dx>=0&&x+dx<4)sum+=(y+dy)*4+x+dx-8;
        assert(a[256+y*4+x]==sum);
    }
    p[0]=9;p[6]=1024;
    a[1024+1]=1;a[1024+6]=1;
    assert(lesion_accel(a.data(),p.data())==0);
    assert(p[32]==2&&p[34]==3&&p[36]==1&&p[38]==5&&p[40]==2&&p[42]==1);
    p[0]=8;p[3]=3;p[4]=3;p[6]=2048;p[7]=4096;p[8]=8192;p[13]=1;
    for(int i=0;i<48;i++)a[2048+i]=int8_t(255);
    assert(lesion_accel(a.data(),p.data())==0);
    for(int i=0;i<48;i++)assert(a[8192+i]==127&&uint8_t(a[4096+i])==255);
    // Signed max-pooling, nearest upsampling, concat with two scales.
    std::fill(p.begin(),p.end(),0);
    p[0]=2;p[1]=4;p[2]=4;p[3]=1;p[4]=1;p[6]=0;p[8]=256;
    for(int i=0;i<16;i++)a[i]=i-8;
    assert(lesion_accel(a.data(),p.data())==0);
    assert(a[256]==-3&&a[257]==-1&&a[258]==5&&a[259]==7);
    p[0]=3;p[1]=2;p[2]=2;p[6]=256;p[8]=512;
    assert(lesion_accel(a.data(),p.data())==0);
    for(int y=0;y<4;y++)for(int x=0;x<4;x++)assert(a[512+y*4+x]==a[256+(y/2)*2+x/2]);
    p[0]=4;p[1]=4;p[2]=4;p[3]=1;p[4]=2;p[6]=0;p[7]=512;p[8]=1024;
    p[11]=1<<23;p[12]=24;p[13]=1;p[14]=1<<24;
    assert(lesion_accel(a.data(),p.data())==0);
    for(int i=0;i<16;i++) {
        int v=i-8;int rounded=v<0?-((-v+1)/2):(v+1)/2;
        assert(a[1024+i]==rounded&&a[1040+i]==a[512+i]);
    }
    // Threshold endpoints with explicit valid region, then opening removes isolated pixel.
    p[0]=5;p[3]=1;p[4]=1;p[6]=0;p[7]=2048;p[8]=4096;
    for(int i=0;i<16;i++)a[2048+i]=(i!=0);
    p[13]=-129;assert(lesion_accel(a.data(),p.data())==0);
    for(int i=0;i<16;i++)assert(a[4096+i]==(i!=0));
    p[13]=128;assert(lesion_accel(a.data(),p.data())==0);
    for(int i=0;i<16;i++)assert(a[4096+i]==0);
    for(int i=0;i<16;i++)a[i]=0;
    a[5]=1;p[0]=6;p[6]=0;p[8]=256;
    assert(lesion_accel(a.data(),p.data())==0);
    for(int i=0;i<16;i++)assert(a[256+i]==0);
    p[0]=7;p[6]=0;p[8]=512;assert(lesion_accel(a.data(),p.data())==0);
    for(int y=0;y<4;y++)for(int x=0;x<4;x++)assert(a[512+y*4+x]==(y<=2&&x<=2));
    std::cout<<"HLS testbench: ABI, convolution, moments, Gaussian, pool, upsample, concat, threshold endpoints, erosion, dilation passed\n";
}
