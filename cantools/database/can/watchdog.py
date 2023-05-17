import re
import time
from decimal import Decimal

from ...version import __version__

WATCHDOG = '''#ifndef primary_WATCHDOG_H
#define primary_WATCHDOG_H

#ifdef __cplusplus
extern "C" {{
#endif

{body}


#ifdef __cplusplus
}}
#endif

#endif // primary_NETWORK_H
'''

def _generate_intervals(messages, database_name):
    ret = ''
    for msg in messages:
        if msg.cycle_time is not None:
            ret += f'#define {database_name}_INTERVAL_{msg.name.upper()} {msg.cycle_time}\n'
    return ret

def generate_watchdog(database, database_name):
    messages = database.messages
    return WATCHDOG.format(body=_generate_intervals(messages, database_name))
    