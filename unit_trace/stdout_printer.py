###############################################################################
# Description
###############################################################################

# Prints records to standard out

###############################################################################
# Public functions
###############################################################################

def stdout_printer(stream):
    for record in stream:
        if record.record_type == "event":
            _print_event(record)
        elif record.record_type == "meta" and record.type_name == "stats":
            _print_stats(record)
        elif record.record_type == "error" and record.type_name == 'inversion_start':
            _print_inversion_start(record)
        elif record.record_type == "error" and record.type_name == 'inversion_end':
            _print_inversion_end(record)
	elif record.record_type == "error" and record.type_name == 'miss_deadline':
	    _print_miss_deadline(record)
        else:
            continue
        print ""

###############################################################################
# Private functions
###############################################################################

def _print_event(record):
    print "Event ID: %d" % (record.id)
    print "Job: %d.%d" % (record.pid,record.job)
    print "Type: %s" % (record.type_name)
    print "Time: %d" % (record.when)
    print "CPU: %d" % (record.cpu)

def _print_inversion_start(record):
    print "Type: %s" % ("Inversion start")
    print "Inversion Record IDs: (%d, U)" % (record.id)
    print "Triggering Event IDs: (%d, U)" % (record.triggering_event_id)
    print "Time: %d" % (record.job.inversion_start)
    print "Job: %d.%d" % (record.job.pid,record.job.job)
    print "Deadline: %d" % (record.job.deadline)
    print "Off CPU: ",
    for job in record.off_cpu:
        print str(job) + " ",
    print
    print "On CPU: ",
    for job in record.on_cpu:
        print str(job) + " ",
    print #newline

def _print_inversion_end(record):
    print "Type: %s" % ("Inversion end")
    print "Inversion record IDs: (%d, %d)" % (record.inversion_start_id,
        record.id)
    print("Triggering Event IDs: (%d, %d)" %
        (record.inversion_start_triggering_event_id,
        record.triggering_event_id))
    print "Time: %d" % (record.job.inversion_end)
    # NOTE: Here, we assume nanoseconds as the time unit.
    # May have to be changed in the future.
    print "Duration: %f ms" % (
        float(record.job.inversion_end - record.job.inversion_start)/1000000)
    print "Job: %d.%d" % (record.job.pid,record.job.job)
    print "Deadline: %d" % (record.job.deadline)
    print "Off CPU: ",
    for job in record.off_cpu:
        print str(job) + " ",
    print
    print "On CPU: ",
    for job in record.on_cpu:
        print str(job) + " ",
    print #newline
def _print_miss_deadline(record):
    print "Type: %s" % ("Miss deadline")
    print "Job: %d.%d" % (record.job.pid, record.job.job)
    print("Deadline: %d" % (record.job.deadline))
    print("Completion time: %d" % (record.late_completion))
