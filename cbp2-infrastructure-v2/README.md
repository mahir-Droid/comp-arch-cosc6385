# Assignment 1: Branch Predictor Implementation

A Pentium M style hybrid branch direction predictor (bimodal table + tagged
global predictor) written for the `cbp2-infrastructure-v2` branch prediction
framework by Daniel A. Jiménez.

The predictor lives in `src/my_predictor.h` (class `pm_predictor`). Everything
else in the framework is unchanged. See `REPORT.md` for the design, the
verification against the handout's worked example, and the results.

## What is implemented

| Component        | Size / organisation                                           | Role                                   |
|------------------|---------------------------------------------------------------|----------------------------------------|
| Bimodal table    | 4096 two-bit counters, indexed by `IP[11:0]`                  | Fallback ("local") prediction          |
| Global predictor | 512 sets x 4 ways, each entry: valid bit, 6-bit tag, 2-bit counter, LRU | Prediction when the tag hits  |
| Global history   | 15-bit shift register of past outcomes (used instead of the Pentium M PIR) | Hashed with the IP          |

The global predictor is looked up with `hash = IP[14:0] xor GHR[14:0]`, set
index `hash[14:6]` and tag `hash[5:0]`. If the tag is found in one of the four
ways the global counter gives the prediction, otherwise the bimodal counter
does. Both tables are trained after every conditional branch; a global miss
replaces the least recently used way. Loop prediction and branch target
prediction are not part of this assignment and are not implemented.

## Building

```
cd src
make
```

This builds `predict` (uses `pm_predictor`) and `predict_extra_credit` (the
untouched extra-credit stub). The build products `src/predict` and
`src/predict_extra_credit` should not be committed.

## Running

A single trace:

```
./src/predict traces/164.gzip/gzip.trace.bz2
12.697 MPKI
```

All traces, with the average, using the framework's `run` script (it is a
`csh` script and uses `dc`; on Debian/Ubuntu/Pop!_OS install them with
`sudo apt install csh dc`):

```
chmod +x run
./run traces
```

The trace reader decompresses with `/usr/bin/bzip2`; if `bzip2` is somewhere
else on your system, change `BZCAT` in `src/trace.h`.

## Results

Mispredictions per 1000 instructions (MPKI), conditional branches only,
over the 20 supplied traces:

| Trace     | MPKI   | Trace     | MPKI   |
|-----------|--------|-----------|--------|
| gzip      | 12.697 | javac     | 3.001  |
| vpr       | 15.969 | mpegaudio | 2.932  |
| gcc       | 18.009 | mtrt      | 3.453  |
| mcf       | 18.269 | jack      | 4.239  |
| crafty    | 9.109  | eon       | 2.153  |
| parser    | 10.936 | perlbmk   | 5.095  |
| compress  | 8.019  | gap       | 4.309  |
| jess      | 2.005  | vortex    | 1.643  |
| raytrace  | 3.602  | bzip2     | 0.115  |
| db        | 4.801  | twolf     | 24.821 |

**Average: 7.758 MPKI** (the always-taken stub that ships with the framework
scores 86.312; the 32K-entry gshare sample scores 6.306 with more than twice
the storage). `REPORT.md` compares several variants of the design.

## Files

```
README.md              this file
REPORT.md              assignment report: design, verification, results, changes
run, run_extra         framework scripts that run predict / predict_extra_credit on a trace directory
src/my_predictor.h     gshare sample (unchanged), pm_predictor (the assignment), cpm_predictor stub (unchanged)
src/predict.cc         framework driver, instantiates pm_predictor (unchanged)
src/*.h, src/trace.cc  framework (unchanged)
traces/                the 20 benchmark traces
doc/index.html         original framework documentation
```


