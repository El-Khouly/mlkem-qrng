# Guide

1. [What this does](#what-this-does)
2. [How ML-KEM uses randomness](#how-ml-kem-uses-randomness)
3. [Installation](#installation)
4. [Preparing your stream](#preparing-your-stream)
5. [Configuration](#configuration)
6. [What the notebook checks](#what-the-notebook-checks)
7. [Output files](#output-files)
8. [The entropy requirement](#the-entropy-requirement)
9. [Reproducing the reference results](#reproducing-the-reference-results)
10. [Using the backends in your own code](#using-the-backends-in-your-own-code)
11. [Limitations](#limitations)
12. [Troubleshooting](#troubleshooting)

---

## What this does

The notebook takes a bitstream and uses it as the only source of randomness for ML-KEM, the post-quantum key-encapsulation mechanism standardized in NIST FIPS 203, in all three parameter sets (ML-KEM-512, -768 and -1024). It establishes three things:

- **Correctness:** the stream drives a standard ML-KEM correctly, as confirmed against NIST test vectors and an independent second implementation.
- **Reproducibility:** every result can be recomputed from the stream and the recorded bit offsets.
- **Performance parity:** the stream-seeded runs perform the same as runs seeded by the operating system.

It does **not** test whether the stream is random. That needs an entropy assessment of the stream itself (see [The entropy requirement](#the-entropy-requirement)).

## How ML-KEM uses randomness

ML-KEM has three algorithms:

| Algorithm | Input | Output |
|---|---|---|
| Key generation | random seeds `d`, `z` (32 bytes each) | encapsulation key `ek` (public), decapsulation key `dk` (secret) |
| Encapsulation | `ek`, random message `m` (32 bytes) | shared key `K` (32 bytes), ciphertext `c` |
| Decapsulation | `dk`, `c` | `K` |

`d`, `z` and `m` are **the only random inputs**. Everything else (the public matrix, the secret and error polynomials, the encryption randomness, `K`) is derived from them deterministically with SHA3-256, SHA3-512, SHAKE128 and SHAKE256. One complete key establishment therefore uses exactly 3 × 256 = 768 random bits, and supplying those bits from your stream makes it ML-KEM's only entropy source.

FIPS 203 exposes these seeds through the internal functions `ML-KEM.KeyGen_internal(d, z)` (Algorithm 16) and `ML-KEM.Encaps_internal(ek, m)` (Algorithm 17). The public versions draw `d`, `z`, `m` from the system random bit generator themselves. FIPS 203 allows the internal functions to be called directly for testing, which is how they are used here.

## Installation

**Python packages**: run the first notebook cell, or:

```
pip install -r requirements.txt
```

**liboqs**: `liboqs-python` contains only the Python wrapper. On the first `import oqs` it downloads and compiles the liboqs C library (into `~/_oqs`), which takes a few minutes and needs:

| OS | Requirements |
|---|---|
| Linux / WSL | `sudo apt install build-essential cmake git` |
| Windows | Visual Studio Build Tools with "Desktop development with C++" (provides MSVC, the Windows SDK and CMake), and Git for Windows |
| macOS | Xcode command-line tools and `brew install cmake` |

The PyPI package is **`liboqs-python`**. A different, unrelated package called `oqs` also exists and provides a module with the same name; installing it gives `AttributeError: module 'oqs' has no attribute 'oqs_version'`. See [Troubleshooting](#troubleshooting).

Use a standard **Python 3 kernel**. The notebook doesn't need SageMath.

## Preparing your stream

Put the file in `data/` and set `STREAM_PATH` and `STREAM_FMT`:

- **`ascii`**: a text file of `0` and `1` characters. All other characters (newlines, spaces, commas) are ignored.
- **`bin`**: raw bytes, read most-significant bit first.

Bits are turned into seed bytes **most-significant bit first**: stream bits `b0 b1 … b7` become the byte `b0b1…b7`.

**How many bits you need:** `START_BIT + len(PARAM_SETS) × TRIALS_PER_SET × 768`. With the defaults that is 146,072 + 1,152,000 = 1,298,072 bits. `START_BIT` lets you reserve the beginning of the stream for other uses; in our work, bits 0 to 146,071 were used to generate S-boxes. Set it to 0 if you don't need that.

Each parameter set gets its own consecutive segment, so **no stream bit is used twice**:

```
[START_BIT ............)[.............)[.............)
     ML-KEM-512            ML-KEM-768     ML-KEM-1024
  TRIALS_PER_SET × 768 bits each; trial i uses bits [start + 768 i, start + 768 (i+1)):
  the first 256 bits are d, the next 256 are z, the last 256 are m.
```

## Configuration

| Setting | Default | Meaning |
|---|---|---|
| `STREAM_PATH` | `data/RNG_Bits.txt` | Your bitstream |
| `STREAM_FMT` | `"ascii"` | `"ascii"` or `"bin"` |
| `START_BIT` | `146_072` | First bit used |
| `PARAM_SETS` | all three | Which ML-KEM parameter sets to run |
| `TRIALS_PER_SET` | `500` | Trials per parameter set (768 bits each) |
| `RUN_CONTROL` | `True` | Also run with `os.urandom` seeds, interleaved trial by trial |
| `H_MIN` | `None` | Min-entropy per bit of the stream (from SP 800-90B); `None` skips the entropy check |
| `BITS_ARE_CONDITIONED` | `False` | `True` if the stream is full-entropy conditioned output |
| `RESULTS_DIR` | `results/run` | Where outputs are written |

## What the notebook checks

**1. NIST ACVP validation (before the stream is touched).** Both implementations are run on NIST's official ML-KEM test vectors (usnistgov/ACVP-Server, pinned commit, verified by SHA-256). For each parameter set they must reproduce all 25 key-generation vectors, all 25 encapsulation vectors and all 10 decapsulation vectors. The decapsulation vectors include invalid ciphertexts. The notebook stops if any vector fails. This also confirms that liboqs's 64-byte key-generation seed is `d ‖ z`.

**2. Key agreement (`K_agree`).** Decapsulating `c` with `dk` returns the same `K` the encapsulation produced.

**3. Cross-implementation check (`xcheck_*`).** The same `d`, `z`, `m` are run through kyber-py, a pure-Python implementation that shares no code with liboqs. `ek`, `dk`, `c` and `K` must be byte-identical. Two unrelated codebases agreeing is strong evidence that the seeds are injected correctly.

**4. Implicit rejection (`implicit_reject_ok`).** One bit of the ciphertext is flipped (the least-significant bit of the first byte) and the result is decapsulated. ML-KEM must not return `K`. Instead it returns a pseudorandom rejection key `J(z ‖ c̃)`, which is deterministic, so both implementations must return the same value. This exercises the re-encryption check that makes ML-KEM secure against chosen-ciphertext attacks.

**5. Control run.** With `RUN_CONTROL = True`, every trial is repeated with seeds from `os.urandom`, alternating with the stream trials so both experience the same machine conditions. Correctness and timing should be indistinguishable, because once the seeds are fixed the computation is identical.

## Output files

All in `results/run/`.

**`mlkem_trials.csv`**: one row per trial.

| Column | Meaning |
|---|---|
| `param_set` | ML-KEM-512, -768 or -1024 |
| `source` | `qrng` (your stream) or `urandom` (control) |
| `trial` | 0 … TRIALS_PER_SET − 1 |
| `start_bit`, `end_bit` | Stream bits used, `[start_bit, end_bit)`; empty for control trials |
| `keygen_us`, `encaps_us`, `decaps_us` | liboqs call latency in microseconds, measured from Python |
| `K_agree` | 1 if decapsulation recovered `K` |
| `xcheck_ek`, `xcheck_dk`, `xcheck_c`, `xcheck_K` | 1 if liboqs and kyber-py produced identical values |
| `implicit_reject_ok` | 1 if the tampered ciphertext gave a key ≠ `K`, identical in both implementations |
| `len_ek`, `len_dk`, `len_c` | Sizes in bytes (fixed by FIPS 203: 800/1632/768, 1184/2400/1088, 1568/3168/1568) |
| `K_hex` | The shared key, for reproducibility checks |

**`mlkem_summary.csv`**: one row per parameter set and source: pass counts (`passed/total`) for every check, sizes, number of distinct keys, and median and 95th-percentile timings.

**`run_meta.json`**: the SHA-256 of the stream, the settings, and the software versions. If you resume a run with a different stream or different settings, the notebook stops instead of mixing results; move or delete `results/run/` to start fresh.

**Resuming:** each trial is written to disk as soon as it finishes. If the kernel dies, rerun the notebook and it continues from where it stopped.

## The entropy requirement

FIPS 203 (Sec. 3.3) requires `d`, `z`, `m` to come from an approved random bit generator with at least **128 / 192 / 256 bits** of security strength for ML-KEM-512 / 768 / 1024.

If you set `H_MIN` (the min-entropy per bit from an SP 800-90B assessment of your raw stream), the notebook reports whether a 256-bit seed carries enough min-entropy:

```
min-entropy per seed = 256 × H_MIN      (raw stream)
                     = 256              (BITS_ARE_CONDITIONED = True)
```

and compares it with 128 / 192 / 256.

Read this as a screening check, not a compliance result:
- The formula assumes the per-bit estimate holds over 256-bit blocks.
- SP 800-90B reports the **minimum** over all its estimators; use that value.
- For a raw stream, ML-KEM-1024 can only pass with `H_MIN = 1`. In practice the stream must go through a vetted conditioning component (SP 800-90B) first.
- Meeting the number doesn't make the setup a FIPS-approved random bit generator.

## Reproducing the reference results

`results/reference/` contains our run (`mlkem_trials.csv`, `mlkem_summary.csv`, `run_meta.json`). If you have the same stream (same SHA-256 as in `run_meta.json`) and keep the default settings, the last notebook cell compares your QRNG shared keys with the reference ones; they must all be identical. Control (`os.urandom`) keys and all timings will differ, as expected.

## Using the backends in your own code

```python
from mlkem_backends import LibOQS, KyberPy

kem = LibOQS("ML-KEM-768")            # or KyberPy("ML-KEM-768")
ek, dk = kem.keygen(d, z)             # d, z: 32 bytes each from your RNG
K, c   = kem.encaps(ek, m)            # m: 32 bytes from your RNG
assert kem.decaps(dk, c) == K
```

## Limitations

- **Testing interfaces only.** FIPS 203 allows the seed-taking internal functions to be called directly for testing. This code is for experiments and validation, not production key establishment.
- **kyber-py is a reference, not a secure implementation.** It isn't constant-time, and its author states it must not be used for cryptographic applications. Here it serves only as an independent cross-check.
- **Timings are Python-level.** They include wrapper and `ctypes` overhead and depend on which liboqs build was compiled (portable C or AVX2). Use them to compare runs within this harness, not as C benchmarks.
- **The shared keys don't measure stream quality.** `K` is the output of SHA3-512, so it looks random whatever the input. Statistics on `K` (bit balance, uniqueness) carry no information about your stream.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| `AttributeError: module 'oqs' has no attribute 'oqs_version'` | The unrelated PyPI package `oqs` is installed. Run `pip uninstall -y oqs liboqs-python`, then `pip install liboqs-python`, then restart the kernel. If it persists, check `oqs.__file__` for a local folder named `oqs` shadowing the package. |
| Build fails on first `import oqs` | Missing compiler, CMake or Git; see [Installation](#installation). |
| `stream too short` | Lower `TRIALS_PER_SET` or `START_BIT`, or supply a longer stream. |
| `results/run was produced with different [...]` | You changed the stream or settings after a previous run. Move or delete `results/run/`. |
| Running in a SageMath kernel | Use a Python 3 kernel. (The code avoids `^` for XOR, so it doesn't break under Sage's preparser, but Sage isn't needed.) |
| `ACVP validation failed` | Don't use the results. Check that `liboqs-python` and `kyber-py` match `requirements.txt`. |
