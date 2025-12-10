#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#ifndef ELEMS
#define ELEMS (1u << 22)  /* 16MB worth of floats */
#endif
#ifndef REPS
#define REPS 8            /* fewer repeats to shorten runtime */
#endif

int main(void) {
    size_t elems = ELEMS;
    size_t bytes = elems * sizeof(float);

    float *a = aligned_alloc(64, bytes);
    float *b = aligned_alloc(64, bytes);
    if (!a || !b) {
        perror("alloc stream_bw");
        free(a);
        free(b);
        return 1;
    }

    for (size_t i = 0; i < elems; i++) {
        a[i] = (float)i;
    }

    for (int r = 0; r < REPS; r++) {
        for (size_t i = 0; i < elems; i++) {
            b[i] = a[i] + 1.0f;
        }
        for (size_t i = 0; i < elems; i++) {
            a[i] = b[i] + 1.0f;
        }
    }

    printf("class_stream_bw done\n");
    free(a);
    free(b);
    return 0;
}
