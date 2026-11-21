#pragma once
// BoundedAsyncResult.h — thread-safe handoff for timeout-bounded MCP tools.
//
// A queued service callback can arrive after run_async_wait() has timed out.
// Never capture handler-stack result storage in that callback. Instead capture
// shared_ptr<BoundedAsyncResult<T>> and seal it with take() on the worker.
// Late/duplicate completions are ignored, and no QObject or broker is involved.
//
// This is a value handoff, NOT a timeout implementation, provider adapter,
// authentication layer, or cancellation of the underlying service operation.

#include <mutex>
#include <utility>

namespace fincept::mcp::tools::detail {

template <typename T>
class BoundedAsyncResult {
  public:
    BoundedAsyncResult() = default;
    BoundedAsyncResult(const BoundedAsyncResult&) = delete;
    BoundedAsyncResult& operator=(const BoundedAsyncResult&) = delete;

    // Callback thread: complete exactly once; do not hold this mutex while
    // notifying run_async_wait via signal_done().
    void complete(bool success, T value) {
        std::lock_guard<std::mutex> guard(mutex_);
        if (sealed_ || completed_)
            return;
        value_ = std::move(value);
        success_ = success;
        completed_ = true;
    }

    // Worker thread: called once, whether the wait completed or timed out.
    // Seals state before the local handler scope unwinds.
    std::pair<bool, T> take() {
        std::lock_guard<std::mutex> guard(mutex_);
        if (sealed_)
            return {false, {}};
        sealed_ = true;
        return {completed_ && success_, std::move(value_)};
    }

  private:
    std::mutex mutex_;
    bool completed_ = false;
    bool sealed_ = false;
    bool success_ = false;
    T value_{};
};

} // namespace fincept::mcp::tools::detail
