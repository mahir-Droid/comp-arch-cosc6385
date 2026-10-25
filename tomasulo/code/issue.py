# Qing
# 21st May 2017
# modified: issue width, branch prediction with the BTB, Beq, R0 is never renamed

"""
1. put 1 instruction in ROB
2. put this instruction in RS/ld_sd_queue
3. update RAT
(repeated up to issue_width times per cycle, in program order)
"""
from init import ld_sd_entry, ROB_entry

# function: find a tag for ld_sd_entry
def find_tag_new_ldsd_entry(ld_sd_queue, size_ld_sd_queue):
    existing_tag = []
    for i in range(len(ld_sd_queue)):
        existing_tag.append(ld_sd_queue[i].ld_sd_tag)
    for i in range(size_ld_sd_queue):
        if 'ldsd'+str(i) not in existing_tag:
            return 'ldsd'+str(i)

# function: read a source register from the RAT
# returns (tag, value, valid): valid = 1 when the value is known
def read_register(register, rat_int, rat_fp):
    if register[0] == 'F':
        rat = rat_fp
    else:
        rat = rat_int
    number = int(register[1:])
    if type(rat[number]) == str:
        return rat[number], 0, 0
    else:
        return '', rat[number], 1

# function put ins into ROB
def put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, ldsd_tag):
    ROB.append(ROB_entry())
    # ROB_tag
    if len(ROB)==1:
        ROB[-1].ROB_tag = 'ROB0'
    else:
        index = ROB[-2].ROB_tag[3:]
        ROB[-1].ROB_tag = 'ROB'+str((int(index)+1)%size_ROB)
    # PC
    ROB[-1].PC = PC.PC
    # dest_tag
    if ins.split(' ')[0]=='Sd': # SD
        ROB[-1].dest_tag = ldsd_tag
    elif (ins.split(' ')[0]=='Bne') or (ins.split(' ')[0]=='Beq'): # branch: keep the offset
        ROB[-1].dest_tag = int(ins.split(' ')[-1])
    else: # ALU and LD instructions
        ROB[-1].dest_tag = ins.split(' ')[1]
    # issue
    ROB[-1].issue.append(cycle)

# function: put ins into reservation station
def put_ins_into_rs(station, index, ins, ROB, rat_int, rat_fp):
    entry = station[index]
    entry.busy = 1
    entry.op = ins.split(' ')[0]
    # reg 1
    register = ins.split(' ')[2] # register name
    entry.tag_1st, entry.value_1st, entry.valid_1st = read_register(register, rat_int, rat_fp)
    # reg 2
    register = ins.split(' ')[3] # register name or immediate number
    if (register[0] == 'F') or (register[0] == 'R'):
        entry.tag_2nd, entry.value_2nd, entry.valid_2nd = read_register(register, rat_int, rat_fp)
    else: # immediate number
        entry.tag_2nd = ''
        entry.value_2nd = int(register)
        entry.valid_2nd = 1
    # dest_tag
    entry.dest_tag = ROB[-1].ROB_tag

# function: put bne/beq into rs
def put_bne_into_rs(rs_int_adder, index, ins, rat_int, rat_fp, ROB):
    entry = rs_int_adder[index]
    entry.busy = 1
    entry.op = ins.split(' ')[0]
    # reg 1
    register = ins.split(' ')[1] # register name
    entry.tag_1st, entry.value_1st, entry.valid_1st = read_register(register, rat_int, rat_fp)
    # reg 2
    register = ins.split(' ')[2] # register name
    entry.tag_2nd, entry.value_2nd, entry.valid_2nd = read_register(register, rat_int, rat_fp)
    # dest_tag
    entry.dest_tag = ROB[-1].ROB_tag

# function: put ins into ld_sd_queue
def put_ins_into_ldsd(ldsd_tag, ld_sd_queue, ins, ROB, rat_int, rat_fp):
    ld_sd_queue.append(ld_sd_entry())
    # ld_sd_tag
    ld_sd_queue[-1].ld_sd_tag = ldsd_tag
    ld_sd_queue[-1].ready = 0
    ld_sd_queue[-1].op = ins.split(' ')[0]
    # data of a Sd: a value or the tag of the ROB entry producing it
    if ld_sd_queue[-1].op == 'Sd':
        register = ins.split(' ')[1] # register name
        if register[0] == 'F':
            ld_sd_queue[-1].data = rat_fp[int(register[1:])]
        else:
            ld_sd_queue[-1].data = rat_int[int(register[1:])]
    ld_sd_queue[-1].dest_tag = ROB[-1].ROB_tag
    # immediate and base register, e.g. 0(R1)
    operand = ins.split(' ')[-1]
    ld_sd_queue[-1].immediate = int(operand[:operand.index('(')])
    register = operand[operand.index('(')+1:-1] # register name
    ld_sd_queue[-1].reg_tag, ld_sd_queue[-1].reg_value, ld_sd_queue[-1].valid = read_register(register, rat_int, rat_fp)

# function: check space of reservation station
def check_rs_space(station):
    index = -1
    for i in range(len(station)):
        if station[i].busy == 0:
            index = i
            break
    return index

# update RAT (R0 is hardwired to 0, so it is never renamed)
def update_rat(ROB, rat_int, rat_fp):
    if ROB[-1].dest_tag[0] == 'F':
        rat_fp[int(ROB[-1].dest_tag[1:])] = ROB[-1].ROB_tag
    elif (ROB[-1].dest_tag[0] == 'R') and (ROB[-1].dest_tag != 'R0'):
        rat_int[int(ROB[-1].dest_tag[1:])] = ROB[-1].ROB_tag
    else:
        pass

# function: predict a branch with the BTB (one bit predictor)
# returns the predicted next PC
def predict_branch(btb, PC):
    entry = btb[PC.PC % len(btb)]
    if (entry.pc == PC.PC) and (entry.taken == 1):
        return entry.target
    else:
        return PC.PC + 1

# function: issue one instruction, returns True if it was issued
def issue_one(cycle, PC, instructions, ROB, size_ROB,
        rs_int_adder,
        rs_fp_adder,
        rs_fp_multi,
        ld_sd_queue, size_ld_sd_queue,
        rat_int, rat_fp, btb):
    # fetch 1 instruction
    ins = instructions[PC.PC]
    op = ins.split(' ')[0]
    issued = False
    '''decode'''
    # LD/SD instructions
    if (op=='Ld')|(op=='Sd'):
        # check space
        if (len(ROB)<size_ROB)&(len(ld_sd_queue)<size_ld_sd_queue):
            # find ldsd_tag
            ldsd_tag = find_tag_new_ldsd_entry(ld_sd_queue, size_ld_sd_queue)
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, ldsd_tag)
            # put ins into ld_sd_queue
            put_ins_into_ldsd(ldsd_tag, ld_sd_queue, ins, ROB, rat_int, rat_fp)
            # update RAT
            update_rat(ROB, rat_int, rat_fp)
            # PC
            PC.PC +=1
            issued = True
    # integer adder instructions
    elif (op=='Add')|(op=='Addi')|(op=='Sub'):
        # check space
        if (len(ROB)<size_ROB)&(check_rs_space(rs_int_adder)>=0):
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, '')
            # put ins into rs_int_adder
            index = check_rs_space(rs_int_adder)
            put_ins_into_rs(rs_int_adder, index, ins, ROB, rat_int, rat_fp)
            # update RAT
            update_rat(ROB, rat_int, rat_fp)
            # PC
            PC.PC +=1
            issued = True
    # fp adder instructions
    elif (op=='Add.d')|(op=='Sub.d'):
        # check space
        if (len(ROB)<size_ROB)&(check_rs_space(rs_fp_adder)>=0):
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, '')
            # put ins into rs_fp_adder
            index = check_rs_space(rs_fp_adder)
            put_ins_into_rs(rs_fp_adder, index, ins, ROB, rat_int, rat_fp)
            # update RAT
            update_rat(ROB, rat_int, rat_fp)
            # PC
            PC.PC +=1
            issued = True
    # fp multiplier instructions
    elif (op=='Mult.d'):
        # check space
        if (len(ROB)<size_ROB)&(check_rs_space(rs_fp_multi)>=0):
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, '')
            # put ins into rs_fp_multi
            index = check_rs_space(rs_fp_multi)
            put_ins_into_rs(rs_fp_multi, index, ins, ROB, rat_int, rat_fp)
            # update RAT
            update_rat(ROB, rat_int, rat_fp)
            # PC
            PC.PC +=1
            issued = True
    # Bne / Beq
    elif (op=='Bne')|(op=='Beq'):
        # check space
        if (len(ROB)<size_ROB)&(check_rs_space(rs_int_adder)>=0):
            # put ins into ROB
            put_ins_into_ROB(ROB, size_ROB, PC, cycle, ins, '')
            # put ins into rs_int_adder
            index = check_rs_space(rs_int_adder)
            put_bne_into_rs(rs_int_adder, index, ins, rat_int, rat_fp, ROB)
            # predict the branch and keep fetching from the predicted PC
            ROB[-1].predict = predict_branch(btb, PC)
            PC.PC = ROB[-1].predict
            issued = True
    else:
        pass
    return issued

""""""
def issue(cycle, PC, instructions, ROB, size_ROB,
        rs_int_adder,
        rs_fp_adder,
        rs_fp_multi,
        ld_sd_queue, size_ld_sd_queue,
        rat_int, rat_fp, btb, issue_width):
    # issue up to issue_width instructions in program order,
    # stop at the first one that cannot be issued (no space)
    for i in range(issue_width):
        if PC.PC >= len(instructions):
            break
        ins = instructions[PC.PC]
        issued = issue_one(cycle, PC, instructions, ROB, size_ROB,
                rs_int_adder, rs_fp_adder, rs_fp_multi,
                ld_sd_queue, size_ld_sd_queue,
                rat_int, rat_fp, btb)
        if issued == False:
            break
        # a branch ends the fetch group of this cycle
        if (ins.split(' ')[0]=='Bne') or (ins.split(' ')[0]=='Beq'):
            break
