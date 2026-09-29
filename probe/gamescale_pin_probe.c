/*
 * Minimal x64 Windows probe for the Overwatch Korea gamescale64.dll trust
 * check.  It intentionally uses no CRT and only Win32 imports so it can be
 * built with a bare Windows cross toolchain.
 *
 * Build (when a Windows-targeting clang and import libraries are available):
 *   clang --target=x86_64-w64-windows-gnu -nostdlib -fuse-ld=lld \
 *     -Wl,/entry:mainCRTStartup,/subsystem:console \
 *     -o gamescale-pin-probe.exe gamescale_pin_probe.c \
 *     -lkernel32 -lcrypt32 -lwintrust
 *
 * Usage:
 *   gamescale-pin-probe.exe "C:\\path\\to\\_retail_\\gamescale64.dll"
 */

typedef unsigned char BYTE;
typedef unsigned short WORD;
typedef unsigned long DWORD;
typedef long LONG;
typedef unsigned long long QWORD;
typedef unsigned short WCHAR;
typedef int BOOL;
typedef void *HANDLE;
typedef void *LPVOID;
typedef const WCHAR *LPCWSTR;
typedef WCHAR *LPWSTR;
typedef DWORD *PDWORD;

#define WINAPI __attribute__((stdcall))
#define DLLIMPORT __declspec(dllimport)
#define TRUE 1
#define FALSE 0
#define NULL ((void *)0)

#define STD_OUTPUT_HANDLE ((DWORD)-11)
#define INVALID_HANDLE_VALUE ((HANDLE)(QWORD)-1)
#define CP_UTF8 65001
#define WTD_UI_NONE 2
#define WTD_REVOKE_NONE 0
#define WTD_CHOICE_FILE 1
#define WTD_STATEACTION_VERIFY 1
#define WTD_STATEACTION_CLOSE 2
#define WTD_UICONTEXT_EXECUTE 0
#define WTD_CACHE_ONLY_URL_RETRIEVAL 0x00002000
#define X509_ASN_ENCODING 0x00000001
#define PKCS_7_ASN_ENCODING 0x00010000
#define CALG_SHA1 0x00008004
#define CERT_NAME_SIMPLE_DISPLAY_TYPE 4
#define GENERIC_READ 0x80000000
#define FILE_SHARE_READ 0x00000001
#define OPEN_EXISTING 3
#define FILE_ATTRIBUTE_NORMAL 0x00000080
#define CERT_STORE_PROV_SYSTEM_W ((const char *)10)
#define CERT_SYSTEM_STORE_LOCAL_MACHINE 0x00020000
#define CERT_STORE_OPEN_EXISTING_FLAG 0x00004000
#define CERT_STORE_ADD_REPLACE_EXISTING 3
#define CERT_SHA1_HASH_PROP_ID 3
#define MAX_CERTIFICATE_BYTES (1024 * 1024)

typedef struct _GUID {
  DWORD Data1;
  WORD Data2;
  WORD Data3;
  BYTE Data4[8];
} GUID;

typedef struct _FILETIME { DWORD dwLowDateTime; DWORD dwHighDateTime; } FILETIME;
typedef struct _CERT_TRUST_STATUS { DWORD dwErrorStatus; DWORD dwInfoStatus; } CERT_TRUST_STATUS;

typedef struct _CERT_CONTEXT {
  DWORD dwCertEncodingType;
  BYTE *pbCertEncoded;
  DWORD cbCertEncoded;
  void *pCertInfo;
  void *hCertStore;
} CERT_CONTEXT, *PCCERT_CONTEXT;

typedef struct _CERT_CHAIN_ELEMENT {
  DWORD cbSize;
  PCCERT_CONTEXT pCertContext;
  CERT_TRUST_STATUS TrustStatus;
  void *pRevocationInfo;
  void *pIssuanceUsage;
  void *pApplicationUsage;
  WCHAR *pwszExtendedErrorInfo;
} CERT_CHAIN_ELEMENT, *PCERT_CHAIN_ELEMENT;

typedef struct _CERT_SIMPLE_CHAIN {
  DWORD cbSize;
  CERT_TRUST_STATUS TrustStatus;
  DWORD cElement;
  PCERT_CHAIN_ELEMENT *rgpElement;
  void *pTrustListInfo;
  BOOL fHasRevocationFreshnessTime;
  DWORD dwRevocationFreshnessTime;
} CERT_SIMPLE_CHAIN, *PCERT_SIMPLE_CHAIN;

typedef struct _CERT_CHAIN_CONTEXT {
  DWORD cbSize;
  CERT_TRUST_STATUS TrustStatus;
  DWORD cChain;
  PCERT_SIMPLE_CHAIN *rgpChain;
  DWORD cLowerQualityChainContext;
  struct _CERT_CHAIN_CONTEXT **rgpLowerQualityChainContext;
  BOOL fHasRevocationFreshnessTime;
  DWORD dwRevocationFreshnessTime;
  DWORD dwCreateFlags;
  GUID ChainId;
} CERT_CHAIN_CONTEXT, *PCCERT_CHAIN_CONTEXT;

typedef struct _WINTRUST_FILE_INFO {
  DWORD cbStruct;
  LPCWSTR pcwszFilePath;
  HANDLE hFile;
  GUID *pgKnownSubject;
} WINTRUST_FILE_INFO;

typedef struct _WINTRUST_DATA {
  DWORD cbStruct;
  LPVOID pPolicyCallbackData;
  LPVOID pSIPClientData;
  DWORD dwUIChoice;
  DWORD fdwRevocationChecks;
  DWORD dwUnionChoice;
  WINTRUST_FILE_INFO *pFile;
  DWORD dwStateAction;
  HANDLE hWVTStateData;
  WCHAR *pwszURLReference;
  DWORD dwProvFlags;
  DWORD dwUIContext;
  LPVOID pSignatureSettings;
} WINTRUST_DATA;

typedef struct _CRYPT_PROVIDER_SGNR {
  DWORD cbStruct;
  FILETIME sftVerifyAsOf;
  DWORD csCertChain;
  LPVOID pasCertChain;
  DWORD dwSignerType;
  LPVOID psSigner;
  DWORD dwError;
  DWORD csCounterSigners;
  LPVOID pasCounterSigners;
  PCCERT_CHAIN_CONTEXT pChainContext;
} CRYPT_PROVIDER_SGNR;

typedef struct _CRYPT_PROVIDER_DATA CRYPT_PROVIDER_DATA;

/* These checks keep the hand-written declarations on the x64 Windows ABI. */
_Static_assert(sizeof(DWORD) == 4, "DWORD must be 32 bits");
_Static_assert(sizeof(WINTRUST_FILE_INFO) == 32, "WINTRUST_FILE_INFO x64 layout");
_Static_assert(sizeof(WINTRUST_DATA) == 88, "WINTRUST_DATA x64 layout");
_Static_assert(sizeof(CRYPT_PROVIDER_SGNR) == 64, "CRYPT_PROVIDER_SGNR x64 layout");

DLLIMPORT HANDLE WINAPI GetStdHandle(DWORD);
DLLIMPORT BOOL WINAPI WriteFile(HANDLE, const void *, DWORD, PDWORD, LPVOID);
DLLIMPORT DWORD WINAPI GetLastError(void);
DLLIMPORT LPCWSTR WINAPI GetCommandLineW(void);
DLLIMPORT void WINAPI ExitProcess(DWORD);
DLLIMPORT int WINAPI WideCharToMultiByte(unsigned int, DWORD, LPCWSTR, int, char *, int, LPCWSTR, BOOL *);
DLLIMPORT HANDLE WINAPI CreateFileW(LPCWSTR, DWORD, DWORD, LPVOID, DWORD, DWORD, HANDLE);
DLLIMPORT DWORD WINAPI GetFileSize(HANDLE, PDWORD);
DLLIMPORT BOOL WINAPI ReadFile(HANDLE, LPVOID, DWORD, PDWORD, LPVOID);
DLLIMPORT BOOL WINAPI CloseHandle(HANDLE);
DLLIMPORT LONG WINAPI WinVerifyTrust(HANDLE, GUID *, LPVOID);
DLLIMPORT CRYPT_PROVIDER_DATA *WINAPI WTHelperProvDataFromStateData(HANDLE);
DLLIMPORT CRYPT_PROVIDER_SGNR *WINAPI WTHelperGetProvSignerFromChain(CRYPT_PROVIDER_DATA *, DWORD, BOOL, DWORD);
DLLIMPORT BOOL WINAPI CryptHashCertificate(HANDLE, DWORD, DWORD, const BYTE *, DWORD, BYTE *, PDWORD);
DLLIMPORT DWORD WINAPI CertGetNameStringW(PCCERT_CONTEXT, DWORD, DWORD, LPVOID, LPWSTR, DWORD);
DLLIMPORT HANDLE WINAPI CertOpenStore(const char *, DWORD, HANDLE, DWORD, const void *);
DLLIMPORT BOOL WINAPI CertAddEncodedCertificateToStore(HANDLE, DWORD, const BYTE *, DWORD, DWORD, PCCERT_CONTEXT *);
DLLIMPORT BOOL WINAPI CertCloseStore(HANDLE, DWORD);
DLLIMPORT PCCERT_CONTEXT WINAPI CertEnumCertificatesInStore(HANDLE, PCCERT_CONTEXT);
DLLIMPORT BOOL WINAPI CertGetCertificateContextProperty(PCCERT_CONTEXT, DWORD, LPVOID, PDWORD);
DLLIMPORT BOOL WINAPI CertDeleteCertificateFromStore(PCCERT_CONTEXT);

static const GUID WINTRUST_ACTION_GENERIC_VERIFY_V2 = {
  0xaac56b, 0xcd44, 0x11d0, {0x8c, 0xc2, 0x00, 0xc0, 0x4f, 0xc2, 0x95, 0xee}
};
static const BYTE PINNED_ROOT_SHA1[20] = {
  0x05, 0x63, 0xb8, 0x63, 0x0d, 0x62, 0xd7, 0x5a, 0xbb, 0xc8,
  0xab, 0x1e, 0x4b, 0xdf, 0xb5, 0xa8, 0x99, 0xb2, 0x4d, 0x43
};
static const BYTE REDUNDANT_G4_ROOT_SHA1[20] = {
  0xdd, 0xfb, 0x16, 0xcd, 0x49, 0x31, 0xc9, 0x73, 0xa2, 0x03,
  0x7d, 0x3f, 0xc8, 0x3a, 0x4d, 0x7d, 0x77, 0x5d, 0x05, 0xe4
};
static const BYTE FIX_G4_CROSS_SHA1[20] = {
  0xa9, 0x9d, 0x5b, 0x79, 0xe9, 0xf1, 0xcd, 0xa5, 0x9c, 0xda,
  0xb6, 0x37, 0x31, 0x69, 0xd5, 0x35, 0x3f, 0x58, 0x74, 0xc6
};

static HANDLE g_output;
static BYTE g_certificate[MAX_CERTIFICATE_BYTES];

static void zero(void *p, DWORD n) {
  BYTE *b = (BYTE *)p;
  while (n--) *b++ = 0;
}

static void out(const char *s) {
  DWORD n = 0, done;
  while (s[n]) n++;
  WriteFile(g_output, s, n, &done, NULL);
}

static void hex32(DWORD v) {
  static const char d[] = "0123456789ABCDEF";
  char b[9];
  DWORD i;
  for (i = 0; i != 8; i++) b[i] = d[(v >> ((7 - i) * 4)) & 15];
  b[8] = 0;
  out(b);
}

static void dec(DWORD v) {
  char b[11];
  DWORD n = 0;
  if (!v) { out("0"); return; }
  while (v) { b[n++] = (char)('0' + (v % 10)); v /= 10; }
  while (n) { char c[2]; c[0] = b[--n]; c[1] = 0; out(c); }
}

static void sha1(const BYTE h[20]) {
  DWORD i;
  for (i = 0; i != 20; i++) {
    static const char d[] = "0123456789ABCDEF";
    char b[3]; b[0] = d[h[i] >> 4]; b[1] = d[h[i] & 15]; b[2] = 0; out(b);
  }
}

static BOOL equal20(const BYTE a[20], const BYTE b[20]) {
  DWORD i;
  for (i = 0; i != 20; i++) if (a[i] != b[i]) return FALSE;
  return TRUE;
}

static BOOL wide_equal(const WCHAR *a, const WCHAR *b) {
  while (*a && *b) {
    if (*a != *b) return FALSE;
    a++; b++;
  }
  return *a == *b;
}

static BOOL no_more_args(const WCHAR *p) {
  while (*p == ' ' || *p == '\t') p++;
  return *p == 0;
}

static void wide_out(const WCHAR *s) {
  char utf8[1024];
  int n = WideCharToMultiByte(CP_UTF8, 0, s, -1, utf8, (int)sizeof(utf8), NULL, NULL);
  if (n > 1) out(utf8);
  else out("<subject unavailable>");
}

static const WCHAR *skip_arg(const WCHAR *p) {
  BOOL quoted = FALSE;
  while (*p == ' ' || *p == '\t') p++;
  if (*p == '"') { quoted = TRUE; p++; }
  while (*p && (quoted ? *p != '"' : (*p != ' ' && *p != '\t'))) p++;
  if (quoted && *p == '"') p++;
  return p;
}

static BOOL next_arg(const WCHAR **cursor, WCHAR *dst, DWORD cap) {
  const WCHAR *p = *cursor;
  DWORD n = 0;
  BOOL quoted = FALSE;
  while (*p == ' ' || *p == '\t') p++;
  if (!*p) return FALSE;
  if (*p == '"') { quoted = TRUE; p++; }
  while (*p && (quoted ? *p != '"' : (*p != ' ' && *p != '\t'))) {
    if (n + 1 < cap) dst[n++] = *p;
    p++;
  }
  dst[n] = 0;
  if (quoted && *p == '"') p++;
  *cursor = p;
  return n != 0;
}

static void dump_chain(PCCERT_CHAIN_CONTEXT context) {
  DWORD i, j;
  if (!context) { out("pChainContext             = NULL\r\n"); return; }
  out("pChainContext.cChain      = "); dec(context->cChain); out("\r\n");
  out("pChainContext.error       = 0x"); hex32(context->TrustStatus.dwErrorStatus); out("\r\n");
  for (i = 0; i < context->cChain; i++) {
    PCERT_SIMPLE_CHAIN chain = context->rgpChain[i];
    out("  chain["); dec(i); out("].error          = 0x"); hex32(chain->TrustStatus.dwErrorStatus); out("\r\n");
    out("  chain["); dec(i); out("].cElement       = "); dec(chain->cElement); out("\r\n");
    for (j = 0; j < chain->cElement; j++) {
      PCERT_CHAIN_ELEMENT element = chain->rgpElement[j];
      BYTE hash[20]; DWORD hash_len = 20; WCHAR subject[256];
      zero(subject, sizeof(subject));
      out("    ["); dec(j); out("] error=0x"); hex32(element->TrustStatus.dwErrorStatus); out(" subject=");
      CertGetNameStringW(element->pCertContext, CERT_NAME_SIMPLE_DISPLAY_TYPE, 0, NULL, subject, 256);
      wide_out(subject); out("\r\n");
      /* CryptHashCertificate takes (provider, ALG_ID, flags), not an encoding. */
      if (CryptHashCertificate(NULL, CALG_SHA1, 0,
                               element->pCertContext->pbCertEncoded, element->pCertContext->cbCertEncoded,
                               hash, &hash_len) && hash_len == 20) {
        out("        DER SHA1="); sha1(hash);
        if (j + 1 == chain->cElement) {
          out("  <-- ROOT; PIN "); out(equal20(hash, PINNED_ROOT_SHA1) ? "MATCH" : "MISMATCH");
        }
        out("\r\n");
      } else {
        out("        CryptHashCertificate failed: "); dec(GetLastError()); out("\r\n");
      }
    }
  }
}

/* Explicit opt-in repair helper: add one DER certificate to LocalMachine\\CA. */
static DWORD add_ca_certificate(const WCHAR *path) {
  HANDLE file, store;
  DWORD size, high = 0, read = 0, hash_len = 20;
  BYTE hash[20];

  file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                     FILE_ATTRIBUTE_NORMAL, NULL);
  if (file == INVALID_HANDLE_VALUE) {
    out("CreateFileW failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  size = GetFileSize(file, &high);
  if (high || size == (DWORD)-1 || size == 0 || size > MAX_CERTIFICATE_BYTES) {
    out("Certificate size rejected (must be 1..1048576 bytes)\r\n");
    CloseHandle(file); return 1;
  }
  if (!ReadFile(file, g_certificate, size, &read, NULL) || read != size) {
    out("ReadFile failed: "); dec(GetLastError()); out("\r\n");
    CloseHandle(file); return 1;
  }
  CloseHandle(file);

  if (!CryptHashCertificate(NULL, CALG_SHA1, 0, g_certificate, size, hash, &hash_len) || hash_len != 20) {
    out("Certificate SHA1 failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  out("Certificate DER SHA1      = "); sha1(hash); out("\r\n");
  if (!equal20(hash, FIX_G4_CROSS_SHA1)) {
    out("Refused: DER is not the required DigiCert G4 cross certificate\r\n"); return 2;
  }

  store = CertOpenStore(CERT_STORE_PROV_SYSTEM_W, X509_ASN_ENCODING, NULL,
                        CERT_SYSTEM_STORE_LOCAL_MACHINE | CERT_STORE_OPEN_EXISTING_FLAG, L"CA");
  if (!store) {
    out("CertOpenStore(LocalMachine\\CA) failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  if (!CertAddEncodedCertificateToStore(store, X509_ASN_ENCODING, g_certificate, size,
                                        CERT_STORE_ADD_REPLACE_EXISTING, NULL)) {
    out("CertAddEncodedCertificateToStore failed: "); dec(GetLastError()); out("\r\n");
    CertCloseStore(store, 0); return 1;
  }
  if (!CertCloseStore(store, 0)) {
    out("CertCloseStore failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  out("Added to LocalMachine\\CA (replace-existing)\r\n");
  return 0;
}

/* Restore only the exact original G4 root supplied by the installer. */
static DWORD restore_original_root(const WCHAR *path) {
  HANDLE file, store;
  DWORD size, high = 0, read = 0, hash_len = 20;
  BYTE hash[20];

  file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                     FILE_ATTRIBUTE_NORMAL, NULL);
  if (file == INVALID_HANDLE_VALUE) {
    out("CreateFileW failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  size = GetFileSize(file, &high);
  if (high || size == (DWORD)-1 || size == 0 || size > MAX_CERTIFICATE_BYTES) {
    out("Certificate size rejected (must be 1..1048576 bytes)\r\n");
    CloseHandle(file); return 1;
  }
  if (!ReadFile(file, g_certificate, size, &read, NULL) || read != size) {
    out("ReadFile failed: "); dec(GetLastError()); out("\r\n");
    CloseHandle(file); return 1;
  }
  CloseHandle(file);
  if (!CryptHashCertificate(NULL, CALG_SHA1, 0, g_certificate, size, hash, &hash_len) || hash_len != 20) {
    out("Certificate SHA1 failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  out("Certificate DER SHA1      = "); sha1(hash); out("\r\n");
  if (!equal20(hash, REDUNDANT_G4_ROOT_SHA1)) {
    out("Refused: DER is not the original DigiCert Trusted Root G4 certificate\r\n"); return 2;
  }
  store = CertOpenStore(CERT_STORE_PROV_SYSTEM_W, X509_ASN_ENCODING, NULL,
                        CERT_SYSTEM_STORE_LOCAL_MACHINE | CERT_STORE_OPEN_EXISTING_FLAG, L"Root");
  if (!store) {
    out("CertOpenStore(LocalMachine\\Root) failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  if (!CertAddEncodedCertificateToStore(store, X509_ASN_ENCODING, g_certificate, size,
                                        CERT_STORE_ADD_REPLACE_EXISTING, NULL)) {
    out("CertAddEncodedCertificateToStore failed: "); dec(GetLastError()); out("\r\n");
    CertCloseStore(store, 0); return 1;
  }
  if (!CertCloseStore(store, 0)) {
    out("CertCloseStore failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  out("Restored original G4 root to LocalMachine\\Root\r\n");
  return 0;
}

/* Delete one of the two certificates this repair owns, selected in code. */
static DWORD remove_known_certificate(const WCHAR *store_name, const BYTE wanted[20]) {
  HANDLE store;
  PCCERT_CONTEXT context = NULL;

  store = CertOpenStore(CERT_STORE_PROV_SYSTEM_W, X509_ASN_ENCODING, NULL,
                        CERT_SYSTEM_STORE_LOCAL_MACHINE | CERT_STORE_OPEN_EXISTING_FLAG, store_name);
  if (!store) {
    out("CertOpenStore failed: "); dec(GetLastError()); out("\r\n"); return 1;
  }
  while ((context = CertEnumCertificatesInStore(store, context)) != NULL) {
    BYTE actual[20]; DWORD actual_len = 20;
    if (CertGetCertificateContextProperty(context, CERT_SHA1_HASH_PROP_ID, actual, &actual_len) &&
        actual_len == 20 && equal20(actual, wanted)) {
      out("Deleting LocalMachine\\"); wide_out(store_name); out(" SHA1="); sha1(actual); out("\r\n");
      if (!CertDeleteCertificateFromStore(context)) {
        out("CertDeleteCertificateFromStore failed: "); dec(GetLastError()); out("\r\n");
        CertCloseStore(store, 0); return 1;
      }
      context = NULL; /* delete consumes the enumeration context */
      if (!CertCloseStore(store, 0)) {
        out("CertCloseStore failed: "); dec(GetLastError()); out("\r\n"); return 1;
      }
      out("Deleted exactly one matching certificate\r\n"); return 0;
    }
  }
  CertCloseStore(store, 0);
  out("No certificate with that SHA1 was found; no change made\r\n"); return 3;
}

void mainCRTStartup(void) {
  static WCHAR path[32768];
  static WCHAR first_argument[32768];
  const WCHAR *command = GetCommandLineW();
  WINTRUST_FILE_INFO file;
  WINTRUST_DATA trust;
  LONG result;
  CRYPT_PROVIDER_DATA *data;
  CRYPT_PROVIDER_SGNR *signer;

  g_output = GetStdHandle(STD_OUTPUT_HANDLE);
  command = skip_arg(command);
  if (!next_arg(&command, first_argument, 32768)) {
    out("Usage: gamescale-pin-probe.exe <gamescale64.dll>\r\n");
    out("   or: gamescale-pin-probe.exe --add-ca <certificate.der>\r\n");
    out("   or: gamescale-pin-probe.exe --remove-redundant-root\r\n");
    out("   or: gamescale-pin-probe.exe --remove-fix-ca\r\n");
    out("   or: gamescale-pin-probe.exe --restore-original-root <certificate.der>\r\n");
    ExitProcess(2);
  }
  if (wide_equal(first_argument, L"--add-ca")) {
    if (!next_arg(&command, path, 32768) || !no_more_args(command)) {
      out("Missing certificate path after --add-ca\r\n"); ExitProcess(2);
    }
    ExitProcess(add_ca_certificate(path));
  }
  if (wide_equal(first_argument, L"--remove-redundant-root")) {
    if (!no_more_args(command)) { out("--remove-redundant-root takes no arguments\r\n"); ExitProcess(2); }
    ExitProcess(remove_known_certificate(L"Root", REDUNDANT_G4_ROOT_SHA1));
  }
  if (wide_equal(first_argument, L"--remove-fix-ca")) {
    if (!no_more_args(command)) { out("--remove-fix-ca takes no arguments\r\n"); ExitProcess(2); }
    ExitProcess(remove_known_certificate(L"CA", FIX_G4_CROSS_SHA1));
  }
  if (wide_equal(first_argument, L"--restore-original-root")) {
    if (!next_arg(&command, path, 32768) || !no_more_args(command)) {
      out("Usage: --restore-original-root <certificate.der>\r\n"); ExitProcess(2);
    }
    ExitProcess(restore_original_root(path));
  }
  if (!no_more_args(command)) { out("The diagnostic mode takes exactly one DLL path\r\n"); ExitProcess(2); }
  {
    DWORD i = 0;
    while (first_argument[i] && i + 1 < 32768) { path[i] = first_argument[i]; i++; }
    path[i] = 0;
  }

  zero(&file, sizeof(file)); zero(&trust, sizeof(trust));
  file.cbStruct = sizeof(file); file.pcwszFilePath = path;
  trust.cbStruct = sizeof(trust);
  trust.dwUIChoice = WTD_UI_NONE;
  trust.fdwRevocationChecks = WTD_REVOKE_NONE;
  trust.dwUnionChoice = WTD_CHOICE_FILE;
  trust.pFile = &file;
  trust.dwStateAction = WTD_STATEACTION_VERIFY;
  trust.dwProvFlags = WTD_CACHE_ONLY_URL_RETRIEVAL;
  trust.dwUIContext = WTD_UICONTEXT_EXECUTE;

  result = WinVerifyTrust(NULL, (GUID *)&WINTRUST_ACTION_GENERIC_VERIFY_V2, &trust);
  out("WinVerifyTrust             = 0x"); hex32((DWORD)result); out(result == 0 ? " (PASS)\r\n" : " (FAIL)\r\n");
  data = WTHelperProvDataFromStateData(trust.hWVTStateData);
  out("ProvDataFromStateData      = "); out(data ? "PASS\r\n" : "FAIL\r\n");
  signer = data ? WTHelperGetProvSignerFromChain(data, 0, FALSE, 0) : NULL;
  out("GetProvSignerFromChain     = "); out(signer ? "PASS\r\n" : "FAIL\r\n");
  if (signer) dump_chain(signer->pChainContext);
  else out("RESULT: no signer chain available\r\n");

  trust.dwStateAction = WTD_STATEACTION_CLOSE;
  WinVerifyTrust(NULL, (GUID *)&WINTRUST_ACTION_GENERIC_VERIFY_V2, &trust);
  ExitProcess(result == 0 ? 0 : 1);
}
