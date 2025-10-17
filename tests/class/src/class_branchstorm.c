#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

#ifndef ITERATIONS
#define ITERATIONS (1 << 20)
#endif

int main(void) {
    uint32_t lfsr = 0xACE1u;
    uint64_t hits = 0;
    uint64_t misses = 0;

    for (uint64_t i = 0; i < ITERATIONS; ++i) {
        lfsr ^= lfsr << 13;
        lfsr ^= lfsr >> 17;
        lfsr ^= lfsr << 5;
        if (lfsr & 1u) {
            hits += lfsr;
        } else {
            misses += lfsr;
        }
    }

    printf("class_branchstorm: hits=%llu misses=%llu\n",
           (unsigned long long)hits,
           (unsigned long long)misses);
    return 0;
}
