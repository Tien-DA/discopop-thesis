#pragma once

#include <condition_variable>
#include <cstddef>
#include <mutex>
#include <queue>

// Thread-safe bounded FIFO queue of ints with close() semantics.
//  - push() blocks while the queue is full.
//  - pop() blocks while the queue is empty and not closed; it returns false
//    only when the queue is closed AND fully drained.
//  - close() marks the end of the stream and must wake up every blocked
//    producer and consumer.
class BoundedQueue {
public:
    explicit BoundedQueue(std::size_t capacity);

    void push(int value);
    bool pop(int& value);
    void close();

private:
    std::size_t capacity_;
    std::queue<int> items_;
    bool closed_ = false;
    std::mutex mutex_;
    std::condition_variable not_empty_;
    std::condition_variable not_full_;
};
