#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>

#ifndef NODE_COUNT
#define NODE_COUNT (1 << 18)
#endif

typedef struct Node {
    struct Node *next;
    uint32_t pad[4];
} Node;

static Node *build_random_ring(size_t count) {
    Node *nodes = (Node *)aligned_alloc(64, sizeof(Node) * count);
    if (!nodes) {
        return NULL;
    }
    for (size_t i = 0; i < count; ++i) {
        nodes[i].next = &nodes[i];
    }
    for (size_t i = 0; i < count; ++i) {
        size_t j = rand() % count;
        Node *tmp = nodes[i].next;
        nodes[i].next = nodes[j].next;
        nodes[j].next = tmp;
    }
    return nodes;
}

int main(void) {
    srand(42);
    Node *ring = build_random_ring(NODE_COUNT);
    if (!ring) {
        perror("alloc ring");
        return 1;
    }
    volatile Node *cursor = ring;
    uint64_t steps = (uint64_t)NODE_COUNT * 8;
    uint64_t visits = 0;
    for (uint64_t i = 0; i < steps; ++i) {
        cursor = cursor->next;
        visits += (uintptr_t)cursor & 1U;
    }
    printf("class_cachethrash: steps=%llu visits=%llu\n",
           (unsigned long long)steps,
           (unsigned long long)visits);
    free((void *)ring);
    return 0;
}
