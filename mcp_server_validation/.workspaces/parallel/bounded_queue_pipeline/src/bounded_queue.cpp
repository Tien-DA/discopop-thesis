#include "bounded_queue.h"

BoundedQueue::BoundedQueue(std::size_t capacity) : capacity_(capacity) {}

void BoundedQueue::push(int value) {
    std::unique_lock<std::mutex> lock(mutex_);
    not_full_.wait(lock, [this] { return items_.size() < capacity_ || closed_; });
    if (closed_) {
        return;
    }
    items_.push(value);
    not_empty_.notify_one();
}

// BUG 1: after removing an item the queue is no longer full, but no thread
// waiting in push() is ever notified (there is no not_full_.notify_one()).
// As soon as a producer has filled the queue it sleeps forever.
bool BoundedQueue::pop(int& value) {
    std::unique_lock<std::mutex> lock(mutex_);
    not_empty_.wait(lock, [this] { return !items_.empty() || closed_; });
    if (items_.empty()) {
        return false;
    }
    value = items_.front();
    items_.pop();
    return true;
}

// BUG 2: close() sets the flag but does not wake up the threads that are
// already blocked in pop() (no not_empty_.notify_all()) or push() (no
// not_full_.notify_all()), so they keep sleeping and never see the flag.
void BoundedQueue::close() {
    std::lock_guard<std::mutex> lock(mutex_);
    closed_ = true;
}
