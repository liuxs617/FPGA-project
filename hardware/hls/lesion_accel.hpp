#pragma once
#include <cstdint>
// ABI 1: arena CHW bytes; params[0:16] descriptor; params[32:44] moments.
// All memory passed to the core must come from the validated host allocation.
extern "C" int lesion_accel(int8_t* arena, int32_t* params);
