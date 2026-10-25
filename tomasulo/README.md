Tomasulo Algorithm Simulation
* includes instructions of int_add, fp_add, fp_multi, load, store, branch (Bne / Beq);
* implements ROB, RAT, load-store-queue;
* implements out-of-order execution, in-order multiple issue (issue width 1-4), 
  in-order commit and memory disambiguation (store-to-load forwarding);
* implements a one-bit branch predictor with an 8-entry branch target buffer,
  speculative execution past branches and recovery after a misprediction
  (RAT recovery, reservation station / ROB clean up, fetch restarts at n+2).

How to run:
    cd code
    python main.py <input file>          (python 3, no extra packages)
    python main.py ../testcases/test1.txt

Without an argument main.py reads code/code.in.

Running every test case with issue width 1, 2, 3 and 4 (outputs go to results/):
    bash run_tests.sh

Input file format (see testcases/*.txt, the text is case insensitive and commas are optional):
                   # of rs    Cycles in EX    Cycles in Mem    # of FUs
    Integer adder   4          1                                1
    FP adder        3          4                                1
    FP multiplier   2          15                               1
    Load/store unit 5          1               5                1

    ROB entries = 64
    Issue width = 2               (optional, default 1)
    R1=12, R2=32, F20=3.0         (registers that are not listed are 0)
    Mem[4]=3.0, Mem[8]=2.0        (byte addresses, memory is 256 bytes)

    Ld F2 0(R1)
    Mult.d F4 F2 F20
    ...

Output: the instruction status table (ISSUE, EXE, MEM, WB, COMMIT cycles of every
committed instruction, in program order), the register values and the non-zero
memory values.

Files:
    code/init.py          data types, reading of the input file
    code/main.py          builds the hardware and runs the cycle loop
    code/issue.py         ISSUE stage (multiple issue, renaming, branch prediction)
    code/exe.py           EX stage (functional units, branch resolution, squashing)
    code/mem.py           MEM stage (load/store queue, forwarding, memory access)
    code/wb.py            WB stage (CDB broadcast)
    code/commit.py        COMMIT stage (in-order commit, stores write memory)
    code/print_status.py  printing helpers
    testcases/            test inputs
    results/              simulator output for every test case and issue width
    REPORT.md             report (code changes and results)
