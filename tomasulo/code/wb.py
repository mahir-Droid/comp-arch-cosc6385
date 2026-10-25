# Qing
# 29th May 2017
# modified: up to issue_width results are broadcast per cycle, the oldest
#           result goes first, the RAT is only updated when it still points
#           at the broadcasting instruction

'''
1. pick the oldest result (program order) that was produced in an earlier cycle
2. broadcast it on the cdb
3. remove it from the results queue
'''
# function: find ROB entry by tag
def find_ROB_entry(ROB, tag):
    for index in range(len(ROB)):
        if ROB[index].ROB_tag == tag:
            return index
    return -1

# function: boroadcast
# rat_int, rat_fp, reservation stations, ld_sd_queue, ROB
def boroadcast(result, rat_int, rat_fp,
                rs_int_adder, rs_fp_adder, rs_fp_multi,
                ld_sd_queue, ROB, cycle):
    # dest_tag
    dest_tag = result.dest_tag
    index = find_ROB_entry(ROB, dest_tag)
    reg_tag = ROB[index].dest_tag
    # rat_int (only if a younger instruction has not renamed the register again)
    if reg_tag[0] == 'R':
        if rat_int[int(reg_tag[1:])] == dest_tag:
            rat_int[int(reg_tag[1:])] = result.value
    # rat_fp
    if reg_tag[0] == 'F':
        if rat_fp[int(reg_tag[1:])] == dest_tag:
            rat_fp[int(reg_tag[1:])] = result.value
    # rs list
    rs_list = [rs_int_adder, rs_fp_adder, rs_fp_multi]
    for rs in rs_list:
        for element in rs:
            if element.busy == 0:
                continue
            if (element.tag_1st==dest_tag)&(element.valid_1st==0):
                element.value_1st = result.value
                element.valid_1st = 1
            if (element.tag_2nd==dest_tag)&(element.valid_2nd==0):
                element.value_2nd = result.value
                element.valid_2nd = 1
    # ld_sd_queue
    for element in ld_sd_queue:
        if (element.op=='Sd')&(element.data==dest_tag):
            element.data = result.value
        if (element.valid==0)&(element.reg_tag==dest_tag):
            element.reg_value = result.value
            element.valid = 1
    # ROB
    ROB[index].value = result.value
    ROB[index].cdb.append(cycle)

# function: wb
def wb(rat_int, rat_fp,
        rs_int_adder, rs_fp_adder, rs_fp_multi,
        ld_sd_queue, ROB, cycle,
        results_buffer, issue_width):
    count = 0
    while count < issue_width:
        # the oldest result that was produced in an earlier cycle
        pick = None
        oldest = len(ROB)
        for result in results_buffer:
            if result.cycle < cycle:
                index = find_ROB_entry(ROB, result.dest_tag)
                if index < oldest:
                    oldest = index
                    pick = result
        if pick == None:
            break
        results_buffer.remove(pick)
        boroadcast(pick, rat_int, rat_fp,
                    rs_int_adder, rs_fp_adder, rs_fp_multi,
                    ld_sd_queue, ROB, cycle)
        count += 1
