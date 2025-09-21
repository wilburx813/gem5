#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#ifndef ARRAY_ELEMS
#define ARRAY_ELEMS (1 << 22)
#endif

int main(void) {
    int *buf = (int *)malloc(sizeof(int) * ARRAY_ELEMS);
    if (!buf) {
        perror("malloc");
        return 1;
    }
    for (size_t i = 0; i < ARRAY_ELEMS; ++i) {
        buf[i] = (int)(i & 0xFFFF);
    }
    int64_t sum = 0;
    for (size_t i = 0; i < ARRAY_ELEMS; ++i) {
        sum += buf[i];
    }
    printf("class_memsum: sum=%lld over %d ints\n", (long long)sum, ARRAY_ELEMS);
    free(buf);
    return 0;
}
