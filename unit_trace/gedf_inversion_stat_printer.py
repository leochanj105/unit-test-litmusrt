###############################################################################
# Description
###############################################################################
# Compute and print G-EDF inversion statistics


###############################################################################
# Public Functions
###############################################################################

def gedf_inversion_stat_printer(stream,num):

    # State
    min_inversion = -1
    max_inversion = -1
    sum_inversions = 0
    num_inversions = 0
    longest_inversions = []

    # Iterate over records, updating state
    for record in stream:
        if record.type_name == 'inversion_end':
            length = record.job.inversion_end - record.job.inversion_start
            if length > 0:
                num_inversions += 1
                if length > max_inversion:
                    max_inversion = length
                if length < min_inversion or min_inversion == -1:
                    min_inversion = length
                sum_inversions += length
                if len(longest_inversions) == num:
                    if num==0:
                        continue
                    si = longest_inversions[0]
                    if length > (si.job.inversion_end -
                        si.job.inversion_start):
                        longest_inversions.append(record)
                        longest_inversions = _sort_longest_inversions(
                            longest_inversions)
                        del longest_inversions[0]
                else:
                    longest_inversions.append(record)
                    longest_inversions = _sort_longest_inversions(
                        longest_inversions)

    # We've seen all records.
    # Further update state
    if num_inversions > 0:
        avg_inversion = int(sum_inversions / num_inversions)
    else:
        avg_inversion = 0

    # Print out our information
    # NOTE: Here, we assume nanoseconds as the time unit.
    # May have to be changed in the future.
    print "Num inversions: %d" % (num_inversions)
    print "Min inversion: %f ms" % (float(min_inversion) / 1000000)
    print "Max inversion: %f ms" % (float(max_inversion) / 1000000)
    print "Avg inversion: %f ms" % (float(avg_inversion) / 1000000)
    for inv in longest_inversions:
        print ""
        print "Inversion record IDs: (%d, %d)" % (inv.inversion_start_id,
            inv.id)
        print("Triggering Event IDs: (%d, %d)" %
            (inv.inversion_start_triggering_event_id,
            inv.triggering_event_id))
        print "Time: %d" % (inv.job.inversion_end)
        # NOTE: Here, we assume nanoseconds as the time unit.
        # May have to be changed in the future.
        print "Duration: %f ms" % (
            float(inv.job.inversion_end - inv.job.inversion_start) / 1000000)
        print "Job: %d.%d" % (inv.job.pid,inv.job.job)
        print "Deadline: %d" % (inv.job.deadline)
        print ""


def _sort_longest_inversions(longest_inversions):
    """ Sort longest inversions"""
    def sortkey(x):
        return x.job.inversion_end - x.job.inversion_start
    longest_inversions.sort(key=sortkey)
    return longest_inversions
