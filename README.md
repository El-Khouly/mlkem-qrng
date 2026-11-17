# mlkem-qrng

Run **ML-KEM (FIPS 203)** with all of its randomness taken from an external bitstream, such as the output of a quantum or chaotic random number generator, and verify the result rigorously.

The notebook feeds the three 256-bit values ML-KEM consumes (`d`, `z`, `m`) from your stream into two independent implementations, [liboqs](https://github.com/open-quantum-safe/liboqs) and [kyber-py](https://github.com/GiacomoPope/kyber-py). Both are first validated against NIST's official ACVP test vectors; then every trial checks key agreement, byte-for-byte agreement between the two implementations, and implicit rejection.

## Contents

| Path | Description |
|---|---|
| `mlkem_qrng.ipynb` | Main notebook: install, configure, validate, run, summarise |
| `mlkem_backends.py` | The two ML-KEM backends with caller-supplied randomness (importable on its own) |
| `GUIDE.md` | Detailed explanation: how ML-KEM uses randomness, every check, every output column, troubleshooting |
| `requirements.txt` | Pinned dependency versions |
| `data/` | Put your bitstream here (ignored by git) |
| `results/reference/` | Published results from our run (see below) |

## Quick start

1. Install build tools for liboqs (needed once, see [GUIDE.md](GUIDE.md#installation)):
   - Linux: `sudo apt install build-essential cmake git`
   - Windows: Visual Studio Build Tools ("Desktop development with C++") and Git
2. Open `mlkem_qrng.ipynb` in Jupyter and run the install cell, then restart the kernel. The first `import oqs` compiles liboqs, which takes a few minutes.
3. Put your stream in `data/` (a text file of `0`/`1` characters, or raw bytes) and set `STREAM_PATH`, `STREAM_FMT` and `START_BIT` in the configuration cell.
4. Run all cells. Results go to `results/run/`.

With the default settings the stream must contain at least `START_BIT + 3 × 500 × 768` bits (1,152,000 bits after `START_BIT`).

## Reference results

`results/reference/` holds our run on a 1,572,864-bit QRNG stream (SHA-256 `b48330da…2c2b77`), using bits 146,072 to 1,298,072. Platform: Intel Core i7-1355U, Windows, liboqs 0.16.0 (mlkem-native portable C), kyber-py 1.2.0.

| ML-KEM | Trials | Key agreement | liboqs = kyber-py | Implicit rejection | KeyGen / Encaps / Decaps, median µs |
|---|---|---|---|---|---|
| 512  | 500 | 500/500 | 500/500 | 500/500 | 198.4 / 157.1 / 177.8 |
| 768  | 500 | 500/500 | 500/500 | 500/500 | 329.8 / 265.0 / 318.5 |
| 1024 | 500 | 500/500 | 500/500 | 500/500 | 506.6 / 429.0 / 507.4 |

Both implementations pass all NIST ACVP ML-KEM vectors for all three parameter sets. All 1,500 QRNG shared keys were later recomputed from the stream on a different platform (Linux, liboqs AVX2 build) and matched exactly. Timings are Python-level call latencies and include wrapper overhead. The `os.urandom` control run gave medians within 3.5% of these.

## Scope

This is a research and validation tool, not a production key-establishment library:

- FIPS 203 permits the seed-taking internal functions used here only for testing.
- A FIPS 203 deployment needs randomness from an approved random bit generator.
- kyber-py is not constant-time.
- Statistics computed on the shared keys say nothing about the quality of the input stream, because the keys are SHA-3 outputs. Assess the stream itself, e.g. with NIST SP 800-90B.

See [GUIDE.md](GUIDE.md) for details.
