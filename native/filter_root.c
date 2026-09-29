#include <CoreFoundation/CoreFoundation.h>
#include <Security/Security.h>
#include <CommonCrypto/CommonDigest.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifndef OVERWATCH_BOTTLE_PATH
#error "Compile with -DOVERWATCH_BOTTLE_PATH=\"/absolute/path/to/CrossOver/bottle\""
#endif

/* Correct the redundant root choice only inside the installer-selected bottle. */
static const char bottle[] = OVERWATCH_BOTTLE_PATH;
static const uint8_t redundant_root[CC_SHA1_DIGEST_LENGTH] = {
    0xdd, 0xfb, 0x16, 0xcd, 0x49, 0x31, 0xc9, 0x73, 0xa2, 0x03,
    0x7d, 0x3f, 0xc8, 0x3a, 0x4d, 0x7d, 0x77, 0x5d, 0x05, 0xe4
};

static int in_bottle(void)
{
    const char *prefix = getenv("WINEPREFIX");
    return prefix && !strcmp(prefix, bottle);
}

static int is_redundant_root(SecCertificateRef cert)
{
    if (CFGetTypeID(cert) != SecCertificateGetTypeID()) return 0;
    CFDataRef der = SecCertificateCopyData(cert);
    if (!der) return 0;
    uint8_t digest[CC_SHA1_DIGEST_LENGTH];
    CC_SHA1(CFDataGetBytePtr(der), (CC_LONG)CFDataGetLength(der), digest);
    CFRelease(der);
    return !memcmp(digest, redundant_root, sizeof(digest));
}

static OSStatus filtered_copy(SecTrustSettingsDomain domain, CFArrayRef *certs)
{
    /* dyld does not interpose calls originating in the interposer image. */
    OSStatus status = SecTrustSettingsCopyCertificates(domain, certs);
    if (status != errSecSuccess || !certs || !*certs || !in_bottle())
        return status;

    CFIndex count = CFArrayGetCount(*certs);
    CFMutableArrayRef filtered = NULL;
    for (CFIndex i = 0; i < count; i++) {
        SecCertificateRef cert = (SecCertificateRef)CFArrayGetValueAtIndex(*certs, i);
        if (is_redundant_root(cert)) {
            if (!filtered) {
                filtered = CFArrayCreateMutable(kCFAllocatorDefault, count,
                                               &kCFTypeArrayCallBacks);
                if (!filtered) return status;
                for (CFIndex j = 0; j < i; j++)
                    CFArrayAppendValue(filtered, CFArrayGetValueAtIndex(*certs, j));
            }
        } else if (filtered) {
            CFArrayAppendValue(filtered, cert);
        }
    }
    if (filtered) {
        fprintf(stderr, "[OverwatchCertFix] domain=%u excluded redundant G4 root; kept %ld/%ld certificates\n",
                (unsigned)domain, (long)CFArrayGetCount(filtered), (long)count);
        CFRelease(*certs);
        *certs = filtered;
    }
    return status;
}

__attribute__((used, section("__DATA,__interpose")))
static const struct {
    const void *replacement;
    const void *original;
} interposer = { (const void *)filtered_copy,
                 (const void *)SecTrustSettingsCopyCertificates };

__attribute__((constructor))
static void announce(void)
{
    if (in_bottle())
        fprintf(stderr, "[OverwatchCertFix] process-local root selection enabled\n");
}
