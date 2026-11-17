"""
ML-KEM (FIPS 203) with caller-supplied randomness.

Two independent backends expose the same three operations:

    keygen(d, z)  -> (ek, dk)    ML-KEM.KeyGen_internal, FIPS 203 Algorithm 16
    encaps(ek, m) -> (K, c)      ML-KEM.Encaps_internal, FIPS 203 Algorithm 17
    decaps(dk, c) -> K           ML-KEM.Decaps,          FIPS 203 Algorithm 21

d, z and m are 32-byte values. Everything else ML-KEM computes is derived
deterministically from them, so feeding these three values from an external
entropy source is enough to make that source the only randomness ML-KEM uses.

Backends
--------
LibOQS   liboqs (Open Quantum Safe), whose ML-KEM code comes from PQCP mlkem-native.
         Key generation from a seed uses liboqs-python's generate_keypair_seed().
         The wrapper has no seeded encapsulation, so OQS_KEM_encaps_derand is
         called directly from the liboqs shared library through ctypes.
KyberPy  kyber-py, a pure-Python FIPS 203 implementation, used as an independent
         reference. It is not constant-time and its author states it must not be
         used for real cryptographic applications.

FIPS 203 allows the *_internal functions to be called directly only for testing.
This module is meant for experiments and validation, not for production use.
"""
import ctypes as ct

import oqs
from kyber_py.ml_kem import ML_KEM_512, ML_KEM_768, ML_KEM_1024

PARAM_SETS = ["ML-KEM-512", "ML-KEM-768", "ML-KEM-1024"]

# A separate ctypes handle to the same liboqs library that liboqs-python loaded,
# so that setting argtypes/restype here cannot interfere with the wrapper.
_lib = ct.CDLL(oqs.oqs.native()._name)
_lib.OQS_KEM_new.restype = ct.c_void_p
_lib.OQS_KEM_new.argtypes = [ct.c_char_p]
_lib.OQS_KEM_free.argtypes = [ct.c_void_p]
_lib.OQS_KEM_encaps_derand.restype = ct.c_int
_lib.OQS_KEM_encaps_derand.argtypes = [ct.c_void_p, ct.c_char_p, ct.c_char_p,
                                       ct.c_char_p, ct.c_char_p]
_OQS_SUCCESS = 0


def _check32(name, value):
    if not isinstance(value, (bytes, bytearray)) or len(value) != 32:
        raise ValueError(f"{name} must be 32 bytes")


class LibOQS:
    """ML-KEM through liboqs."""

    name = "liboqs"

    def __init__(self, alg):
        if alg not in PARAM_SETS:
            raise ValueError(f"unknown parameter set {alg!r}; use one of {PARAM_SETS}")
        self.alg = alg
        with oqs.KeyEncapsulation(alg) as k:
            self.len_ct = k.details["length_ciphertext"]
            self.len_ss = k.details["length_shared_secret"]
        self._kem = _lib.OQS_KEM_new(alg.encode())
        if not self._kem:
            raise RuntimeError(f"{alg} is not enabled in this liboqs build")

    def keygen(self, d, z):
        _check32("d", d); _check32("z", z)
        with oqs.KeyEncapsulation(self.alg) as k:
            ek = k.generate_keypair_seed(bytes(d) + bytes(z))   # liboqs seed = d || z
            dk = k.export_secret_key()
        return bytes(ek), bytes(dk)

    def encaps(self, ek, m):
        _check32("m", m)
        c = ct.create_string_buffer(self.len_ct)
        K = ct.create_string_buffer(self.len_ss)
        rc = _lib.OQS_KEM_encaps_derand(self._kem, c, K, bytes(ek), bytes(m))
        if rc != _OQS_SUCCESS:
            raise RuntimeError("OQS_KEM_encaps_derand failed")
        return K.raw, c.raw

    def decaps(self, dk, c):
        with oqs.KeyEncapsulation(self.alg, secret_key=bytes(dk)) as k:
            return bytes(k.decap_secret(bytes(c)))

    def __del__(self):
        kem = getattr(self, "_kem", None)
        if kem:
            _lib.OQS_KEM_free(kem)


_KYBER_PY = {"ML-KEM-512": ML_KEM_512, "ML-KEM-768": ML_KEM_768, "ML-KEM-1024": ML_KEM_1024}


class KyberPy:
    """ML-KEM through kyber-py (independent pure-Python reference)."""

    name = "kyber-py"

    def __init__(self, alg):
        if alg not in _KYBER_PY:
            raise ValueError(f"unknown parameter set {alg!r}; use one of {PARAM_SETS}")
        self.alg, self._k = alg, _KYBER_PY[alg]

    def keygen(self, d, z):
        _check32("d", d); _check32("z", z)
        return self._k._keygen_internal(bytes(d), bytes(z))

    def encaps(self, ek, m):
        _check32("m", m)
        return self._k._encaps_internal(bytes(ek), bytes(m))

    def decaps(self, dk, c):
        return self._k.decaps(bytes(dk), bytes(c))
