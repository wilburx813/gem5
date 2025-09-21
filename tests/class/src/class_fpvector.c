#include <stdio.h>
#include <stdlib.h>

#ifndef ARRAY_ELEMS
#define ARRAY_ELEMS (1 << 22)
#endif

int main(void) {
    float *buf = (float *)malloc(sizeof(float) * ARRAY_ELEMS);
    if (!buf) {
        perror("malloc");
        return 1;
    }

    for (size_t i = 0; i < ARRAY_ELEMS; ++i) {
        buf[i] = (float)((i % 1024) / 1024.0f);
    }

    float sum = 0.0f;
    float prod = 1.0f;
    for (size_t i = 0; i < ARRAY_ELEMS; ++i) {
        sum += buf[i];
        prod *= 1.0f + buf[i] * 1e-6f;
    }

    printf("class_fpvector: sum=%f prod=%f over %d floats\n", sum, prod, ARRAY_ELEMS);

    free(buf);
    return 0;
}
