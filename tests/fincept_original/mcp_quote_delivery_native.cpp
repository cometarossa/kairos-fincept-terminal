#include "services/markets/QuoteDeliveryEvidence.h"

#include <cassert>
#include <string_view>

using namespace fincept::services;

int main() {
    constexpr QuoteDeliveryOrigin paths[] = {
        QuoteDeliveryOrigin::Unknown,
        QuoteDeliveryOrigin::ProviderResponse,
        QuoteDeliveryOrigin::UnexpiredCacheHit,
        QuoteDeliveryOrigin::ProviderFailureCacheHit,
        static_cast<QuoteDeliveryOrigin>(-1),
    };
    constexpr std::string_view expected[] = {
        "unknown", "provider_response", "unexpired_cache_hit",
        "provider_failure_cache_hit", "unknown",
    };
    for (unsigned i = 0; i < 5; ++i) {
        assert(std::string_view(quote_delivery_origin_name(paths[i])) == expected[i]);
        assert(!quote_market_asof_verified(paths[i]));
        assert(!quote_execution_eligible(paths[i]));
    }
    static_assert(!quote_market_asof_verified(QuoteDeliveryOrigin::ProviderResponse));
    static_assert(!quote_execution_eligible(QuoteDeliveryOrigin::ProviderResponse));
}
