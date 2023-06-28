import re
import time
from decimal import Decimal

from ...version import __version__

WATCHDOG = '''#ifndef {network}_WATCHDOG_H
#define {network}_WATCHDOG_H

#include <inttypes.h>

#ifdef __cplusplus
extern "C" {{
#endif

#ifndef CANLIB_WATCHDOG_TIMESTAMP_TYPE
#define CANLIB_WATCHDOG_TIMESTAMP_TYPE
typedef uint32_t canlib_watchdog_timestamp;
#endif // CANLIB_WATCHDOG_TIMESTAMP_TYPE

#ifndef CANLIB_MESSAGE_ID_TYPE
#define CANLIB_MESSAGE_ID_TYPE
typedef uint16_t canlib_message_id;
#endif // CANLIB_MESSAGE_ID_TYPE

#ifndef CANLIB_WATCHDOG_CALLBACK
#define CANLIB_WATCHDOG_CALLBACK
typedef void (*canlib_watchdog_callback)(int);
#endif // CANLIB_WATCHDOG_CALLBACK

#ifndef CANLIB_BITMASK_UTILS
#define CANLIB_BITMASK_UTILS

#define CANLIB_BITMASK_TYPE uint8_t
#define CANLIB_BITMASK_TYPE_BITS 8

#define CANLIB_BITMASK_ARRAY(b) (1 << ((b) % CANLIB_BITMASK_TYPE_BITS))
#define CANLIB_BITSLOT_ARRAY(b) ((b) / CANLIB_BITMASK_TYPE_BITS)
#define CANLIB_BITSET_ARRAY(a, b) ((a)[CANLIB_BITSLOT_ARRAY(b)] |= CANLIB_BITMASK_ARRAY(b))
#define CANLIB_BITCLEAR_ARRAY(a, b) ((a)[CANLIB_BITSLOT_ARRAY(b)] &= ~CANLIB_BITMASK_ARRAY(b))
#define CANLIB_BITTEST_ARRAY(a, b) ((a)[CANLIB_BITSLOT_ARRAY(b)] & CANLIB_BITMASK_ARRAY(b))
#define CANLIB_BITNSLOTS_ARRAY(nb) ((nb + CANLIB_BITMASK_TYPE_BITS - 1) / CANLIB_BITMASK_TYPE_BITS)

#define CANLIB_BITMASK(b) (1 << (b))
#define CANLIB_BITSET(a, b) ((a) |= CANLIB_BITMASK(b))
#define CANLIB_BITCLEAR(a, b) ((a) &= ~CANLIB_BITMASK(b))
#define CANLIB_BITTEST(a, b) ((a) & CANLIB_BITMASK(b))

#endif // CANLIB_BITMASK_UTILS

#ifndef CANLIB_UNUSED
#define CANLIB_UNUSED(expr) do {{ (void)(expr); }} while (0)
#endif // CANLIB_UNUSED

#ifndef CANLIB_INTERVAL_THRESHOLD
#define CANLIB_INTERVAL_THRESHOLD 500
#endif // CANLIB_INTERVAL_THRESHOLD

{body}


#ifdef __cplusplus
}}
#endif

#endif // {network}_NETWORK_H
'''

INTERVAL_FROM_ID = '''
static int {network}_watchdog_interval_from_id(uint16_t message_id) {{
    switch (message_id) {{
{messages}
    }}
    return -1;
}}
'''
INDEX_FROM_ID = '''
static int {network}_watchdog_index_from_id(uint16_t message_id) {{
    switch (message_id) {{
{messages}
    }}
    return -1;
}}
'''

WATCHDOG_DEFINITION = '''
typedef struct {{
    uint8_t activated[{msg_byte_count}];
    uint8_t timeout[{msg_byte_count}];
    canlib_watchdog_timestamp last_reset[{msg_count}];
}} {network}_watchdog;


{network}_watchdog* {network}_watchdog_new();
void {network}_watchdog_free({network}_watchdog *watchdog);
void {network}_watchdog_reset({network}_watchdog *watchdog, canlib_message_id id, canlib_watchdog_timestamp timestamp);
void {network}_watchdog_reset_all({network}_watchdog *watchdog, canlib_watchdog_timestamp timestamp);
void {network}_watchdog_timeout({network}_watchdog *watchdog, canlib_watchdog_timestamp timestamp);
'''

WATCHDOG_NEW = '''
{network}_watchdog* {network}_watchdog_new() {{
    {network}_watchdog *watchdog = ({network}_watchdog*)malloc(sizeof({network}_watchdog));
    if (watchdog == NULL) {{
        return NULL;
    }}
    memset(watchdog->activated, 0, sizeof(watchdog->activated));
    memset(watchdog->timeout, 0, sizeof(watchdog->timeout));
    memset(watchdog->last_reset, 0, sizeof(watchdog->last_reset));
    return watchdog;
}}
'''

WATCHDOG_FREE = '''
void {network}_watchdog_free({network}_watchdog *watchdog) {{
    free(watchdog);
}}
'''
WATCHDOG_RESET = '''
void {network}_watchdog_reset({network}_watchdog *watchdog, canlib_message_id id, canlib_watchdog_timestamp timestamp) {{
    int index = {network}_watchdog_index_from_id(id);
    if (index < {msg_count} && CANLIB_BITTEST_ARRAY(watchdog->activated, index)) {{
        CANLIB_BITCLEAR_ARRAY(watchdog->timeout, index);
        watchdog->last_reset[index] = timestamp;
    }}
}}
'''
WATCHDOG_RESET_ALL = '''
void {network}_watchdog_reset_all({network}_watchdog *watchdog, canlib_watchdog_timestamp timestamp) {{
    memset(watchdog->timeout, 0, sizeof(watchdog->timeout));
    memset(watchdog->last_reset, timestamp, sizeof(watchdog->last_reset));
}}'''

WATCHDOG_TIMEOUT = '''
void {network}_watchdog_timeout({network}_watchdog *watchdog, canlib_watchdog_timestamp timestamp) {{
{body}
}}
'''
MESSAGE_TIMEOUT = '''
    if (
        CANLIB_BITTEST_ARRAY(watchdog->activated, {index})
        && timestamp - watchdog->last_reset[{index}] > {interval} * 3
    ) {{
        CANLIB_BITSET_ARRAY(watchdog->timeout, {index});
    }}
'''

def _get_name(database_name, msg_name, type):
    return f'{database_name}_{type}_{msg_name}'

def _interval_name(database_name, msg_name):
    return _get_name(database_name, msg_name, 'INTERVAL').upper()
def _index_name(database_name, msg_name):
    return _get_name(database_name, msg_name, 'INDEX').upper()

def _generate_intervals(database_name, messages):
    intervals = ''
    indexes = ''
    for i, msg in enumerate(messages):
        if msg.cycle_time is not None:
            intervals += f'#define {_interval_name(database_name, msg.name)} {msg.cycle_time}\n'
        indexes += f'#define {_index_name(database_name, msg.name)} {i}\n'
    return intervals + "\n\n" + indexes + "\n\n"

def _generate_intervals_from_id(database_name, messages):
    tmp = ''
    for msg in messages:
        if msg.cycle_time is not None:
            tmp += f'       case {msg.frame_id}: return {_interval_name(database_name, msg.name)};\n'
    return INTERVAL_FROM_ID.format(messages=tmp, network=database_name)

def _generate_index_from_id(database_name, messages):
    tmp = ''
    for msg in messages:
        tmp += f'       case {msg.frame_id}: return {_index_name(database_name, msg.name)};\n'
    return INDEX_FROM_ID.format(messages=tmp, network=database_name)

def _generate_timeouts(database_name, messages):
    timeouts = ''
    for msg in messages:
        if msg.cycle_time is not None:
            timeouts += MESSAGE_TIMEOUT.format(index=_index_name(database_name, msg.name),
                                            interval=_interval_name(database_name, msg.name))
    return WATCHDOG_TIMEOUT.format(network=database_name, body=timeouts)
    

def generate_watchdog(database, database_name):
    messages = database.messages
    body = _generate_intervals(database_name, messages)
    body += WATCHDOG_DEFINITION.format(network=database_name,
                                    msg_count=len(messages),
                                    msg_byte_count=(len(messages)+7)//8)
    body += _generate_intervals_from_id(database_name, messages)
    body += _generate_index_from_id(database_name, messages)
    body += '#ifdef primary_WATCHDOG_IMPLEMENTATION\n'
    body += WATCHDOG_NEW.format(network=database_name)
    body += WATCHDOG_FREE.format(network=database_name)
    body += WATCHDOG_RESET.format(network=database_name, msg_count=len(messages))
    body += WATCHDOG_RESET_ALL.format(network=database_name)
    body += _generate_timeouts(database_name, messages)
    body += '#endif // primary_WATCHDOG_IMPLEMENTATION\n'
    return WATCHDOG.format(body=body, network=database_name)
    