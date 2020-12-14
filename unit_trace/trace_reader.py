###############################################################################
# Description
###############################################################################

# trace_reader(files) returns an iterator which produces records
# in order from the files given. (the param is a list of files.)
#
# Each record is just a Python object. It is guaranteed to have the following
# attributes:
#   - 'pid': pid of the task
#   - 'job': job number for that task
#   - 'cpu', given by LITMUS
#   - 'when', given by LITMUS as a timestamp. LITMUS does not provide a
#       timestamp for all records. In this case, when is set to 0.
#   - 'type', a numerical value given by LITMUS
#   - 'type_name', a human-readable name defined in this module
#   - 'record_type', set to 'event' by this module (to distinguish from, e.g.,
#       error records produced elsewhere).
#   - Possible additional attributes, depending on the type of record.
#
# To find out exactly what attributes are set for each record type, look at
#     the trace-parsing information at the bottom of this file.

###############################################################################
# Imports
###############################################################################

import struct
import sys


###############################################################################
# Public functions
###############################################################################

# Generator function returning an iterable over records in a trace file.
def trace_reader(files, buffsize):

    # Yield a record containing the input files
    # This is used by progress.py to calculate progress
    class Obj: pass
    record = Obj()
    record.record_type = "meta"
    record.type_name = "trace_files"
    record.files = files
    yield record

    # Yield a record indicating the number of CPUs, used by the G-EDF test
    record = Obj()
    record.record_type = "meta"
    record.type_name = "num_cpus"
    record.num_cpus = len(files)
    yield record

    # Create iterators for each file and a buffer to store records in
    file_iters = [] # file iterators
    file_iter_buff = [] # file iterator buffers
    for file in files:
        file_iter = _get_file_iter(file)
        file_iters.append(file_iter)
        try:
            file_iter_buff.append([file_iter.next()])
        # What if there isn't a single valid record in a trace file?
        # file_iter.next() will raise a StopIteration that we need to catch
        except:
            # Forget that file iter
            file_iters.pop()

    # We keep some number of records (given as buffsize) in each buffer and
    # then keep the buffer sorted.  This is because records may have been
    # recorded slightly out of order.  The 'try' and 'except' catches the case
    # where there are less than buffsize records in a file (throwing a
    # StopIteration) which otherwise would propogate up and cause the
    # trace_reader generator itself to throw a StopIteration.
    for x in range(0,len(file_iter_buff)):
        try:
            for y in range(0,buffsize):
                file_iter_buff[x].append(file_iters[x].next())
        except StopIteration:
            pass
    for x in range(0,len(file_iter_buff)):
        file_iter_buff[x] = sorted(file_iter_buff[x],key=lambda rec: rec.when)

    # Remember the time of the last record. This way, we can make sure records
    # truly are produced in monotonically increasing order by time and terminate
    # fatally if they are not.
    last_time = None

    # We want to give records ID numbers so users can filter by ID
    id = 0

    # Keep pulling records as long as we have a buffer
    while len(file_iter_buff) > 0:
        # Select the earliest record from those at the heads of the buffers
        earliest = -1
        buff_to_refill = -1
        for x in range(0,len(file_iter_buff)):
            if earliest==-1 or file_iter_buff[x][0].when < earliest.when:
                earliest = file_iter_buff[x][0]
                buff_to_refill = x

        # Take it out of the buffer
        del file_iter_buff[buff_to_refill][0]

        # Try to append a new record to the buffer (if there is another) and
        #     then keep the buffer sorted
        try:
            file_iter_buff[buff_to_refill].append(file_iters[buff_to_refill].next())
            file_iter_buff[buff_to_refill] = sorted(file_iter_buff[buff_to_refill],
                key=lambda rec: rec.when)

        # If there aren't any more records, fine. Unless the buffer is also empty.
        # If that is the case, delete the buffer.
        except StopIteration:
            if len(file_iter_buff[buff_to_refill]) < 1:
                del file_iter_buff[buff_to_refill]
                del file_iters[buff_to_refill]

        # Give the record an id number
        id += 1
        earliest.id = id

        # Check for monotonically increasing time
        if last_time is not None and earliest.when < last_time:
            record = Obj()
            record.record_type = "meta"
            record.type_name = "out_of_order_warning"
            record.id = earliest.id
            yield record
        else:
            last_time = earliest.when

        # Yield the record
        yield earliest

###############################################################################
# Private functions
###############################################################################

# Returns an iterator to pull records from a file
def _get_file_iter(file):
    f = open(file,'rb')
    while True:
        data = f.read(RECORD_HEAD_SIZE)
        try:
            type_num = struct.unpack_from('b',data)[0]
        except struct.error:
            break #We read to the end of the file
        try:
            type = _get_type(type_num)
        except:
            sys.stderr.write("Skipping record with invalid type num: %d\n" %
                (type_num))
            continue
        try:
            values = struct.unpack_from(StHeader.format +
                type.format,data)
            record_dict = dict(zip(type.keys,values))
	    if(type_num == 2):
		record_dict["partition"] = ord(record_dict["partition"])
        except struct.error:
            f.close()
            sys.stderr.write("Skipping record that does not match proper" +
                " struct formatting\n")
            continue

        # Convert the record_dict into an object
        record = _dict2obj(record_dict)

        # Give it a type name (easier to work with than type number)
        record.type_name = _get_type_name(type_num)

        # All records should have a 'record type' field.
        # e.g. these are 'event's as opposed to 'error's
        record.record_type = "event"

        # If there is no timestamp, set the time to 0
        if 'when' not in record.__dict__.keys():
            record.when = 0
	#for k in record.__dict__.keys():
	#    print(k)
	#    print(record.__dict__[k])
	#print("--------------------------")
        yield record

# Convert a dict into an object
def _dict2obj(d):
    class Obj(object): pass
    o = Obj()
    for key in d.keys():
        o.__dict__[key] = d[key]
    return o

###############################################################################
# Trace record data types and accessor functions
###############################################################################

# Each class below represents a type of event record. The format attribute
# specifies how to decode the binary record and the keys attribute
# specifies how to name the pieces of information decoded. Note that all
# event records have a common initial 24 bytes, represented by the StHeader
# class.

RECORD_HEAD_SIZE = 24

class StHeader:
    format =  '<bbhi'
    formatStr = struct.Struct(format)
    keys = ['type','cpu','pid','job']
    message = 'The header.'

class StActionData:
    format =  'Qb'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when','action']
    message = 'An action was performed.'

class StNameData:
    format =  '16s'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['name']
    message = 'The name of the executable of this process.'

class StParamData:
    format =  'IIIc'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['wcet','period','phase','partition']
    message = 'Regular parameters.'

class StReleaseData:
    format =  'QQ'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when','deadline']
    message = 'A job was/is going to be released.'

#Not yet used by Sched Trace
class StAssignedData:
    format =  'Qc'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when','target']
    message = 'A job was assigned to a CPU.'

class StSwitchToData:
    format =  'QI'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when','exec_time']
    message = 'A process was switched to on a given CPU.'

class StSwitchAwayData:
    format =  'QI'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when','exec_time']
    message = 'A process was switched away on a given CPU.'

class StCompletionData:
    #format =  'Q3x?c'
    format = 'Q3xcc'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when','forced?','flags']
    message = 'A job completed.'

class StBlockData:
    format =  'Q'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when']
    message = 'A task blocks.'

class StResumeData:
    format =  'Q'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when']
    message = 'A task resumes.'

class StSysReleaseData:
    format =  'QQ'
    formatStr = struct.Struct(StHeader.format + format)
    keys = StHeader.keys + ['when','release']
    message = 'All tasks have checked in, task system released by user'

# Return the binary data type, given the type_num
def _get_type(type_num):
    types = [None,StNameData,StParamData,StReleaseData,StAssignedData,
             StSwitchToData,StSwitchAwayData,StCompletionData,StBlockData,
             StResumeData,StActionData,StSysReleaseData]
    if type_num > len(types)-1 or type_num < 1:
        raise Exception
    return types[type_num]

# Return the type name, given the type_num (this is simply a convenience to
#     programmers of other modules)
def _get_type_name(type_num):
    type_names = [None,"name","params","release","assign","switch_to",
        "switch_away","completion","block","resume","action","sys_release"]
    return type_names[type_num]
