// Standalone original-header test, deliberately independent of Qt/market data.
// No HTTP, GUI, broker, or external account. Build: c++ -std=c++17 -pthread
// -I fincept-qt/src tests/fincept_original/mcp_async_lifetime_native.cpp -o /tmp/...
#include "mcp/tools/BoundedAsyncResult.h"

#include <atomic>
#include <cassert>
#include <chrono>
#include <functional>
#include <memory>
#include <string>
#include <thread>
#include <vector>

using fincept::mcp::tools::detail::BoundedAsyncResult;

struct QuoteLike {
    int sequence = -1;
    std::string source;
    std::vector<int> bars;
};

int main() {
    // Complete-before-take: all fields move as one coherent value.
    {
        auto state = std::make_shared<BoundedAsyncResult<QuoteLike>>();
        state->complete(true, QuoteLike{17, "SYNTH", {2, 3, 5}});
        auto [ok, q] = state->take();
        assert(ok);
        assert(q.sequence == 17 && q.source == "SYNTH");
        assert(q.bars == std::vector<int>({2, 3, 5}));
    }

    // Callback never fires: the timeout path stays denied, no value.
    {
        auto state = std::make_shared<BoundedAsyncResult<QuoteLike>>();
        auto [ok, q] = state->take();
        assert(!ok && q.sequence == -1);
    }

    // Late asynchronous completion after timeout is ignored.
    {
        auto state = std::make_shared<BoundedAsyncResult<QuoteLike>>();
        std::thread late([state] {
            std::this_thread::sleep_for(std::chrono::milliseconds(15));
            state->complete(true, QuoteLike{99, "LATE", {999}});
        });
        auto [ok, q] = state->take();
        assert(!ok && q.sequence == -1);
        late.join();
        auto [second_ok, second_q] = state->take();
        assert(!second_ok && second_q.sequence == -1);
    }

    // First callback wins: duplicate callbacks must not overwrite a result.
    {
        auto state = std::make_shared<BoundedAsyncResult<QuoteLike>>();
        state->complete(true, QuoteLike{3, "FIRST", {3}});
        state->complete(true, QuoteLike{4, "SECOND", {4}});
        auto [ok, q] = state->take();
        assert(ok && q.sequence == 3 && q.source == "FIRST");
    }

    // State survives the handler stack and is freed after the late callback.
    {
        auto state = std::make_shared<BoundedAsyncResult<QuoteLike>>();
        std::weak_ptr<BoundedAsyncResult<QuoteLike>> weak = state;
        std::function<void()> delayed = [state]() {
            state->complete(true, QuoteLike{123, "DELAYED", {}});
        };
        state->take();
        state.reset();
        assert(!weak.expired());
        delayed();
        delayed = {};
        assert(weak.expired());
    }

    // Race near timeout: no torn reads, no use-after-scope, no data races.
    for (int i = 0; i != 500; ++i) {
        auto state = std::make_shared<BoundedAsyncResult<QuoteLike>>();
        std::atomic<bool> go{false};
        std::thread writer([state, &go, i] {
            while (!go.load(std::memory_order_acquire))
                std::this_thread::yield();
            state->complete(true, QuoteLike{i, "PAIR", {i, i * 2}});
        });
        go.store(true, std::memory_order_release);
        auto [ok, q] = state->take();
        if (ok) {
            assert(q.sequence == i);
            assert(q.source == "PAIR");
            assert(q.bars.size() == 2);
            assert(q.bars[0] == i && q.bars[1] == i * 2);
        } else {
            assert(q.sequence == -1);
            assert(q.bars.empty());
        }
        writer.join();
    }

    // Also cover a QVector-like, movable history container.
    {
        auto state = std::make_shared<BoundedAsyncResult<std::vector<double>>>();
        state->complete(true, {1.5, 2.5, 3.5});
        auto [ok, values] = state->take();
        assert(ok && values.size() == 3 && values[2] == 3.5);
    }
}
