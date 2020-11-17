###############################################################################
# Description
###############################################################################

# Enforce latest record

###############################################################################
# Public functions
###############################################################################

def latest(stream, latest):
    for record in stream:
        if record.record_type=="event":
            if record.id > latest:
                break
            else:
                yield record
        else:
            yield record
