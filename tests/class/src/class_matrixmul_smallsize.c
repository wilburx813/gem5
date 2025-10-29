#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#ifndef MAT_N
#define MAT_N 64
#endif

static void fill_matrix(double *m, size_t n) {
    for (size_t i = 0; i < n * n; ++i) {
        m[i] = (double)(i % 97) / 97.0;
    }
}

int main(void) {
    size_t n = MAT_N;
    size_t bytes = n * n * sizeof(double);
    double *a = (double *)aligned_alloc(64, bytes);
    double *b = (double *)aligned_alloc(64, bytes);
    double *c = (double *)aligned_alloc(64, bytes);
    if (!a || !b || !c) {
        perror("alloc matrix");
        free(a);
        free(b);
        free(c);
        return 1;
    }

    fill_matrix(a, n);
    fill_matrix(b, n);

    for (size_t i = 0; i < n; ++i) {
        for (size_t j = 0; j < n; ++j) {
            double acc = 0.0;
            for (size_t k = 0; k < n; ++k) {
                acc += a[i * n + k] * b[k * n + j];
            }
            c[i * n + j] = acc;
        }
    }

    double checksum = 0.0;
    for (size_t i = 0; i < n * n; ++i) {
        checksum += c[i];
    }

    printf("class_matrixmul: checksum=%.6f\n", checksum);

    free(a);
    free(b);
    free(c);
    return 0;
}
