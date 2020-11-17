###############################################################################
# Description
###############################################################################

# Display any warnings

###############################################################################
# Imports
###############################################################################

import sys

###############################################################################
# Public functions
###############################################################################

def warning_printer(stream):
    out_of_order_ids = []
    for record in stream:
        if (record.record_type == "meta" and
            record.type_name == "out_of_order_warning"):
            out_of_order_ids.append(record.id)
    if len(out_of_order_ids) > 0:
        sys.stderr.write(
            "WARNING: The following {0} records were out of order:\n{1}\n".format(
            len(out_of_order_ids), out_of_order_ids))
