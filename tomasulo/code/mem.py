# Qing
# 26th May 2017
# modified: a load waits until the addresses of all earlier stores are known,
#           forwarding takes one cycle, loads go to memory oldest first,
#           stores only use the memory when they commit (see commit.py)

'''
1. Ld forward check from Sd in ld_sd_queue
    -- only check nearest Sd instruction
2. execute LD/SD instruction in ld_sd_mem (single ported memory)
    -- once LD instruction gets data, put it into results_buffer
    -- LD instruction is removed from ld_sd_queue when it goes to the memory
    -- SD instruction is removed at commit stage
3. fetch new LD instruction into ld_sd_mem
    -- the oldest Ld whose address is known, all earlier Sd addresses are known and no address matches
'''
from init import fu_result

# function: find ROB entry by tag
def find_ROB_entry(ROB, tag):
    for index in range(len(ROB)):
        if ROB[index].ROB_tag == tag:
            return index
    return -1

# function: check if the address of a ld/sd entry was calculated in an earlier cycle
def address_ready(entry, ROB, cycle):
    if entry.ready == 0:
        return False
    index = find_ROB_entry(ROB, entry.dest_tag)
    return ROB[index].exe[-1] < cycle

# function: forward check from sd
# look for the nearest earlier Sd with the same address, returns its data or None
# (None also when an earlier Sd address is still unknown)
def forward_check_from_sd(ld_sd_queue, index, ROB, cycle):
    for i in reversed(range(index)):
        if (ld_sd_queue[i].op=='Sd'):
            if address_ready(ld_sd_queue[i], ROB, cycle) == False:
                return None
            if ld_sd_queue[i].address == ld_sd_queue[index].address:
                if (type(ld_sd_queue[i].data)==int)|(type(ld_sd_queue[i].data)==float):
                    return ld_sd_queue[i].data
                return None
    return None

# function: check if previous all Sds are ready and un-matched
def check_all_previous_Sd_no_match(ld_sd_queue, index, ROB, cycle):
    flag = True
    for i in range(index):
        # all Sd instructions
        if (ld_sd_queue[i].op=='Sd'):
            if address_ready(ld_sd_queue[i], ROB, cycle) == False:
                flag = False
                break
            elif (ld_sd_queue[i].address==ld_sd_queue[index].address):
                flag = False
                break
            else:
                pass
    return flag

# function: check if the (single ported, non pipelined) memory can start a new access
def memory_free(ld_sd_mem, cycle):
    return (ld_sd_mem.busy == 0) and (ld_sd_mem.end < cycle)

# function: find the ld_sd_queue entry of a Sd
def find_ldsd_entry(ld_sd_queue, ldsd_tag):
    for element in ld_sd_queue:
        if element.ld_sd_tag == ldsd_tag:
            return element
    return None

# function: check if a Sd has its address and its data
def sd_ready(entry, ROB, cycle):
    if address_ready(entry, ROB, cycle) == False:
        return False
    return (type(entry.data) == int) or (type(entry.data) == float)

# function: check if the ROB head is a Sd that is waiting for the memory
def head_sd_waiting(ROB, ld_sd_queue, cycle):
    if len(ROB) == 0:
        return False
    if (type(ROB[0].dest_tag) != str) or (ROB[0].dest_tag[:4] != 'ldsd'):
        return False
    entry = find_ldsd_entry(ld_sd_queue, ROB[0].dest_tag)
    return sd_ready(entry, ROB, cycle)

# function: put entry into ld_sd_mem
def put_entry_into_ld_sd_mem(ld_sd_mem, entry, cycle, time_ld_sd_mem):
    ld_sd_mem.busy = 1
    ld_sd_mem.cycle = 1
    ld_sd_mem.end = cycle + time_ld_sd_mem - 1
    ld_sd_mem.address = entry.address
    ld_sd_mem.dest_tag = entry.dest_tag
    ld_sd_mem.op = entry.op
    if ld_sd_mem.op == 'Sd':
        ld_sd_mem.data = entry.data

# function: the memory access finishes after time_ld_sd_mem cycles
def finish_ld_sd_mem(ld_sd_mem, time_ld_sd_mem, results_buffer, memory, cycle):
    if (ld_sd_mem.busy == 1) and (ld_sd_mem.cycle >= time_ld_sd_mem):
        ld_sd_mem.busy = 0
        if ld_sd_mem.op == 'Ld':
            # put Ld data into results_buffer
            results_buffer.append(fu_result())
            results_buffer[-1].value = memory[ld_sd_mem.address]
            results_buffer[-1].dest_tag = ld_sd_mem.dest_tag
            results_buffer[-1].cycle = cycle
        # put data into memory for Sd
        else:
            memory[ld_sd_mem.address] = ld_sd_mem.data

# function: mem
def mem(ld_sd_queue, ld_sd_mem, time_ld_sd_mem, results_buffer,
        memory, ROB, cycle):
    '''ld_sd_mem execution (one more cycle)'''
    if ld_sd_mem.busy == 1:
        ld_sd_mem.cycle += 1
        finish_ld_sd_mem(ld_sd_mem, time_ld_sd_mem, results_buffer, memory, cycle)
    '''forward check for all Ld instructions (takes one cycle)'''
    remove_list = []
    for index in range(len(ld_sd_queue)):
        element = ld_sd_queue[index]
        if (element.op=='Ld') and address_ready(element, ROB, cycle):
            data = forward_check_from_sd(ld_sd_queue, index, ROB, cycle)
            if data != None:
                # Ld gets data from the Sd
                results_buffer.append(fu_result())
                results_buffer[-1].value = data
                results_buffer[-1].dest_tag = element.dest_tag
                results_buffer[-1].cycle = cycle
                # write mem cycle in ROB
                rob_index = find_ROB_entry(ROB, element.dest_tag)
                ROB[rob_index].mem.append(cycle)
                # remove the Ld instruction
                remove_list.append(element)
    for element in remove_list:
        ld_sd_queue.remove(element)
    '''fetch the oldest ready Ld into ld_sd_mem'''
    # (a Sd at the ROB head is older than every Ld, it gets the memory first)
    if memory_free(ld_sd_mem, cycle) and (head_sd_waiting(ROB, ld_sd_queue, cycle) == False):
        for index in range(len(ld_sd_queue)):
            element = ld_sd_queue[index]
            if (element.op=='Ld') and address_ready(element, ROB, cycle):
                # all previous Sd addresses are known and none of them matches
                if check_all_previous_Sd_no_match(ld_sd_queue, index, ROB, cycle):
                    put_entry_into_ld_sd_mem(ld_sd_mem, element, cycle, time_ld_sd_mem)
                    ld_sd_queue.remove(element)
                    # write mem cycles in ROB
                    rob_index = find_ROB_entry(ROB, element.dest_tag)
                    ROB[rob_index].mem.extend([cycle, cycle+time_ld_sd_mem-1])
                    finish_ld_sd_mem(ld_sd_mem, time_ld_sd_mem, results_buffer, memory, cycle)
                    break
