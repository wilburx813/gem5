#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>

#ifndef STREAM_ELEMS
#define STREAM_ELEMS (1 << 24)
#endif
#ifndef STREAM_REPS
#define STREAM_REPS 16
#endif

int main(void) {
    size_t elems = STREAM_ELEMS;
    size_t bytes = elems * sizeof(float);
    float *src = (float *)aligned_alloc(64, bytes);
    float *dst = (float *)aligned_alloc(64, bytes);
    if (!src || !dst) {
        perror("alloc stream");
        free(src);
        free(dst);
        return 1;
    }

    for (size_t i = 0; i < elems; ++i) {
        src[i] = (float)(i & 0xFFFF);
    }

    for (int rep = 0; rep < STREAM_REPS; ++rep) {
        memcpy(dst, src, bytes);
        for (size_t i = 0; i < elems; ++i) {
            dst[i] += 1.0f;
        }
        memcpy(src, dst, bytes);
    }

    double checksum = 0.0;
    for (size_t i = 0; i < elems; ++i) {
        checksum += src[i];
    }
    printf("class_streamcopy: checksum=%.3f\n", checksum);

    free(src);
    free(dst);
    return 0;
}
