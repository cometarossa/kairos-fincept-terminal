#pragma once
// This stub represents a locked/unlocked test flag. It does NOT clear any PIN.
namespace fincept::auth {
class InactivityGuard {
public:
    static InactivityGuard& instance() {
        static InactivityGuard guard;
        return guard;
    }
    bool is_terminal_locked() const { return locked_; }
    void set_test_locked(bool state) { locked_ = state; }
private:
    bool locked_ = false;
};
} // namespace fincept::auth
