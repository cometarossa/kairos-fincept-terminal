#pragma once
// Conservative delivery-path evidence for Fincept's existing quote service.
//
// This records *how* a quote reached a consumer, not the exchange timestamp,
// provider accuracy, or its fitness for scientific/trading decisions. A
// successful provider request does NOT prove market freshness.

namespace fincept::services {

enum class QuoteDeliveryOrigin {
    Unknown,
    ProviderResponse,
    UnexpiredCacheHit,
    ProviderFailureCacheHit,
};

constexpr const char* quote_delivery_origin_name(QuoteDeliveryOrigin origin) noexcept {
    switch (origin) {
    case QuoteDeliveryOrigin::ProviderResponse:
        return "provider_response";
    case QuoteDeliveryOrigin::UnexpiredCacheHit:
        return "unexpired_cache_hit";
    case QuoteDeliveryOrigin::ProviderFailureCacheHit:
        return "provider_failure_cache_hit";
    case QuoteDeliveryOrigin::Unknown:
    default:
        return "unknown";
    }
}

constexpr bool quote_market_asof_verified(QuoteDeliveryOrigin) noexcept {
    return false; // Existing yfinance adapter does not attest exchange as-of.
}

constexpr bool quote_execution_eligible(QuoteDeliveryOrigin) noexcept {
    return false; // No quote delivery route grants KAIROS execution authority.
}

} // namespace fincept::services
