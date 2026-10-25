# Qing
# 24th May 2017
# modified: instructions are never executed twice in a cycle, oldest ready
#           instruction is dispatched first, several functional units,
#           branch resolution with the BTB and squashing after a misprediction

'''
1. advance the instructions already in the functional units by one cycle
    -- for ALU instructions that finish, write results into fu_results, remove that fu entry
    -- for LD/SD, write address result back to ld_sd_queue
    -- for branches, compare the outcome with the prediction and squash on a misprediction
2. fetch ready instructions (issued in an earlier cycle) into the functional units
    -- remove ALU instructions from rs
    -- don't remove ld/sd instructions
'''
from init import fu_entry, fu_result

# function: find ROB entry by tag, -1 if it is not in the ROB
def find_ROB_entry(ROB, tag):
    for index in range(len(ROB)):
        if ROB[index].ROB_tag == tag:
            return index
    return -1

# function: check rs and return the oldest valid instruction index
# (the instruction has to be issued in an earlier cycle)
def check_valid_ins_in_rs(rs, ROB, cycle):
    index = -1
    oldest = len(ROB)
    for i in range(len(rs)):
        if (rs[i].busy==1) and (rs[i].valid_1st==1) and (rs[i].valid_2nd==1):
            rob_index = find_ROB_entry(ROB, rs[i].dest_tag)
            if (ROB[rob_index].issue[0] < cycle) and (rob_index < oldest):
                oldest = rob_index
                index = i
    return index

# function: check ld_sd_queue and return the oldest instruction that needs its address
def check_valid_ins_in_ldsd(ldsd, ROB, cycle):
    index = -1
    for i in range(len(ldsd)):
        if (ldsd[i].valid==1) and (ldsd[i].ready==0):
            rob_index = find_ROB_entry(ROB, ldsd[i].dest_tag)
            if ROB[rob_index].issue[0] < cycle:
                index = i
                break
    return index

# function: add entry into fu
def add_entry_into_fu(fu, ins_in_rs):
    fu.append(fu_entry())
    fu[-1].cycle = 1
    fu[-1].op = ins_in_rs.op
    fu[-1].value1 = ins_in_rs.value_1st
    fu[-1].value2 = ins_in_rs.value_2nd
    fu[-1].dest_tag = ins_in_rs.dest_tag

# function: resolve a branch at the end of its execution
def resolve_branch(entry, rob_entry, cycle, PC, btb):
    if entry.op == 'Bne':
        taken = (entry.value1 != entry.value2)
    else: # Beq
        taken = (entry.value1 == entry.value2)
    # offset is a byte offset relative to PC+4, PC counts words here
    target = rob_entry.PC + 1 + int(rob_entry.dest_tag / 4)
    if taken:
        next_pc = target
    else:
        next_pc = rob_entry.PC + 1
    # update the BTB entry / one bit predictor
    slot = btb[rob_entry.PC % len(btb)]
    slot.pc = rob_entry.PC
    slot.target = target
    if taken:
        slot.taken = 1
    else:
        slot.taken = 0
    # misprediction: fetch stops, recovery takes one cycle,
    # the correct instruction is fetched at cycle+2
    if next_pc != rob_entry.predict:
        PC.PC = next_pc
        PC.valid = 0
        PC.resume = cycle + 2
        PC.squash = rob_entry.ROB_tag

# function: the oldest instructions in the fu finish when they have spent time_fu cycles
def fu_finish(fu, fu_results, ROB, time_fu, cycle, PC, btb):
    while (len(fu) > 0) and (fu[0].cycle >= time_fu):
        entry = fu.popleft()
        index = find_ROB_entry(ROB, entry.dest_tag)
        ROB[index].exe.append(cycle)
        if (entry.op=='Bne') or (entry.op=='Beq'):
            # a branch behind an already mispredicted branch is squashed anyway
            if PC.squash == '':
                resolve_branch(entry, ROB[index], cycle, PC, btb)
        else:
            # calculation result
            fu_results.append(fu_result())
            fu_results[-1].dest_tag = entry.dest_tag
            fu_results[-1].cycle = cycle
            if (entry.op=='Add')|(entry.op=='Add.d')|(entry.op=='Addi'):
                fu_results[-1].value = entry.value1 + entry.value2
            elif (entry.op=='Sub')|(entry.op=='Sub.d'):
                fu_results[-1].value = entry.value1 - entry.value2
            elif (entry.op=='Mult.d'):
                fu_results[-1].value = entry.value1 * entry.value2

# function: functional units execution (one more cycle for every instruction in the unit)
def fu_exe(fu, fu_results, ROB, time_fu, cycle, PC, btb):
    for element in fu:
        element.cycle += 1
    fu_finish(fu, fu_results, ROB, time_fu, cycle, PC, btb)

# function: fetch ready instructions from a rs into its fu
# pipelined units accept num_fu instructions per cycle,
# the (unpipelined) integer adder holds at most num_fu instructions
# (in_use = instructions that were in the unit at the start of this cycle)
def fu_dispatch(rs, fu, fu_results, ROB, time_fu, num_fu, pipelined, in_use, cycle, PC, btb):
    for n in range(num_fu):
        if (pipelined == False) and (in_use + n >= num_fu):
            break
        index = check_valid_ins_in_rs(rs, ROB, cycle)
        if index < 0:
            break
        add_entry_into_fu(fu, rs[index])
        # write starting cycle
        rob_index = find_ROB_entry(ROB, rs[index].dest_tag)
        ROB[rob_index].exe.append(cycle)
        # remove ins from rs
        rs[index].busy = 0
        # one cycle units finish in the same cycle
        fu_finish(fu, fu_results, ROB, time_fu, cycle, PC, btb)

# function: ld_sd address calculation finishes, write address back to ld_sd_queue
def ld_sd_finish(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle):
    if (ld_sd_exe.busy == 1) and (ld_sd_exe.cycle >= time_ld_sd_exe):
        address = int(ld_sd_exe.value1 + ld_sd_exe.value2)
        for element in ld_sd_queue:
            if element.ld_sd_tag == ld_sd_exe.dest_tag:
                element.address = address
                element.ready = 1
                # write down finish cycle
                index = find_ROB_entry(ROB, element.dest_tag)
                ROB[index].exe.append(cycle)
                break
        ld_sd_exe.busy = 0
        ld_sd_exe.end = cycle

# function: ld_sd_execution (one more cycle in the address adder)
def ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle):
    if ld_sd_exe.busy == 1:
        ld_sd_exe.cycle += 1
        ld_sd_finish(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle)

# function: recover the RAT after a misprediction
# start from the architectural registers and redo the renaming of the
# instructions that are still in the ROB
def recover_rat(ROB, rat_int, rat_fp, reg_int, reg_fp):
    for i in range(32):
        rat_int[i] = reg_int[i]
        rat_fp[i] = reg_fp[i]
    for entry in ROB:
        if type(entry.dest_tag) != str:
            continue
        if entry.dest_tag[0] == 'F':
            rat = rat_fp
        elif (entry.dest_tag[0] == 'R') and (entry.dest_tag != 'R0'):
            rat = rat_int
        else:
            continue
        if len(entry.cdb) == 0:
            rat[int(entry.dest_tag[1:])] = entry.ROB_tag
        else:
            rat[int(entry.dest_tag[1:])] = entry.value

# function: squash all instructions behind a mispredicted branch
def squash(branch_tag, ROB, rs_int_adder, rs_fp_adder, rs_fp_multi,
        fu_int_adder, fu_fp_adder, fu_fp_multi,
        ld_sd_exe, ld_sd_queue, ld_sd_mem, results_buffer,
        rat_int, rat_fp, reg_int, reg_fp):
    # 1. clear the ROB entries that surpass the branch
    flushed = []
    while ROB[-1].ROB_tag != branch_tag:
        flushed.append(ROB.pop().ROB_tag)
    # 2. clear the reservation stations of the wrong instructions
    for rs in [rs_int_adder, rs_fp_adder, rs_fp_multi]:
        for element in rs:
            if (element.busy == 1) and (element.dest_tag in flushed):
                element.busy = 0
    # wrong instructions still in the functional units or waiting for the CDB
    for fu in [fu_int_adder, fu_fp_adder, fu_fp_multi, results_buffer]:
        remove_list = []
        for element in fu:
            if element.dest_tag in flushed:
                remove_list.append(element)
        for element in remove_list:
            fu.remove(element)
    # wrong loads and stores
    remove_list = []
    for element in ld_sd_queue:
        if element.dest_tag in flushed:
            remove_list.append(element)
            if (ld_sd_exe.busy == 1) and (ld_sd_exe.dest_tag == element.ld_sd_tag):
                ld_sd_exe.busy = 0
    for element in remove_list:
        ld_sd_queue.remove(element)
    if (ld_sd_mem.busy == 1) and (ld_sd_mem.dest_tag in flushed):
        ld_sd_mem.busy = 0
    # 3. recover the RAT
    recover_rat(ROB, rat_int, rat_fp, reg_int, reg_fp)

# function: execution
def exe(fu_int_adder, time_fu_int_adder, num_int_adder,
        fu_fp_adder, time_fu_fp_adder, num_fp_adder,
        fu_fp_multi, time_fu_fp_multi, num_fp_multi, results_buffer,
        rs_int_adder, rs_fp_adder, rs_fp_multi,
        ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ld_sd_mem,
        cycle, ROB, PC, btb, rat_int, rat_fp, reg_int, reg_fp):
    '''execution in fu and ld_sd address calculation'''
    # the integer adder is not pipelined: remember how many instructions it holds
    int_adder_in_use = len(fu_int_adder)
    ld_sd_execution(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle)
    # functional units
    fu_exe(fu_int_adder, results_buffer, ROB, time_fu_int_adder, cycle, PC, btb)
    fu_exe(fu_fp_adder, results_buffer, ROB, time_fu_fp_adder, cycle, PC, btb)
    fu_exe(fu_fp_multi, results_buffer, ROB, time_fu_fp_multi, cycle, PC, btb)
    '''fetch instructions from rs and ld_sd_queue'''
    # from ld_sd_queue into the address adder
    index = check_valid_ins_in_ldsd(ld_sd_queue, ROB, cycle)
    if (index>=0) and (ld_sd_exe.busy==0) and (ld_sd_exe.end<cycle):
        ld_sd_exe.busy = 1
        ld_sd_exe.cycle = 1
        ld_sd_exe.value1 = ld_sd_queue[index].reg_value
        ld_sd_exe.value2 = ld_sd_queue[index].immediate
        ld_sd_exe.dest_tag = ld_sd_queue[index].ld_sd_tag
        # write down starting cycle
        rob_index = find_ROB_entry(ROB, ld_sd_queue[index].dest_tag)
        ROB[rob_index].exe.append(cycle)
        ld_sd_finish(ld_sd_exe, time_ld_sd_exe, ld_sd_queue, ROB, cycle)
    # from rs
    fu_dispatch(rs_int_adder, fu_int_adder, results_buffer, ROB, time_fu_int_adder,
            num_int_adder, False, int_adder_in_use, cycle, PC, btb)
    fu_dispatch(rs_fp_adder, fu_fp_adder, results_buffer, ROB, time_fu_fp_adder,
            num_fp_adder, True, 0, cycle, PC, btb)
    fu_dispatch(rs_fp_multi, fu_fp_multi, results_buffer, ROB, time_fu_fp_multi,
            num_fp_multi, True, 0, cycle, PC, btb)
    '''squash the wrong path after a misprediction'''
    if PC.squash != '':
        squash(PC.squash, ROB, rs_int_adder, rs_fp_adder, rs_fp_multi,
                fu_int_adder, fu_fp_adder, fu_fp_multi,
                ld_sd_exe, ld_sd_queue, ld_sd_mem, results_buffer,
                rat_int, rat_fp, reg_int, reg_fp)
        PC.squash = ''
