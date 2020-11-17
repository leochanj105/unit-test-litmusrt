#!/usr/bin/env python
from schedule import *

"""Class that interprets the raw trace data, outputting it
to a Python schedule object.

Doesn't do any checking on the logic of the schedule (except to
check for corrupted data)"""

def get_type(type_num):
    """Return the binary data type, given the type_num"""
    return Trace.DATA_TYPES[type_num]

def get_type_num(type):
    nums = dict(zip(Trace.DATA_TYPES, range(0, 11)))
    return nums[type]

def _get_job_from_record(sched, record):
    if record.pid == 0:
        return None
    else:
        tname = _pid_to_task_name(record.pid)
        job_no = record.job
        if tname not in sched.get_tasks():
            sched.add_task(Task(tname, []))
        if job_no not in sched.get_tasks()[tname].get_jobs():
            sched.get_tasks()[tname].add_job(Job(job_no, []))
        job = sched.get_tasks()[tname].get_jobs()[job_no]
        return job

def convert_trace_to_schedule(stream):
    """The main function of interest in this module. Coverts a stream of records
    to a Schedule object."""
    def noop():
        pass

    num_cpus, stream = _find_num_cpus(stream)
    sched = Schedule('sched', num_cpus)
    for record in stream:
        #if record.record_type == 'meta':
        #    if record.type_name == 'num_cpus':
        #        sched = Schedule('sched', record.num_cpus)
        #    continue
        if record.record_type == 'event':
            job = _get_job_from_record(sched, record)
            cpu = record.cpu

            if not hasattr(record, 'deadline'):
                record.deadline = None

            # This whole method should be refactored for this posibility
            if job is None:
                if record.type_name == "action":
                    event = ActionEvent(record.when, cpu, record.action)
                    event.set_schedule(sched)
                    sched.add_jobless(event)
                continue

            actions = {
                'name' : (noop),
                'params' : (noop),
                'release' : (lambda :
                (job.add_event(ReleaseEvent(record.when, cpu)),
                 job.add_event(DeadlineEvent(record.deadline, cpu)))),
                'switch_to' : (lambda :
                job.add_event(SwitchToEvent(record.when, cpu))),
                'switch_away' : (lambda :
                job.add_event(SwitchAwayEvent(record.when, cpu))),
                'assign' : (noop),
                'completion' : (lambda :
                job.add_event(CompleteEvent(record.when, cpu))),
                'block' : (lambda :
                job.add_event(SuspendEvent(record.when, cpu))),
                'resume' : (lambda :
                job.add_event(ResumeEvent(record.when, cpu))),
                'action' : (lambda :
                job.add_event(ActionEvent(record.when, cpu, record.action))),
                'sys_release' : (noop)
            }

            actions[record.type_name]()

        elif record.record_type == 'error':
            job = _get_job_from_record(sched, record.job)

            actions = {
                'inversion_start' : (lambda :
                job.add_event(InversionStartEvent(record.job.inversion_start))),
                'inversion_end' : (lambda :
                job.add_event(InversionEndEvent(record.job.inversion_end)))
            }

            actions[record.type_name]()

    return sched

def _pid_to_task_name(pid):
    """Converts a PID to an appropriate name for a task."""
    return str(pid)

def _find_num_cpus(stream):
    """Determines the number of CPUs used by scanning the binary format."""
    max = 0
    stream_list = []
    for record in stream:
        stream_list.append(record)
        if record.record_type == 'event':
            if record.cpu > max:
                max = record.cpu

    def recycle(l):
        for record in l:
            yield record
    return (max + 1, recycle(stream_list))
