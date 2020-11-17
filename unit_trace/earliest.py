###############################################################################
# Description
###############################################################################

# Enforce earliest record

###############################################################################
# Public functions
###############################################################################

def earliest(stream, earliest):
    for record in stream:
        if record.record_type=="event":
            if record.id < earliest:
                pass
            else:
                yield record
                break
        else:
            yield record
    for record in stream:
        yield record
