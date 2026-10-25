# Qing
# 29th may 2017
# modified: up to issue_width instructions commit per cycle, branches commit,
#           stores write the memory at commit, R0 stays 0
'''
1. commit the ROB head when it is done (broadcast in an earlier cycle)
2. a Sd writes its data into the memory when it commits
'''
from mem import memory_free, find_ldsd_entry, sd_ready, put_entry_into_ld_sd_mem, finish_ld_sd_mem

# function: print ROB entry
def print_ROB(entry, instructions):
    item = instructions[entry.PC].ljust(30)
    item += str(entry.issue).ljust(15)
    item += str(entry.exe).ljust(15)
    item += str(entry.mem).ljust(15)
    item += str(entry.cdb).ljust(15)
    item += str(entry.commit)
    print(item)
# function: modify architectual reg
def modify_arch_reg(entry, reg_int, reg_fp):
    if entry.dest_tag[0] == 'F':
        reg_fp[int(entry.dest_tag[1:])] = entry.value
    elif (entry.dest_tag[0] == 'R') and (entry.dest_tag != 'R0'):
        reg_int[int(entry.dest_tag[1:])] = entry.value
    else:
        pass

# function: commit
def commit(ROB, reg_int, reg_fp, cycle, instructions, issue_width,
        ld_sd_queue, ld_sd_mem, time_ld_sd_mem, results_buffer, memory):
    for i in range(issue_width):
        if len(ROB) == 0:
            break
        head = ROB[0]
        op = instructions[head.PC].split(' ')[0]
        if op == 'Sd':
            # the Sd needs its address and data, and the memory has to be free
            entry = find_ldsd_entry(ld_sd_queue, head.dest_tag)
            if (sd_ready(entry, ROB, cycle) == False) or (memory_free(ld_sd_mem, cycle) == False):
                break
            # write the memory, this takes time_ld_sd_mem cycles
            ld_sd_queue.remove(entry)
            put_entry_into_ld_sd_mem(ld_sd_mem, entry, cycle, time_ld_sd_mem)
            head.mem.extend([cycle, cycle+time_ld_sd_mem-1])
            finish_ld_sd_mem(ld_sd_mem, time_ld_sd_mem, results_buffer, memory, cycle)
        elif (op == 'Bne') or (op == 'Beq'):
            # a branch commits once it has been resolved
            if (len(head.exe) < 2) or (head.exe[-1] >= cycle):
                break
        else:
            # broadcasted instructions
            if (len(head.cdb) == 0) or (head.cdb[0] >= cycle):
                break
            modify_arch_reg(head, reg_int, reg_fp)
        head.commit.append(cycle)
        entry = ROB.popleft()
        print_ROB(entry, instructions)
