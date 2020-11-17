###############################################################################
# Description
###############################################################################

# Skip over the given number of records.

###############################################################################
# Public functions
###############################################################################

def skipper(stream, number):
    for record in stream:
        if record.record_type=="event":
            if number > 0:
                number -= 1
            else:
                yield record
                break
        else:
            yield record
    for record in stream:
       yield record
