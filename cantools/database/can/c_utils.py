


type_to_specifier = {"uint8_t": '%" PRIu8  \n\t\t\t"',
                    "uint16_t": '%" PRIu16 \n\t\t\t"',
                    "uint32_t": '%" PRIu32 \n\t\t\t"',
                    "uint64_t": '%" PRIu64 \n\t\t\t"',
                    "int8_t":   '%" PRIi8  \n\t\t\t"',
                    "int16_t":  '%" PRIi16 \n\t\t\t"',
                    "int32_t":  '%" PRIi32 \n\t\t\t"',
                    "int64_t":  '%" PRIi64 \n\t\t\t"',
                    "float": '""%f"\n\t\t\t"',
                    "double": '""%f"\n\t\t\t"'}

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

ENUM_FIELDS = '''int {}_enum_fields(int enum_id, char **v, size_t fields_size, size_t string_size)
{{
    switch(enum_id)
    {{
{}
    }}
    return 0;
}}
'''

SERIALIZE = '''int {}_serialize_from_id(int id, char *s, uint8_t *data, size_t size)
{{
    switch(id)
    {{
{}
    }}
    return 0;
}}'''
SERIALIZE_MSG = '''\tcase {id}:
\t{{
\t\t{msg_name}_t tmp;
\t\t{msg_name}_converted_t tmp_converted;
\t\tsscanf(s, "{form}",
{args});
\t\t{msg_name}_conversion_to_raw_struct(&tmp, &tmp_converted);
\t\treturn {msg_name}_pack(data, &tmp, size);
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
        if signal.length == 32:
            type_name = 'float'
        else:
            type_name = 'double'
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

def _generate_enums(database_name, messages):
    types = set()
    enums = set()

    for msg in messages.messages:
        for signal in msg.signals:
            if signal.choices != None:
                enums.add(f'e_{database_name}_{msg.name}_{signal.name}'.lower())
            else:
                types.add('e_'+_type_name(signal))
    
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
        msg_name = f'{database_name}_{msg.name.lower()}'
        for signal in msg.signals:
            form += type_to_specifier[_type_name(signal)]
            args += f'\t\t\ttmp.{signal.name.lower()},\n'
        args = args[:-2]
        ret += SERIALIZE_MSG.format(id=msg.frame_id, msg_name=msg_name, form=form, args=args)
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


def generate_c_utils(database_name, messages):
    header = f'#ifndef {database_name.upper()}_UTILS_C_H\n\n#define {database_name.upper()}_UTILS_C_H\n\n'
    header += f'#include <cstddef>\n#include "{database_name}_network.h"\n\n'
    header += _generate_defines(database_name, messages) + _generate_enums(database_name, messages)
    header += f'int {database_name}_fields_string_from_id(int id, char **v, size_t fields_size, size_t string_size);\n'
    header += f'int {database_name}_enum_fields(int enum_id, char **v, size_t fields_size, size_t string_size);\n'
    header += f'int {database_name}_serialize_from_id(int id, char *s, uint8_t *data, size_t size);\n'
    header += '\n\n#endif'
    implementation = f'#include "{database_name}_utils_c.h"\n\n\n'
    implementation += _generate_string_fields_from_id(database_name, messages)
    implementation += _generate_enums_fields(database_name, messages)
    implementation += _generate_serialize_from_id(database_name, messages)

    return header, implementation


