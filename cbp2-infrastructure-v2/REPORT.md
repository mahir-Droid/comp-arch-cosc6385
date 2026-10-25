# Assignment 1: Branch Predictor Implementation — Report


## 1. Summary

I implemented the branch *direction* prediction part of the Pentium M branch
prediction unit inside the `cbp2-infrastructure-v2` framework: a 4096-entry
bimodal table plus a 512-set, 4-way, tagged global predictor that is hashed
with a global history register. The two are combined the way the Pentium M
does it: when the global predictor has an entry for the branch, its answer is
used; otherwise the bimodal table's answer is used. The loop predictor, the
path information register (PIR) and all branch target prediction were left
out, as the handout allows.

All of the work is in one file, `src/my_predictor.h`, in the `pm_predictor`
class that `predict.cc` already instantiates. Nothing else in the framework was
changed. Before running the traces I checked the implementation against the
22-branch worked example in Appendix B of the handout and it reproduces every
row of the handout's tables. On the 20 supplied traces the predictor averages
**7.758 MPKI**, down from 86.312 for the always-taken stub the framework ships
with.

## 2. What the Pentium M does and what was implemented

The handout's diagram (from Uzelac and Milenković, ISPASS 2009) shows the
outcome prediction path of the Pentium M. The table below maps each block that
the assignment asks for onto the code.

| Block in the diagram | Parameters in the diagram | In `pm_predictor` |
|---|---|---|
| Bimodal table | 4096 two-bit counters, `Index = IP[11:0]` | `bimodal[4096]`, `BIMODAL_BITS = 12` |
| Global predictor | 512 sets x 4 ways, each with a 6-bit tag and a 2-bit counter (2bC); `Index = HASH[14:6]`, `Tag = HASH[5:0]` | `global[512][4]` of `global_entry {valid, tag, counter, lru}`; `HASH_BITS = 15`, `TAG_BITS = 6`, `WAYS = 4` |
| Hash of IP and PIR | 15 bits of IP xor the 15-bit PIR | `hash = (IP ^ history) & 0x7fff`, where `history` is a 15-bit global history register |
| Final outcome mux | global prediction if "global predictor hit", else bimodal prediction | the `if (u.global_way >= 0)` in `predict()` |
| Loop branch predictor buffer | — | not required, not implemented |
| BTB / iBTB (targets) | — | not required, not implemented |

### 2.1 Global history register instead of the PIR

The real chip hashes the instruction pointer with a path information register
built from the targets of recent taken branches. The handout says the PIR and
its hash are not required, and Appendix B replaces them with a plain global
history register (GHR) of recent branch outcomes, exactly as in the gshare
sample that comes with the framework. I did the same: after every conditional
branch the outcome is shifted into `history` (1 for taken, 0 for not taken) and
the register is kept 15 bits wide so that it covers the whole hash. The newest
outcome lands in bit 0, so the six most recent outcomes end up in the tag and
the nine older ones in the set index. This is the same bit arrangement as the
4-bit example in the handout, just wider.

### 2.2 Set-associative global predictor with LRU replacement

The global predictor behaves like a small cache. A lookup computes the hash,
takes `hash[14:6]` as the set number and `hash[5:0]` as the tag, and compares
the tag with the four ways of that set. A matching valid way is a "global hit".
On a hit the way's two-bit counter is trained and the way becomes the most
recently used one. On a miss the least recently used way of the set is handed
over to the new tag (valid bit set, tag written) and then trained like a hit.

Each entry carries a small `lru` rank: 0 means most recently used and
`WAYS-1` means least recently used; the ranks inside a set are always a
permutation of 0..3. With two ways this rank is exactly the single LRU bit that
the handout's worked example draws (1 = replace next), which made it easy to
check. The handout allows a 2-way global predictor instead of the 4-way one;
I kept the real 4-way organisation, and `WAYS` is a single constant, so the
2-way variant is a one-character change (results for it are in Section 5).

I did not reuse the L1 cache simulator code that the handout points to
(github.com/NishadSaraf/L1-Cache-Simulator). It is a full data-cache model with
string tags, dirty bits and a write-back policy, which is more machinery than a
tag-plus-counter table needs; a small `find_way` / `lru_way` / `touch` trio in
`pm_predictor` is shorter and easier to read.

### 2.3 Allocation policy — following the worked example

When a new tag is installed in a way, the worked example in the handout does
not reset the two-bit counter of that entry: it keeps whatever value the
previous occupant left behind and trains it with the current outcome (for
example in step 2 the counter goes 1 -> 2, in step 3 it goes 3 -> 2). The
submitted code does exactly this so that it matches the handout step for step.
Section 5.3 measures the alternative of initialising the counter on allocation,
which turns out to be noticeably better; switching to it is a one-line change
that is shown there.

### 2.4 Non-conditional branches

The driver calls `predict()` and `update()` for every branch but only scores
conditional ones. For unconditional jumps, calls and returns the predictor
answers "taken" and touches none of its tables, and the GHR is only updated by
conditional branches. This is the same convention the gshare sample uses, and
it keeps the history identical to the handout's example, which only contains
conditional branches.

## 3. Code walkthrough

`pm_update` is the record handed from `predict()` to `update()`. It remembers
whether the branch was conditional, which bimodal counter was used, which global
set and tag were looked up, and which way hit (`-1` on a miss), so that the
update does not have to recompute anything.

`pm_predictor::predict()`

1. If the branch is not conditional, predict taken and return.
2. `bimodal_index = IP[11:0]`; the bimodal prediction is "taken" if that
   counter is 2 or 3.
3. `hash = (IP ^ history) & 0x7fff`; `global_index = hash >> 6`;
   `global_tag = hash & 0x3f`; `find_way()` searches the set for the tag.
4. Final prediction: the global counter if there was a hit, else the bimodal
   prediction. The target prediction is left at 0.

`pm_predictor::update()`

1. Train the bimodal counter (saturating up on taken, down on not taken).
2. Global predictor: if the lookup missed, pick `lru_way()` and give it the new
   tag; then train the counter of that way and `touch()` it (it becomes most
   recently used, the others in the set age by one).
3. Shift the outcome into the 15-bit history register.

The helper `train()` is the usual two-bit saturating counter; `find_way()`,
`lru_way()` and `touch()` are the three small loops that make the set
associative table work.

## 4. Verification against the handout's worked example

Appendix B of the handout walks a three-branch program through a shrunken
version of the same design: 8-bit addresses, 16 bimodal counters indexed by
address bits [5:2], a 2-way global predictor with 4 sets, 2-bit tags and a
4-bit GHR, with the counters started at the illustrative values 0,1,2,3 instead
of zeros. To make sure my logic is the one the handout describes, I compiled a
copy of `pm_predictor` with its size constants shrunk to those values
(`BIMODAL_BITS = 4`, `HASH_BITS = 4`, `TAG_BITS = 2`, `WAYS = 2`), preset the
counters the same way, and replayed the 22 branches of the "Branch History"
table, feeding the addresses shifted right by two so that bits [5:2] become the
index.

For every step the harness compared the GHR, the 4-bit hash, the row and tag,
the local prediction, the global hit/miss and prediction, and the final
prediction with the "Hybrid Predictor Results" table, and after steps 11 and 21
it compared the complete valid/tag/counter/LRU contents of both ways of all four
sets with the "Global Predictor" tables. Everything matched:

```
step br  out  GHR   hash  row tag  local  global     final
  1  b1  T    0000  0001  0   01   NT     No hit     NT
  2  b3  T    0001  0005  1   01   NT     No hit     NT
  3  b1  NT   0003  0002  0   02   T      No hit     T
  4  b2  NT   0006  000d  3   01   T      No hit     T
  5  b3  T    000c  0008  2   00   NT     No hit     NT
  6  b1  T    0009  0008  2   00   NT     Hit, T     T
  7  b3  T    0003  0007  1   03   T      No hit     T
  8  b1  NT   0007  0006  1   02   T      No hit     T
  9  b2  NT   000e  0005  1   01   T      No hit     T
 10  b3  T    000c  0008  2   00   T      Hit, T     T
 11  b1  NT   0009  0008  2   00   NT     Hit, T     T
 12  b2  T    0002  0009  2   01   NT     No hit     NT
 13  b1  NT   0005  0004  1   00   NT     No hit     NT
 14  b2  NT   000a  0001  0   01   T      Hit, NT    NT
 15  b3  T    0004  0000  0   00   T      No hit     T
 16  b1  T    0009  0008  2   00   NT     Hit, T     T
 17  b3  T    0003  0007  1   03   T      No hit     T
 18  b1  NT   0007  0006  1   02   NT     No hit     NT
 19  b2  NT   000e  0005  1   01   NT     No hit     NT
 20  b3  T    000c  0008  2   00   T      Hit, T     T
 21  b1  T    0009  0008  2   00   NT     Hit, T     T
 22  b3  T    0003  0007  1   03   T      No hit     T

All 22 steps and both table snapshots match the handout.
```

(Row and tag are printed in decimal; the handout prints them in binary, e.g.
row 3 / tag 01 in step 4 is `hash = 1101`.)

## 5. Results

### 5.1 Submitted predictor

Built with the unmodified `Makefile` (`g++ -g -O3 -Wall`) and run with the
framework's `run traces` script. The number is mispredictions per 1000
instructions for conditional branches; each trace is 100 million instructions.

```
traces/164.gzip/gzip.trace.bz2              12.697
traces/175.vpr/vpr.trace.bz2                15.969
traces/176.gcc/gcc.trace.bz2                18.009
traces/181.mcf/mcf.trace.bz2                18.269
traces/186.crafty/crafty.trace.bz2           9.109
traces/197.parser/parser.trace.bz2          10.936
traces/201.compress/compress.trace.bz2       8.019
traces/202.jess/jess.trace.bz2               2.005
traces/205.raytrace/raytrace.trace.bz2       3.602
traces/209.db/db.trace.bz2                   4.801
traces/213.javac/javac.trace.bz2             3.001
traces/222.mpegaudio/mpegaudio.trace.bz2     2.932
traces/227.mtrt/mtrt.trace.bz2               3.453
traces/228.jack/jack.trace.bz2               4.239
traces/252.eon/eon.trace.bz2                 2.153
traces/253.perlbmk/perlbmk.trace.bz2         5.095
traces/254.gap/gap.trace.bz2                 4.309
traces/255.vortex/vortex.trace.bz2           1.643
traces/256.bzip2/bzip2.trace.bz2             0.115
traces/300.twolf/twolf.trace.bz2            24.821
average MPKI: 7.758
```

(The `run` script truncates the average to three decimals with `dc`; the exact
mean of the twenty numbers is 7.7589.)

Storage used by the predictor, counting only what the hardware would keep:

| Structure | Bits |
|---|---|
| Bimodal table: 4096 x 2 | 8192 (1 KB) |
| Global predictor: 2048 entries x (1 valid + 6 tag + 2 counter) | 18432 (2.25 KB) |
| LRU state: 2 bits per way, 2048 ways | 4096 (0.5 KB; a hardware PLRU would need 3 bits per set) |
| Global history register | 15 |
| **Total** | **~3.75 KB** |

### 5.2 Comparison with other configurations

To understand where the accuracy comes from I also ran a few variants. All of
them were built from scratch copies of `src/` with one line changed, so the
repository only contains the submitted design.

| Trace | Hybrid (4-way, submitted) | Hybrid 2-way | Bimodal only | Hybrid, no history in hash | Hybrid, counter reset on allocate | gshare sample (32K) | Always taken (stub) |
|---|---|---|---|---|---|---|---|
| gzip | 12.697 | 12.954 | 15.032 | 15.049 | 12.461 | 12.473 | 70.025 |
| vpr | 15.969 | 16.824 | 14.673 | 14.689 | 14.071 | 13.415 | 85.312 |
| gcc | 18.009 | 19.790 | 19.319 | 19.539 | 13.302 | 11.254 | 86.071 |
| mcf | 18.269 | 20.079 | 33.247 | 32.968 | 16.490 | 15.837 | 102.497 |
| crafty | 9.109 | 10.819 | 13.075 | 12.497 | 6.898 | 5.837 | 48.651 |
| parser | 10.936 | 12.617 | 15.420 | 15.746 | 9.245 | 10.008 | 78.421 |
| compress | 8.019 | 8.610 | 9.336 | 9.137 | 7.841 | 7.831 | 76.983 |
| jess | 2.005 | 2.559 | 8.749 | 8.649 | 1.463 | 1.562 | 92.343 |
| raytrace | 3.602 | 4.058 | 3.718 | 3.520 | 2.945 | 2.756 | 109.506 |
| db | 4.801 | 5.244 | 6.318 | 6.041 | 4.262 | 3.909 | 91.451 |
| javac | 3.001 | 3.293 | 3.174 | 3.024 | 2.400 | 2.267 | 109.644 |
| mpegaudio | 2.932 | 3.253 | 3.141 | 2.984 | 2.354 | 2.188 | 110.339 |
| mtrt | 3.453 | 3.911 | 3.699 | 3.441 | 2.968 | 2.657 | 112.022 |
| jack | 4.239 | 5.684 | 7.908 | 6.947 | 3.077 | 3.033 | 77.958 |
| eon | 2.153 | 3.836 | 9.408 | 9.328 | 1.839 | 1.807 | 24.226 |
| perlbmk | 5.095 | 7.310 | 5.829 | 6.141 | 3.248 | 2.554 | 66.833 |
| gap | 4.309 | 5.758 | 9.624 | 10.731 | 3.814 | 3.926 | 75.950 |
| vortex | 1.643 | 2.235 | 1.923 | 1.772 | 1.090 | 1.222 | 70.524 |
| bzip2 | 0.115 | 0.147 | 0.113 | 0.117 | 0.074 | 0.094 | 178.257 |
| twolf | 24.821 | 24.242 | 21.946 | 22.402 | 22.239 | 21.489 | 59.221 |
| **Average** | **7.758** | 8.661 | 10.283 | 10.236 | 6.604 | 6.306 | 86.312 |

What the columns are:

- *Hybrid 2-way*: `WAYS = 2`, the smaller organisation the handout permits.
- *Bimodal only*: the global predictor's answer is ignored (only the 4096
  bimodal counters predict).
- *No history in hash*: `hash = IP[14:0]` without the xor with the GHR, i.e. the
  global predictor becomes a tagged table indexed by address alone.
- *Counter reset on allocate*: on a global miss the new entry's counter starts
  at 1 (if not taken) or 2 (if taken) instead of inheriting the old value; see
  5.3.
- *gshare sample*: the unmodified `gshare_predictor` from `my_predictor.h`
  (32768 two-bit counters, 15-bit history, 8 KB of counters).
- *Always taken*: the empty `pm_predictor` stub as distributed.

### 5.3 Discussion

**The global predictor is doing real work.** Adding it to the bimodal table
cuts the average from 10.283 to 7.758 MPKI, about 25 % fewer mispredictions
with 2.75 KB of extra state. The gains are largest on the traces whose branches
depend on what happened just before them: mcf (33.2 -> 18.3), jess (8.7 ->
2.0), eon (9.4 -> 2.2), gap (9.6 -> 4.3) and jack (7.9 -> 4.2).

**The history is what makes it work.** Taking the GHR out of the hash gives
10.236 MPKI, essentially the bimodal-only number. Without history the global
predictor is just another address-indexed table, and a second counter per
branch adds nothing. The xor with the outcome history is what lets one branch
have several entries, one per recent pattern.

**Four ways beat two.** The 2-way variant is 8.661 MPKI, about 12 % more
mispredictions than the 4-way one. With 512 sets and only two ways, the
different history patterns of the hot branches keep evicting each other; a lot
of lookups miss, fall back to the bimodal table, and then allocate again.

**Where the hybrid loses.** On vpr (15.97 vs 14.67) and twolf (24.82 vs 21.95),
and by a hair on bzip2, the bimodal table alone is better than the hybrid. The
Pentium M style selection rule trusts the global predictor whenever its tag
matches; there is no confidence check. A freshly allocated entry hits on its
very next use after being trained only once, and under the handout's
allocation policy its counter started from whatever the previous occupant left
behind, so the "hit" can be backed by a counter that mostly reflects a
different branch. On traces with many hard-to-predict branches (twolf is the
worst trace in every column) these half-trained hits override a bimodal counter
that had settled on the right answer.

**Allocation policy.** This is also why the "counter reset on allocate" column
is so much better: 6.604 MPKI, a 15 % improvement, and it never loses to the
bimodal table except on twolf. Starting a new entry in the weak state that
agrees with the branch's current outcome removes the stale bias. (Starting it in
the strong state, 0 or 3, gives 6.589 and is just as good.) I kept the
handout's behaviour in the submitted code because it is what the worked example
specifies and it lets the code be checked against the handout line by line. To
try the better policy, add one line in `update()` right after the new tag is
written:

```cpp
global[pu->global_index][way].tag = pu->global_tag;
global[pu->global_index][way].counter = taken ? 1 : 2;   // start fresh: train() makes it 2 or 1
```

**Against the gshare sample.** The 32K-entry gshare scores 6.306 MPKI. It has
more than twice the storage of the hybrid (8 KB of counters against 3.75 KB),
and with the allocation change above the Pentium M style hybrid gets within
0.3 MPKI of it, which is a reasonable place for a predictor that was designed
for a low-power notebook core.

## 6. Changes made to the repository

The repository is the `cbp2-infrastructure-v2` tree as distributed. Three
files are different from the distribution; everything else is untouched.

| File | Status | What changed |
|---|---|---|
| `src/my_predictor.h` | modified | The `pm_update` and `pm_predictor` stubs (original lines 52-85) were replaced by the implementation described above (now lines 52-219). The `gshare_predictor` sample above them and the `cpm_update` / `cpm_predictor` extra-credit stubs below them are byte for byte the same as in the distribution. No new `#include`s and no new `#define`s were added; the sizes are `static const int` members of the class so they cannot clash with the gshare sample's `HISTORY_LENGTH` / `TABLE_BITS` macros. |
| `README.md` | new | Build and run instructions, summary of the design and results, file map. |
| `REPORT.md` | new | This report. |

Files deliberately left as they were: `src/predict.cc` (already instantiates
`pm_predictor`), `src/predict_extra_credit.cc`, `src/predictor.h`,
`src/branch.h`, `src/trace.h`, `src/trace.cc`, `src/Makefile`,
`src/compress/*`, `run`, `run_extra`, `README`, `doc/index.html` and the
`traces/` directory. The extra-credit target `predict_extra_credit` still
builds and still uses the empty `cpm_predictor` stub, since target prediction is
not part of this assignment. The compiled binaries `src/predict` and
`src/predict_extra_credit` are build products and are not part of the
submission.

The verification harness of Section 4 and the modified copies used for the
comparison runs of Section 5.2 were kept outside the repository on purpose, so
that the submitted tree contains exactly one predictor.

## 7. How to reproduce

```
cd src && make && cd ..        # builds src/predict and src/predict_extra_credit
./src/predict traces/164.gzip/gzip.trace.bz2     # one trace  ->  12.697 MPKI
chmod +x run && ./run traces                     # all traces, prints the average
```

`run` is a `csh` script that also uses `dc`; on Debian, Ubuntu or Pop!_OS they
are installed with `sudo apt install csh dc`. The whole run takes about ten
seconds. The code compiles without warnings under the Makefile's `-Wall`, and
also under `-std=c++98 -Wextra -pedantic` apart from the unused `target`
parameter that the `branch_predictor::update` interface requires (the gshare
sample has the same one).


