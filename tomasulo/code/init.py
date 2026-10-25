# Qing
# 21st May 2017
# modified: read the hardware configuration from the input file,
#           branch target buffer, extra fields for branch handling

from collections import namedtuple

'''define data types'''
# reservation station
def rs_entry():
    rs_entry = namedtuple('rs_entry', 'busy, op, tag_1st, value_1st, valid_1st, tag_2nd, value_2nd, valid_2nd, dest_tag')
    temp = rs_entry
    return temp
# functional unit
def fu_entry():
    fu_entry = namedtuple('fu_entry', 'cycle, op, value1, value2, dest_tag')
    temp = fu_entry
    return temp
# function result
# cycle = the cycle in which the result was produced, it can only be
# broadcast on the CDB in a later cycle
def fu_result():
    fu_result = namedtuple('fu_result', 'value, dest_tag, cycle')
    temp = fu_result
    return temp
# ld/sd entry
def ld_sd_entry():
    ld_sd_entry = namedtuple('ld_sd_entry', 'ld_sd_tag, ready, op, address, data, dest_tag, immediate, reg_tag, reg_value, valid')
    temp = ld_sd_entry
    temp.data = None
    temp.address = None
    return temp
# ld/sd exe
# end = last cycle in which the unit was used, it is free again in the next cycle
def ld_sd_exe():
    ld_sd_exe = namedtuple('ld_sd_exe', 'busy, cycle, value1, value2, dest_tag, end')
    temp = ld_sd_exe
    temp.busy = 0
    temp.end = 0
    return temp
# ld/sd mem
def ld_sd_mem():
    ld_sd_mem = namedtuple('ld_sd_mem', 'busy, cycle, op, data, address, dest_tag, end')
    temp = ld_sd_mem
    temp.busy = 0
    temp.end = 0
    return temp
# ROB_entry
# predict = the next PC that was predicted when a branch was issued
def ROB_entry():
    ROB_entry = namedtuple('ROB_entry', 'ROB_tag, PC, value, dest_tag, issue, exe, mem, cdb, commit, predict')
    temp = ROB_entry
    temp.issue = []
    temp.exe = []
    temp.mem = []
    temp.cdb = []
    temp.commit =[]
    temp.predict = -1
    return temp
# PC
# valid = 0 means fetch is stopped (after a misprediction),
# resume = the cycle in which fetch starts again,
# squash = ROB tag of a mispredicted branch that has to be handled
def PC():
    PC = namedtuple('PC', 'PC, valid, resume, squash')
    temp = PC
    temp.resume = 0
    temp.squash = ''
    return temp
# branch target buffer entry (one bit predictor)
def btb_entry():
    btb_entry = namedtuple('btb_entry', 'pc, target, taken')
    temp = btb_entry
    temp.pc = -1
    temp.target = 0
    temp.taken = 0
    return temp

# function: build rs
def build_rs(num):
    rs = []
    for _ in range(num):
        temp = rs_entry()
        temp.busy = 0
        rs.extend([temp])
    return rs
# function: build btb
def build_btb(num):
    btb = []
    for _ in range(num):
        btb.append(btb_entry())
    return btb

# function: pick the numbers out of a configuration line
def get_numbers(line):
    numbers = []
    for word in line.replace('=', ' ').split():
        if word.lstrip('-').isdigit():
            numbers.append(int(word))
    return numbers

# function: turn one assembly line into the form 'Op A B C'
# (the input is case insensitive and may use commas)
op_names = {'ld':'Ld', 'sd':'Sd', 'add':'Add', 'add.d':'Add.d', 'addi':'Addi',
            'sub':'Sub', 'sub.d':'Sub.d', 'mult.d':'Mult.d', 'bne':'Bne', 'beq':'Beq'}
def normalize_instruction(line):
    parts = line.replace(',', ' ').split()
    op = parts[0].lower()
    if op not in op_names:
        return ''
    words = [op_names[op]]
    for part in parts[1:]:
        words.append(part.upper())
    return ' '.join(words)

# function: read the input file
# returns the configuration (a dictionary) and the list of instructions
def read_input(codefile):
    config = {'rs_int_adder':2, 'time_int_adder':1, 'num_int_adder':1,
              'rs_fp_adder':3, 'time_fp_adder':3, 'num_fp_adder':1,
              'rs_fp_multi':2, 'time_fp_multi':20, 'num_fp_multi':1,
              'size_ld_sd_queue':3, 'time_ld_sd_exe':1, 'time_ld_sd_mem':4,
              'size_ROB':128, 'issue_width':1,
              'reg_int':{}, 'reg_fp':{}, 'memory':{}}
    instructions = []
    with open(codefile) as f:
        lines = f.read().splitlines()
    for line in lines:
        line = line.strip()
        low = line.lower()
        if len(line) == 0 or line[0] == '#':
            continue
        if low.startswith('integer adder'):
            numbers = get_numbers(line)
            config['rs_int_adder'] = numbers[0]
            config['time_int_adder'] = numbers[1]
            config['num_int_adder'] = numbers[2]
        elif low.startswith('fp adder'):
            numbers = get_numbers(line)
            config['rs_fp_adder'] = numbers[0]
            config['time_fp_adder'] = numbers[1]
            config['num_fp_adder'] = numbers[2]
        elif low.startswith('fp multiplier'):
            numbers = get_numbers(line)
            config['rs_fp_multi'] = numbers[0]
            config['time_fp_multi'] = numbers[1]
            config['num_fp_multi'] = numbers[2]
        elif low.startswith('load/store'):
            numbers = get_numbers(line)
            config['size_ld_sd_queue'] = numbers[0]
            config['time_ld_sd_exe'] = numbers[1]
            config['time_ld_sd_mem'] = numbers[2]
        elif low.startswith('rob entries'):
            config['size_ROB'] = get_numbers(line)[0]
        elif low.startswith('issue width'):
            config['issue_width'] = get_numbers(line)[0]
        elif '=' in line:
            # initial register and memory values, e.g. R1=12, F20=3.0, Mem[4]=3.0
            for item in line.split(','):
                name, value = item.split('=')
                name = name.strip()
                if '.' in value:
                    value = float(value)
                else:
                    value = int(value)
                if name.upper().startswith('MEM'):
                    address = int(name[name.index('[')+1:name.index(']')])
                    config['memory'][address] = value
                elif name[0].upper() == 'R':
                    config['reg_int'][int(name[1:])] = int(value)
                elif name[0].upper() == 'F':
                    config['reg_fp'][int(name[1:])] = value
        else:
            ins = normalize_instruction(line)
            if ins != '':
                instructions.append(ins)
    return config, instructions
