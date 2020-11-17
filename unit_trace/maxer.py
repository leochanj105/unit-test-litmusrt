###############################################################################
# Description
###############################################################################

# Parse at most the given number of records

###############################################################################
# Public functions
###############################################################################

def maxer(stream, number):
    for record in stream:
        if record.record_type=="event":
            if number > 0:
                number -= 1
                yield record
            else:
                break
        else:
            yield record
