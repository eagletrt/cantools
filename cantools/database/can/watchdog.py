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

INTERVAL_FROM_ID = '''
static int primary_watchdog_interval_from_id(uint16_t message_id) {{
    switch (message_id) {{
{messages}
    }}
    return -1;
}}'''

def _interval_name(database_name, msg_name):
    return f'{database_name}_INTERVAL_{msg_name}'

def _generate_intervals(messages, database_name):
    ret = ''
    for msg in messages:
        if msg.cycle_time is not None:
            ret += f'#define {_interval_name(database_name, msg.name.upper())} {msg.cycle_time}\n'
    return ret

def _generate_intervals_from_id(messages, database_name):
    tmp = ''
    for msg in messages:
        if msg.cycle_time is not None:
            tmp += f'       case {msg.frame_id}: return {_interval_name(database_name, msg.name.upper())};\n'
    return INTERVAL_FROM_ID.format(messages=tmp)

def generate_watchdog(database, database_name):
    messages = database.messages
    body = _generate_intervals(messages, database_name) + _generate_intervals_from_id(messages, database_name)
    return WATCHDOG.format(body=body)
    