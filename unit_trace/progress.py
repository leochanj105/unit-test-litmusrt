###############################################################################
# Description
###############################################################################

# Display progress information:
# - Total number of bytes in trace files
# - Total number of event records in trace files
# - Message for every 1,000 records processed
# - Total records processed
# - Total elapsed time

###############################################################################
# Imports
###############################################################################

import time
import sys
import os

###############################################################################
# Public functions
###############################################################################

def progress(stream):

    start_time = 0
    count = 0

    for record in stream:
        if record.record_type=="event":
            count += 1
        if (count % 1000) == 0 and count > 0:
            sys.stderr.write(("Parsed %d event records\n") % (count))
        if record.record_type=="meta" and record.type_name=="trace_files":
            bytes = 0
            for file in record.files:
                bytes += int(os.path.getsize(file))
            sys.stderr.write(("Total bytes  : %d\n") % (bytes))
            # 192 bits per event record, 8 bits per byte
            sys.stderr.write(("Total records: %d\n") % (bytes * 8 / 192))
            start_time = time.time()
        yield record

    sys.stderr.write(("Total records processed: %d\n") % (count))
    sys.stderr.write(("Time elapsed: %ds\n") % (time.time() - start_time))

