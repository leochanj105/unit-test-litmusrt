###############################################################################
# Description
###############################################################################

# Sanitize input. (There are a number of goofy issues with the sched_trace
# output.)

###############################################################################
# Public functions
###############################################################################

def sanitizer(stream):

    job_2s_released = [] # list of tasks which have released their job 2s
    jobs_switched_to = []

    released = False

    for record in stream:

        # Ignore records which are not events (e.g. the num_cpus record)
        if record.record_type != 'event':
            yield record
            continue

        if record.type_name == 'release':
            released = released or True

        if record.type_name == 'action' and released:
            yield record
            continue

        # All records with job < 2 are garbage
        if record.job < 2:
            continue

        # Some records with job == 2 are garbage
        if record.job==2:

            # There is a duplicate release of every job 2
            # This will throw away the second one
            if record.type_name == 'release':
                if record.pid in job_2s_released:
                    continue
                else:
                    job_2s_released.append(record.pid)

            # Job 2 has a resume that is garbage
            if record.type_name == 'resume':
                continue

        # By default, the switch_away for a job (after it has completed)
        # is maked as being for job+1, which has never been switched to.
        # We can correct this if we note which jobs really
        # have been switched to.
        if record.type_name == 'switch_to':
            jobs_switched_to.append((record.pid,record.job))
        if record.type_name == 'switch_away':
            if (record.pid,record.job) not in jobs_switched_to:
                record.job -= 1


        yield record
