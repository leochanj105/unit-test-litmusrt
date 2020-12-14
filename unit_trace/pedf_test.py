###############################################################################
# Description
###############################################################################

# G-EDF Test

###############################################################################
# Imports
###############################################################################

import copy
import sys


###############################################################################
# Public Functions
###############################################################################

task_partition = dict()	# Partitions of each task

def pedf_test(stream):

    # System model
    on_cpu = []     # Tasks on a CPU
    off_cpu = []    # Tasks not on a CPU

    m = None        # CPUs
    timer_resolution = 1000000	    # Resolution of gaps between jobs

    # Time of the last record we saw. Only run the G-EDF test when the time
    # is updated.
    last_time = 0

    # First event for the latest timestamp. This is used to match up
    # inversion starts and ends with the first event from the previous
    # timestamp, which is the first event that could have triggered
    # the inversion start or end.
    first_event_this_timestamp = 0

    for record in stream:
        if record.record_type != "event":
            if record.record_type == "meta" and record.type_name == "num_cpus":
                m = record.num_cpus
		for partition in range(m):
		    on_cpu.append([])
		    off_cpu.append([])
            continue
	
	if record.type_name == "params":
	    task_partition[record.pid] = record.partition
	    continue

	# Skip the initial setup jobs
	if record.job < 3:
	    continue

        # Bookkeeping iff the timestamp has moved forward.
        # Check for inversion starts and ends and yield them.
        # (It is common to have records with simultaneous timestamps,
        # so we only check when the time has moved forward)
        # Also, need to update the first_event_this_timestamp variable
        if last_time is not None and (last_time // timer_resolution) != (record.when // timer_resolution):
            errors = _pedf_check(off_cpu,on_cpu,last_time,m,
                record.id - 1)
            first_event_this_timestamp = record.id
            for error in errors:
                yield error

        # Add a newly-released Job to the off_cpu queue
        if record.type_name == 'release':
            off_cpu[record.cpu].append(Job(record))

        # Move a Job from the off_cpu queue to on_cpu
        elif record.type_name == 'switch_to':
            pos = _find_job(record,off_cpu[record.cpu])
            if pos is None:
                msg = "Event %d tried to switch to a job that was not on the"
                msg += " off_cpu queue\n"
                msg = msg % (record.id)
                sys.stderr.write(msg)
                exit()
            job = off_cpu[record.cpu][pos]
            del off_cpu[record.cpu][pos]
            on_cpu[record.cpu].append(job)

        # Mark a Job as completed.
        # The only time a Job completes when it is not on a
        # CPU is when it is the last job of the task.
        elif record.type_name == 'completion':
            pos = _find_job(record,on_cpu[record.cpu])
   	    job = None
            if pos is not None:
                on_cpu[record.cpu][pos].is_complete = True
		job = on_cpu[record.cpu][pos]
		del on_cpu[record.cpu][pos]
            else:
                pos = _find_job(record,off_cpu[record.cpu])
		job = off_cpu[record.cpu][pos]
                del off_cpu[record.cpu][pos]
	    if(record.when > job.deadline):
		yield Error(job, off_cpu[record.cpu], on_cpu[record.cpu], record.id, record.when)

        # A job is switched away from a CPU. If it has
        # been marked as complete, remove it from the model.
        elif record.type_name == 'switch_away':
            pos = _find_job(record,on_cpu[record.cpu])
            if pos is None and record.job:
                msg = ("Event %d tried to switch away a job" +
                    " that was not running\n")
                msg = msg % (record.id)
                sys.stderr.write(msg)
                exit()
            job = on_cpu[record.cpu][pos]
            del on_cpu[record.cpu][pos]
            if job.is_complete == False:
                off_cpu[record.cpu].append(job)

        # A job has been blocked.
        elif record.type_name == 'block':
            pos = _find_job(record,on_cpu[record.cpu])
            # What if the job is blocked AFTER being switched away?
            # This is a bug in some versions of LITMUS.
            if pos is None:
                pos = _find_job(record,off_cpu[record.cpu])
                job = off_cpu[record.cpu][pos]
            else:
                job = on_cpu[record.cpu][pos]
            job.is_blocked = True

        # A job is resumed
        elif record.type_name == 'resume':
            pos = _find_job(record,off_cpu[record.cpu])
            job = off_cpu[record.cpu][pos]
            job.is_blocked = False

        last_time = record.when
        yield record

###############################################################################
# Private Functions
###############################################################################

# Internal representation of a Job
class Job(object):
    def __init__(self, record):
        self.pid = record.pid
        self.job = record.job
        self.deadline = record.deadline
        self.is_complete = False
        self.is_blocked = False
        self.inversion_start = None
        self.inversion_end = None
        self.inversion_start_id = None
        self.inversion_start_triggering_event_id = None
	self.partition = record.cpu
    def __str__(self):
        return "(%d.%d:%d on %d)" % (self.pid,self.job,self.deadline, self.partition)

# P-EDF errors: the start or end of an inversion / deadline misses
class Error(object):
    id = 0
    def __init__(self, job, off_cpu, on_cpu,first_event_this_timestamp, late_completion = None, partition = None):
        Error.id += 1
        self.id = Error.id
        self.job = copy.copy(job)
        self.off_cpu = copy.copy(off_cpu)
        self.on_cpu = copy.copy(on_cpu)
        self.record_type = 'error'
        self.triggering_event_id = first_event_this_timestamp
	self.late_completion = late_completion
	self.partition = partition
	if late_completion is not None:
	    self.type_name = 'miss_deadline'
	elif partition is not None:
	    self.type_name = 'wrong_partition'
        elif job.inversion_end is None:
            self.type_name = 'inversion_start'
            job.inversion_start_id = self.id
            job.inversion_start_triggering_event_id = self.triggering_event_id
        else:
            self.type_name = 'inversion_end'
            self.inversion_start_id = job.inversion_start_id
            self.inversion_start_triggering_event_id = job.inversion_start_triggering_event_id

# Returns the position of a Job in a list, or None
def _find_job(record,list):
    for i in range(0,len(list)):
        if list[i].pid == record.pid and list[i].job == record.job:
            return i
    return None

# Return records for any inversion_starts and inversion_ends
def _pedf_check(off,on,when,m,first_event_this_timestamp):

    # List of error records to be returned
    errors = []
    for part in range(m):
    	# List of all jobs that are contending for the CPU (neither complete nor
	# blocked)
	on_cpu = on[part]
	off_cpu = off[part]
	all = []
	for x in on_cpu:
	    if x.is_complete is not True and x.is_blocked is not True:
	        all.append(x)
	for x in off_cpu:
	    if x.is_blocked is not True:
        	all.append(x)
	
	# Sort by on_cpu and then by deadline. sort() is guaranteed to be stable.
	# Thus, this gives us jobs ordered by deadline with preference to those
	# actually running.
	all.sort(key=lambda x: 0 if (x in on_cpu) else 1)
	all.sort(key=lambda x: x.deadline)
	
	# Check if any job is on the wrong partition
	for x in all:
	    if x.partition != task_partition[x.pid]:
		errors.append(Error(x, off_cpu, on_cpu, first_event_this_timestamp, None, task_partition[x.pid]))

	# Check those that actually should be running, to look for priority
	# inversions
	for x in range(0,min(m,len(all))):
	    job = all[x]
	
	    # It's not running and an inversion_start has not been recorded
	    if job not in on_cpu and job.inversion_start is None:
	        job.inversion_start = when
	        errors.append(Error(job, off_cpu, on_cpu,
	        first_event_this_timestamp))
	
	    # It is running and an inversion_start exists (i.e. it it still
	    # marked as being inverted)
	    elif job in on_cpu and job.inversion_start is not None:
	        job.inversion_end = when
	        errors.append(Error(job, off_cpu, on_cpu,
	             first_event_this_timestamp))
                job.inversion_start = None
	        job.inversion_end = None
	
	# Check those that actually should not be running, to record the end of any
	# priority inversions
	for x in range(m,len(all)):
	    job = all[x]
	    if job not in on_cpu and job.inversion_start is not None:
                job.inversion_end = when
	        errors.append(Error(job, off_cpu, on_cpu,
        	        first_event_this_timestamp))
	        job.inversion_start = None
	        job.inversion_end = None
	
	# Look for priority inversions among blocked tasks and end them
	all = filter(lambda x:x.is_blocked and x.inversion_start is not None,
	    on_cpu + off_cpu)
	for job in all:
	    job.inversion_end = when
	    errors.append(Error(job, off_cpu, on_cpu,
	        first_event_this_timestamp))
	    job.inversion_start = None
	    job.inversion_end = None

    return errors
