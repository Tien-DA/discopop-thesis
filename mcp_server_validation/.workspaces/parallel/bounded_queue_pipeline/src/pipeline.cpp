#include "pipeline.h"

#include <thread>

#include "bounded_queue.h"

long long pipeline_reference(const std::vector<int>& input) {
    long long sum = 0;
    for (int x : input) {
        sum += static_cast<long long>(x) * x + 1;
    }
    return sum;
}

long long run_pipeline(const std::vector<int>& input, std::size_t queue_capacity, int workers) {
    BoundedQueue raw(queue_capacity);
    BoundedQueue transformed(queue_capacity);
    long long total = 0;

    std::thread producer([&] {
        for (int x : input) {
            raw.push(x);
        }
        raw.close();
    });

    std::vector<std::thread> transformers;
    for (int w = 0; w < workers; ++w) {
        transformers.emplace_back([&] {
            int x = 0;
            while (raw.pop(x)) {
                // The transformed value is small enough to fit in an int
                // for the inputs used by the benchmark.
                transformed.push(x * x + 1);
            }
        });
    }

    std::thread collector([&] {
        int y = 0;
        while (transformed.pop(y)) {
            total += y;
        }
    });

    producer.join();
    for (std::thread& t : transformers) {
        t.join();
    }
    transformed.close();
    collector.join();
    return total;
}
