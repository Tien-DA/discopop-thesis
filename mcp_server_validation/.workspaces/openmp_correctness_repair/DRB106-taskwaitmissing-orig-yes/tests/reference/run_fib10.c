#include <stdio.h>

int fib(unsigned int n);

int main(void)
{
    int result = 0;
#pragma omp parallel
    {
#pragma omp single
        result = fib(10);
    }
    printf("%d\n", result);
    return 0;
}
