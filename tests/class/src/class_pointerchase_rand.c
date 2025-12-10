#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#ifndef N
#define N (1u << 14)  /* 1M nodes (smaller heap) */
#endif
#ifndef STEPS
#define STEPS (1ULL << 18)  /* shorter walk */
#endif

typedef struct Node {
    struct Node *next;
    uint64_t pad[7];  /* force one node per cache line */
} Node;

int main(void) {
    Node *buf = aligned_alloc(64, (size_t)N * sizeof(Node));
    if (!buf) {
        perror("alloc pointerchase_rand");
        return 1;
    }

    for (size_t i = 0; i < N; i++) {
        buf[i].next = &buf[rand() % N];
    }

    Node *p = &buf[0];
    volatile uint64_t sum = 0;

    for (uint64_t i = 0; i < STEPS; i++) {
        p = p->next;
        sum += (uint64_t)p;
    }

    printf("class_pointerchase_rand sum=%lu\n", (unsigned long)sum);
    free(buf);
    return 0;
}
