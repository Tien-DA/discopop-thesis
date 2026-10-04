#include <atomic>
#include <chrono>
#include <cstdlib>
#include <functional>
#include <future>
#include <iostream>
#include <memory>
#include <thread>
#include <vector>

#include "bounded_queue.h"
#include "pipeline.h"

namespace {

// Runs 'body' on a helper thread and waits for at most 'seconds'. A test
// that deadlocks is reported as a failure (the stuck helper thread is
// abandoned; main() terminates the process with _Exit at the end).
bool run_with_timeout(std::function<bool()> body, int seconds, bool& timed_out) {
    auto promise = std::make_shared<std::promise<bool>>();
    std::future<bool> future = promise->get_future();
    std::thread([promise, body] { promise->set_value(body()); }).detach();
    if (future.wait_for(std::chrono::seconds(seconds)) == std::future_status::timeout) {
        timed_out = true;
        return false;
    }
    return future.get();
}

bool test_queue_fifo_order_and_close() {
    BoundedQueue queue(4);
    queue.push(1);
    queue.push(2);
    queue.push(3);
    queue.close();
    int value = 0;
    if (!queue.pop(value) || value != 1) return false;
    if (!queue.pop(value) || value != 2) return false;
    if (!queue.pop(value) || value != 3) return false;
    return !queue.pop(value);  // closed and drained
}

bool test_close_wakes_blocked_consumers() {
    BoundedQueue queue(4);
    std::atomic<int> returned_false{0};
    std::vector<std::thread> consumers;
    for (int i = 0; i < 3; ++i) {
        consumers.emplace_back([&] {
            int value = 0;
            if (!queue.pop(value)) ++returned_false;
        });
    }
    std::this_thread::sleep_for(std::chrono::milliseconds(200));  // let them block
    queue.close();
    for (std::thread& t : consumers) t.join();
    return returned_false == 3;
}

bool test_blocked_producer_resumes_after_pop() {
    BoundedQueue queue(2);
    std::thread producer([&] {
        for (int i = 0; i < 100; ++i) queue.push(i);
        queue.close();
    });
    int value = 0;
    int expected = 0;
    while (queue.pop(value)) {
        if (value != expected++) {
            producer.join();
            return false;
        }
    }
    producer.join();
    return expected == 100;
}

bool test_close_wakes_blocked_producer() {
    BoundedQueue queue(1);
    queue.push(7);  // queue is now full
    std::thread producer([&] { queue.push(8); });  // blocks: full
    std::this_thread::sleep_for(std::chrono::milliseconds(200));
    queue.close();
    producer.join();
    return true;
}

bool test_pipeline_matches_reference() {
    std::vector<int> input;
    for (int i = -500; i <= 500; ++i) input.push_back(i);
    const long long expected = pipeline_reference(input);
    const std::size_t capacities[] = {1, 2, 5, 64};
    for (std::size_t capacity : capacities) {
        for (int workers = 1; workers <= 4; ++workers) {
            if (run_pipeline(input, capacity, workers) != expected) return false;
        }
    }
    return true;
}

bool test_pipeline_empty_and_single_item() {
    return run_pipeline({}, 3, 2) == 0 && run_pipeline({6}, 1, 3) == 37;
}

}  // namespace

int main() {
    struct Test {
        const char* name;
        bool (*function)();
    };

    const Test tests[] = {
        {"queue_fifo_order_and_close", test_queue_fifo_order_and_close},
        {"close_wakes_blocked_consumers", test_close_wakes_blocked_consumers},
        {"blocked_producer_resumes_after_pop", test_blocked_producer_resumes_after_pop},
        {"close_wakes_blocked_producer", test_close_wakes_blocked_producer},
        {"pipeline_matches_reference", test_pipeline_matches_reference},
        {"pipeline_empty_and_single_item", test_pipeline_empty_and_single_item}
    };

    int failures = 0;
    bool any_timeout = false;
    for (const Test& test : tests) {
        bool timed_out = false;
        bool passed = run_with_timeout(test.function, 10, timed_out);
        any_timeout = any_timeout || timed_out;
        if (passed) {
            std::cout << "[PASS] " << test.name << std::endl;
        } else if (timed_out) {
            std::cerr << "[FAIL] " << test.name << " (timeout: deadlock or lost wake-up)" << std::endl;
            ++failures;
        } else {
            std::cerr << "[FAIL] " << test.name << std::endl;
            ++failures;
        }
    }

    if (failures > 0) {
        std::cerr << failures << " test(s) failed." << std::endl;
        std::_Exit(1);  // do not wait for abandoned (deadlocked) threads
    }

    std::cout << "All tests passed." << std::endl;
    return 0;
}
