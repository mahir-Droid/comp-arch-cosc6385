# Qing
# 21st May 2017
# modified: added the register and memory dump printed at the end

# function: print RS/ROB status
def ps(unit):
    if(len(unit)==0):
        print('empty!')
    else:
        # get all fields in namedtuple
        fields_list = unit[0]._fields
        for unit_item in unit:
            print ('******')
            for field in fields_list:
                print(field+': ', str(getattr(unit_item, field)))

# function: print single namedtuple
def pss(snt):
    fields_list = snt._fields
    for field in fields_list:
        print (field+': ', str(getattr(snt, field)))

# function: print one register file, 8 registers per row
def print_reg_file(regs, prefix):
    for start in range(0, len(regs), 8):
        names = ''.ljust(8)
        values = 'value:'.ljust(8)
        for i in range(start, start+8):
            names += (prefix+str(i)).ljust(8)
            values += str(regs[i]).ljust(8)
        print(names)
        print(values)

# function: print register values
def print_registers(reg_int, reg_fp):
    print('')
    print('REGISTER VALUES')
    print('')
    print_reg_file(reg_int, 'R')
    print_reg_file(reg_fp, 'F')

# function: print non-zero memory values
def print_memory(memory):
    print('')
    print('NON-ZERO MEMORY VALUES')
    print('')
    print('Addresses'.ljust(15) + 'Values')
    for address in range(len(memory)):
        if memory[address] != 0:
            print(str(address).ljust(15) + str(memory[address]))
