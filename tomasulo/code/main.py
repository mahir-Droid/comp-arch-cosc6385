# Qing
# 21st May 2017
# modified: configuration is read from the input file, issue width,
#           branch target buffer, register and memory dump at the end

import sys
from copy import deepcopy
from collections import deque
from init import read_input, build_rs, build_btb, ld_sd_exe, ld_sd_mem, PC
from print_status import print_registers, print_memory
from issue import issue
from exe import exe
from mem import mem
from wb import wb
from commit import commit

'''initialize'''
# read the configuration and the instructions
if len(sys.argv) > 1:
    codefile = sys.argv[1]
else:
    codefile = 'code.in'
config, instructions = read_input(codefile)
issue_width = config['issue_width']
'''initialize regs, RAT, memory'''
# integer REG (R0 is always 0)
reg_int = []
for i in range(32):
    reg_int.extend([0])
for i in config['reg_int']:
    reg_int[i] = config['reg_int'][i]
reg_int[0] = 0
rat_int = deepcopy(reg_int)
# fp REG
reg_fp = []
for i in range(32):
    reg_fp.extend([0.0])
for i in config['reg_fp']:
    reg_fp[i] = config['reg_fp'][i]
rat_fp = deepcopy(reg_fp)
# memory (256 bytes, byte addressed)
memory = []
for i in range(256):
    memory.extend([0])
for address in config['memory']:
    memory[address] = config['memory'][address]
'''intialize reservation stations'''
rs_int_adder = build_rs(config['rs_int_adder'])
rs_fp_adder = build_rs(config['rs_fp_adder'])
rs_fp_multi = build_rs(config['rs_fp_multi'])
'''initilize function unit'''
# integer adder (not pipelined)
fu_int_adder = deque()
time_fu_int_adder = config['time_int_adder']
num_int_adder = config['num_int_adder']
# fp adder (pipelined)
fu_fp_adder = deque()
time_fu_fp_adder = config['time_fp_adder']
num_fp_adder = config['num_fp_adder']
# fp multiplier (pipelined)
fu_fp_multi = deque()
time_fu_fp_multi = config['time_fp_multi']
num_fp_multi = config['num_fp_multi']
'''initialize load/store queue'''
ld_sd_queue = deque()
size_ld_sd_queue = config['size_ld_sd_queue']
ld_sd_exe = ld_sd_exe()
ld_sd_exe.busy = 0
time_ld_sd_exe = config['time_ld_sd_exe']
ld_sd_mem = ld_sd_mem()
ld_sd_mem.busy = 0
time_ld_sd_mem = config['time_ld_sd_mem']
'''initialize ROB'''
ROB = deque()
size_ROB = config['size_ROB']
'''initialize CDB (results waiting to be broadcast)'''
results_buffer = deque()
'''initialize branch target buffer (8 entries, one bit predictor)'''
btb = build_btb(8)
"""issue first instruction"""
# instruction pointer
PC = PC()
PC.PC = 0
PC.valid = 1
cycle = 1

# print title
item = ''.ljust(30)
item += 'ISSUE'.ljust(15)
item += 'EXE'.ljust(15)
item += 'MEM'.ljust(15)
item += 'WB'.ljust(15)
item += 'COMMIT'.ljust(15)
print (item)

# main
while (len(ROB)>0) or (PC.PC<len(instructions)):

    '''ISSUE stage'''
    # fetch starts again after the recovery from a misprediction
    if (PC.valid==0) and (cycle>=PC.resume):
        PC.valid = 1
    if (PC.PC<len(instructions)) and (PC.valid==1):
        issue(cycle, PC, instructions, ROB, size_ROB,
                rs_int_adder,
                rs_fp_adder,
                rs_fp_multi,
                ld_sd_queue, size_ld_sd_queue,
                rat_int, rat_fp, btb, issue_width)

    '''EXE stage'''
    exe(fu_int_adder, time_fu_int_adder, num_int_adder,
        fu_fp_adder, time_fu_fp_adder, num_fp_adder,
        fu_fp_multi, time_fu_fp_multi, num_fp_multi, results_buffer,
        rs_int_adder, rs_fp_adder, rs_fp_multi,
        ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ld_sd_mem,
        cycle, ROB, PC, btb, rat_int, rat_fp, reg_int, reg_fp)

    '''MEM stage'''
    mem(ld_sd_queue, ld_sd_mem, time_ld_sd_mem, results_buffer,
        memory, ROB, cycle)

    '''CDB stage'''
    wb(rat_int, rat_fp,
        rs_int_adder, rs_fp_adder, rs_fp_multi,
        ld_sd_queue, ROB, cycle,
        results_buffer, issue_width)

    '''COMMIT stage'''
    commit(ROB, reg_int, reg_fp, cycle, instructions, issue_width,
            ld_sd_queue, ld_sd_mem, time_ld_sd_mem, results_buffer, memory)

    # cycle number
    cycle +=1

# a store may still be writing the memory after everything has committed
while ld_sd_mem.busy == 1:
    mem(ld_sd_queue, ld_sd_mem, time_ld_sd_mem, results_buffer,
        memory, ROB, cycle)
    cycle += 1

'''final register and memory contents'''
print_registers(reg_int, reg_fp)
print_memory(memory)
