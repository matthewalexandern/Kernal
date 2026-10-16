// SPDX-License-Identifier: GPL-3.0-or-later
// Compile and run only in the dedicated Debian installer build guest.
#include "KythosStoragePolicy.h"
#include <cassert>

int main()
{
    using namespace KythosStoragePolicy;
    // Native manual plain root can contain /boot. Separate boot is optional.
    assert(validate(false, false, false, false) == Issue::None);
    assert(validate(false, true, false, true) == Issue::None);
    // Both guided and manual encrypted root with a public boot are allowed.
    assert(validate(true, true, false, false) == Issue::None);
    // The actual boot and selected swap invariants have precise failures.
    assert(validate(true, false, false, false) == Issue::MissingPublicBoot);
    assert(validate(true, true, true, false) == Issue::EncryptedBoot);
    assert(validate(false, true, true, false) == Issue::EncryptedBoot);
    assert(validate(true, true, false, true) == Issue::PlaintextSwap);
    return 0;
}
