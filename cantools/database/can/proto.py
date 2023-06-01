import re
import time
from decimal import Decimal

from ...version import __version__

PROTO = '''syntax = "proto3";
package {db_name};


{enum_body}

{messages_body}

{pack_body}
'''

def is_float_conversion(signal):
    return signal.is_float or signal.scale % 1 != 0

def type_name(database_name, message_name, signal):
    if signal.choices is not None:
        return f"{database_name}_{message_name}_{signal.name}".lower()
    if is_float_conversion(signal):
        if signal.length == 32:
            type_name = 'float'
        else:
            type_name = 'double'
    else:
        if signal.length == 1:
            return 'bool'
        type_name = f'int{32 if signal.length <= 32 else 64}'

        if not signal.is_signed:
            type_name = 'u' + type_name

    return type_name

def _generate_enums(database_name, messages):
    s = {}
    for msg in messages:
        for signal in msg.signals:
            if signal.choices is not None:
                s[f"{database_name}_{msg.name}_{signal.name}".lower()] = signal.choices
    ret = ""

    for enum in s:
        ret += "enum " + enum + " {\n"
        for choice in s[enum]:
            ret += f"\t{enum}_{s[enum][choice]} = {choice};\n"
        ret += "}\n"
    return ret

def _generate_messages(database_name, messages):
    ret = ""
    for msg in messages:
        ret += f"message {msg.name}{{\n"
        i = 1
        for signal in msg.signals:
            ret += "\t"
            ret += f"{type_name(database_name, msg.name, signal)} {signal.name} = {i};\n"
            i += 1
        ret += f"\tuint64 _inner_timestamp = {i};\n"
        ret += "}\n"
    return ret

def _generate_pack(database_name, messages):
    ret = "message Pack{\n"
    for i, msg in enumerate(messages):
        ret += f"\trepeated {msg.name} {msg.name} = {i+1};\n"
    ret += "}\n"
    return ret

def generate_proto(database, database_name):
    messages = database.messages
    enums = _generate_enums(database_name, messages)
    msgs = _generate_messages(database_name, messages)
    pack = _generate_pack(database_name, messages)
    return PROTO.format(db_name=database_name, enum_body=enums, messages_body=msgs, pack_body=pack)