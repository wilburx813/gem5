#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#ifndef STRIDE
#define STRIDE (1u << 14)  /* 16KB stride to hit same bank groups */
#endif
#ifndef ITERS
#define ITERS (1u << 24)   /* fewer total touches to shorten runtime */
#endif
#ifndef SIZE_BYTES
#define SIZE_BYTES (64u * 1024u * 1024u)  /* shrink buffer from 512MB -> 64MB */
#endif

int main(void) {
    size_t size = SIZE_BYTES;
    char *buf = aligned_alloc(64, size);
    if (!buf) {
        perror("alloc bank_conflict");
        return 1;
    }

    volatile uint64_t sum = 0;
    for (uint64_t i = 0; i < ITERS; i++) {
        sum += (uint64_t)buf[(i * STRIDE) & (size - 1)];
    }

    printf("class_bank_conflict sum=%lu\n", (unsigned long)sum);
    free(buf);
    return 0;
}
