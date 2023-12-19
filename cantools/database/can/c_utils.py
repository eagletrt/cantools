


type_to_specifier = {"uint8_t": '%" SCNu8 ","  \n\t\t\t"',
                    "uint16_t": '%" SCNu16 "," \n\t\t\t"',
                    "uint32_t": '%" SCNu32 "," \n\t\t\t"',
                    "uint64_t": '%" SCNu64 "," \n\t\t\t"',
                    "int8_t":   '%" SCNi8 ","  \n\t\t\t"',
                    "int16_t":  '%" SCNi16 "," \n\t\t\t"',
                    "int32_t":  '%" SCNi32 "," \n\t\t\t"',
                    "int64_t":  '%" SCNi64 "," \n\t\t\t"',
                    "float":    '%f,"       \n\t\t\t"',
                    "double":   '%f,"       \n\t\t\t"'}

UTILS = '''#ifndef {network}_UTILS_H
#define {network}_UTILS_H

#include <inttypes.h>
#include <string.h>
#include <stdlib.h>

#ifdef __cplusplus
extern "C" {{
#endif

{defines}

{body}

#endif
'''

DEFINE_MSG = '#define {}_{}_string "{}_{}"\n'
DEFINE_SIGNAL = '#define {}_{}_{}_string "{}_{}_{}"\n'

FIELDS_MESSAGE = '''\tcase {}:
\t\tif({} > fields_size) return 1;
{}
\t\treturn 0;
'''
FIELDS_STRING = '''\t\tsnprintf(v[{}], string_size, {});\n'''
FIELDS_FROM_ID = '''int {}_fields_string_from_id(int id, char **v, size_t fields_size, size_t string_size)
{{
	switch(id)
    {{
{}
    }}
    return 0;
}}
'''
N_FIELDS_FROM_ID = '''int {}_n_fields_from_id(int id)
{{
	switch(id)
    {{
{}
    }}
    return 0;
}}
'''

ENUM_FIELDS = '''int {}_enum_fields(int enum_id, char **v, size_t fields_size, size_t string_size)
{{
    switch(enum_id)
    {{
{}
    }}
    return 0;
}}
'''

SERIALIZE = '''int {}_serialize_from_id(int id, char *s, uint8_t *data, size_t *size)
{{
    switch(id)
    {{
{}
    }}
    return 0;
}}
'''
FIELDS_TYPES = '''int {}_fields_types_from_id(int id, int* fields_types, int fields_types_size)
{{
    switch(id)
    {{
{}
    }}
    return 0;
}}
'''
SERIALIZE_MSG = '''\tcase {id}:
\t{{
\t\t{msg_name}_t tmp;
\t\t{msg_name}_converted_t tmp_converted;
{declarations}
\t\tsscanf(s, "{form},
{args});
{assign}
\t\t{msg_name}_conversion_to_raw_struct(&tmp, &tmp_converted);
\t\t*size = {msg_size};
\t\treturn {msg_name}_pack(data, &tmp, {msg_size});
\t}}
'''

def _type_length(signal):
    if signal.length <= 8:
        return 8
    elif signal.length <= 16:
        return 16
    elif signal.length <= 32:
        return 32
    else:
        return 64

def _is_float_conversion(signal):
    return signal.is_float or signal.scale % 1 != 0

def _type_name(signal):
    if _is_float_conversion(signal):
        type_name = 'float'
    else:
        type_name = f'int{_type_length(signal)}_t'

        if not signal.is_signed:
            type_name = 'u' + type_name
    return type_name

def _generate_defines(database_name, messages):
    ret = ''
    for msg in messages.messages:
        ret += "/* START */\n"
        ret += DEFINE_MSG.format(database_name.lower(), msg.name.lower(), database_name.upper(), msg.name.upper()) + "\n"

        for signal in msg.signals:
            ret += DEFINE_SIGNAL.format(database_name.lower(), msg.name.lower(), signal.name.lower(), 
                        database_name.upper(), msg.name.upper(), signal.name.upper())
        ret += "/* END */\n\n"
    
    return ret

def _get_type(signal, msg_name, database_name):
    if signal.choices != None:
        return f'e_{database_name}_{msg_name}_{signal.name}'.lower()
    return f'e_{database_name}_{_type_name(signal)}'

def _generate_enums(database_name, messages):
    types = set()
    enums = set()

    for msg in messages.messages:
        for signal in msg.signals:
            if signal.choices != None:
                enums.add(_get_type(signal, msg.name, database_name))
            else:
                types.add(_get_type(signal, msg.name, database_name))
    
    size = len(types)

    types = '\t'+',\n\t'.join(list(types))
    enums = '\t'+',\n\t'.join(list(enums))

    ind = types.find(',')
    types = types[:ind] + f' = -{size}' + types[ind:]

    return f'enum {database_name}_types_id{{\n{types},\n\n{enums}\n}};\n'

def _generate_enums_fields(database_name, messages):
    enum_id = 0
    body = ""
    for msg in messages.messages:
        for signal in msg.signals:
            if signal.choices != None:
                choices = signal.choices
                tmp = ""
                i = 0
                for c in choices:
                    tmp += f'\t\tsnprintf(v[{i}], string_size, "{database_name}_{msg.name.lower()}_{signal.name.lower()}_{choices[c]}");\n'
                    i += 1
                body += FIELDS_MESSAGE.format(enum_id, len(signal.choices), tmp)

                enum_id += 1
    return ENUM_FIELDS.format(database_name, body)

def _generate_serialize_from_id(database_name, messages):
    ret = ''
    for msg in messages.messages:
        if len(msg.signals) <= 0:
            continue
        form = ''
        args = ''
        assign = ''
        declarations = ''
        msg_name = f'{database_name}_{msg.name.lower()}'
        msg_size = f'{database_name.upper()}_{msg.name.upper()}_BYTE_SIZE'
        for signal in msg.signals:
            declarations += f'\t\t{_type_name(signal)} r_{signal.name.lower()};\n'
            form += type_to_specifier[_type_name(signal)]
            args += f'\t\t\t&r_{signal.name.lower()},\n'
            type = _type_name(signal)
            if signal.choices != None:
                type = f'{msg_name}_{signal.name.lower()}'
            assign += f'\t\ttmp_converted.{signal.name.lower()} = ({type})r_{signal.name.lower()};\n'
        args = args[:-2]
        form = form[:-5]
        ret += SERIALIZE_MSG.format(id=msg.frame_id, msg_name=msg_name, msg_size=msg_size, form=form, args=args, assign=assign, declarations=declarations)
    return SERIALIZE.format(database_name, ret)

def _generate_string_fields_from_id(database_name, messages):
    ret = ''
    for msg in messages.messages:
        if(len(msg.signals) <= 0): continue
        tmp = ''
        for i, signal in enumerate(msg.signals):
            tmp += FIELDS_STRING.format(i, f'{database_name}_{msg.name}_{signal.name}_string'.lower())
        ret += FIELDS_MESSAGE.format(msg.frame_id, len(msg.signals), tmp)
    return FIELDS_FROM_ID.format(database_name, ret)

def _get_n_fields(database_name, messages):
    body = ''
    for msg in messages.messages:
        body += f'\t\tcase {msg.frame_id}: return {len(msg.signals)};\n'
    body = body[:-1]
    return N_FIELDS_FROM_ID.format(database_name, body)

def _fields_types_from_id(database_name, messages):
    body = ''
    for msg in messages.messages:
        if len(msg.signals) == 0:
            continue
        body += f'\tcase {msg.frame_id}:\n'
        body += f'\t\tif(fields_types_size < {len(msg.signals)}) return 0;\n'
        for i, signal in enumerate(msg.signals):
            body += f'\t\tfields_types[{i}] = {_get_type(signal, msg.name, database_name)};\n'
        body += f'\t\treturn {len(msg.signals)};\n'
    return FIELDS_TYPES.format(database_name, body)


def generate_c_utils(database_name, messages):
    header = f'#ifndef {database_name.upper()}_UTILS_C_H\n\n#define {database_name.upper()}_UTILS_C_H\n\n'
    header += f'#include <stddef.h>\n#include "{database_name}_network.h"\n\n'
    header += _generate_defines(database_name, messages) + _generate_enums(database_name, messages)
    header += f'int {database_name}_fields_string_from_id(int id, char **v, size_t fields_size, size_t string_size);\n'
    header += f'int {database_name}_enum_fields(int enum_id, char **v, size_t fields_size, size_t string_size);\n'
    header += f'int {database_name}_serialize_from_id(int id, char *s, uint8_t *data, size_t *size);\n'
    header += f'int {database_name}_n_fields_from_id(int id);\n'
    header += f'int {database_name}_fields_types_from_id(int id, int* fields_types, int fields_types_size);\n'
    header += '\n\n#endif'
    implementation = f'#include "{database_name}_utils_c.h"\n\n\n'
    implementation += _generate_string_fields_from_id(database_name, messages)
    implementation += _generate_enums_fields(database_name, messages)
    implementation += _generate_serialize_from_id(database_name, messages)
    implementation += _get_n_fields(database_name, messages)
    implementation += _fields_types_from_id(database_name, messages)

    return header, implementation


