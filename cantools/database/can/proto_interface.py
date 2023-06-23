import re
import time
from decimal import Decimal
from typing import List

from ...version import __version__

class Signal:

    def __init__(self, signal, message_name, database_name):
        self.database_name = database_name
        self.message_name = message_name
        self._signal = signal
        self.snake_name = camel_to_snake_case(self.name)

    def __getattr__(self, name):
        return getattr(self._signal, name)

    @property
    def is_bool(self):
        return self._signal.is_bool

    @property
    def unit(self):
        return _get(self._signal.unit, '-')
    
    @property
    def is_enum(self):
        return self._signal.choices != None

    @property
    def type_length(self):
        if self.length <= 8:
            return 8
        elif self.length <= 16:
            return 16
        elif self.length <= 32:
            return 32
        else:
            return 64

    @property
    def type_name(self):
        if self.is_float:
            if self.length == 32:
                type_name = 'float'
            else:
                type_name = 'double'
        else:
            type_name = f'int{self.type_length}_t'

            if not self.is_signed:
                type_name = 'u' + type_name

        return type_name

    @property
    def enum_name(self):
        return f'{self.database_name}_{self.message_name}_{self.snake_name}'

    @property
    def type_suffix(self):
        try:
            return {
                'uint8_t': 'u',
                'uint16_t': 'u',
                'uint32_t': 'u',
                'int64_t': 'll',
                'uint64_t': 'ull',
                'float': 'f'
            }[self.type_name]
        except KeyError:
            return ''

    @property
    def conversion_type_suffix(self):
        try:
            return {
                8: 'u',
                16: 'u',
                32: 'u',
                64: 'ull'
            }[self.type_length]
        except KeyError:
            return ''

    @property
    def is_float_conversion(self):
        return self.is_float or _get(self.scale, '-') % 1 != 0 or self.minimum_value % 1 != 0 or self.maximum_value % 1 != 0

    @property
    def minimum_type_value(self):
        if self.type_name == 'int8_t':
            return -128
        elif self.type_name == 'int16_t':
            return -32768
        elif self.type_name == 'int32_t':
            return -2147483648
        elif self.type_name == 'int64_t':
            return -9223372036854775808
        elif self.type_name[0] == 'u':
            return 0
        else:
            return None

    @property
    def maximum_type_value(self):
        if self.type_name == 'int8_t':
            return 127
        elif self.type_name == 'int16_t':
            return 32767
        elif self.type_name == 'int32_t':
            return 2147483647
        elif self.type_name == 'int64_t':
            return 9223372036854775807
        elif self.type_name == 'uint8_t':
            return 255
        elif self.type_name == 'uint16_t':
            return 65535
        elif self.type_name == 'uint32_t':
            return 4294967295
        elif self.type_name == 'uint64_t':
            return 18446744073709551615
        else:
            return None

    @property
    def minimum_value(self):
        if self.is_float:
            return None
        elif self.is_signed:
            return -(2 ** (self.length - 1))
        else:
            return 0

    @property
    def maximum_value(self):
        if self.is_float:
            return None
        elif self.is_signed:
            return ((2 ** (self.length - 1)) - 1)
        else:
            return ((2 ** self.length) - 1)

    def segments(self, invert_shift):
        index, pos = divmod(self.start, 8)
        left = self.length

        while left > 0:
            if self.byte_order == 'big_endian':
                if left >= (pos + 1):
                    length = (pos + 1)
                    pos = 7
                    shift = -(left - length)
                    mask = ((1 << length) - 1)
                else:
                    length = left
                    shift = (pos - length + 1)
                    mask = ((1 << length) - 1)
                    mask <<= (pos - length + 1)
            else:
                shift = (left - self.length) + pos

                if left >= (8 - pos):
                    length = (8 - pos)
                    mask = ((1 << length) - 1)
                    mask <<= pos
                    pos = 0
                else:
                    length = left
                    mask = ((1 << length) - 1)
                    mask <<= pos

            if invert_shift:
                if shift < 0:
                    shift = -shift
                    shift_direction = 'left'
                else:
                    shift_direction = 'right'
            else:
                if shift < 0:
                    shift = -shift
                    shift_direction = 'right'
                else:
                    shift_direction = 'left'

            yield index, shift, shift_direction, mask

            left -= length
            index += 1
class Message:
    def __init__(self, message, database_name):
        self._message = message
        self.snake_name = camel_to_snake_case(self.name)
        self.signals = [Signal(signal, self.snake_name, database_name)for signal in message.signals]
        self.has_conversions = False
        for sig in self.signals:
            if sig.is_float_conversion:
                self.has_conversions = True
                break

    def __getattr__(self, name):
        return getattr(self._message, name)

    def get_signal_by_name(self, name):
        for signal in self.signals:
            if signal.name == name:
                return signal
def camel_to_snake_case(value):
    return value.lower()
    value = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', value)
    value = re.sub(r'(_+)', '_', value)
    value = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', value).lower()
    value = re.sub(r'[^a-zA-Z0-9]', '_', value)
    return value


CIRCULAR_BUFFER = '''
#ifndef CANLIB_CIRCULAR_BUFFER
#define CANLIB_CIRCULAR_BUFFER
namespace Helper {
template <bool FITS8, bool FITS16>
struct Index {
  using Type = uint32_t;
};

template <>
struct Index<false, true> {
  using Type = uint16_t;
};

template <>
struct Index<true, true> {
  using Type = uint8_t;
};
}  // namespace Helper

template <typename T, size_t S,
          typename IT =
              typename Helper::Index<(S <= UINT8_MAX), (S <= UINT16_MAX)>::Type>
class canlib_circular_buffer {
 public:
  static constexpr IT capacity = static_cast<IT>(S);

  using index_t = IT;

  constexpr canlib_circular_buffer();
  canlib_circular_buffer(const canlib_circular_buffer &) = delete;
  canlib_circular_buffer(canlib_circular_buffer &&) = delete;
  canlib_circular_buffer &operator=(const canlib_circular_buffer &) = delete;
  canlib_circular_buffer &operator=(canlib_circular_buffer &&) = delete;

  bool unshift(T value);
  bool push(T value);
  T shift();
  T pop();
  const T& start() const;
  T inline first() const;
  T inline last() const;
  const T& operator[](IT index) const;
  IT inline size() const;
  IT inline available() const;
  bool inline empty() const;
  bool inline full() const;
  void inline clear();
  size_t inline offset() const;


 private:
  T buffer[S];
  T *head;
  T *tail;
  size_t _offset;
#ifndef CIRCULAR_BUFFER_INT_SAFE
  IT count;
#else
  volatile IT count;
#endif
};

template <typename T, size_t S, typename IT>
constexpr canlib_circular_buffer<T, S, IT>::canlib_circular_buffer()
    : head(buffer), tail(buffer), count(0), _offset(0) {}

template <typename T, size_t S, typename IT>
bool canlib_circular_buffer<T, S, IT>::unshift(T value) {
  if (head == buffer) {
    head = buffer + capacity;
  }
  *--head = value;
  if (count == capacity) {
    if (tail-- == buffer) {
      tail = buffer + capacity - 1;
    }
    return false;
  } else {
    if (count++ == 0) {
      tail = head;
    }
    return true;
  }
}

template <typename T, size_t S, typename IT>
bool canlib_circular_buffer<T, S, IT>::push(T value) {
  if (++tail == buffer + capacity) {
    tail = buffer;
  }
  *tail = value;
  if (count == capacity) {
    if (++head == buffer + capacity) {
      head = buffer;
    }
    _offset = (_offset + 1) % capacity;
    return false;
  } else {
    if (count++ == 0) {
      head = tail;
    }
    return true;
  }
}

template <typename T, size_t S, typename IT>
T canlib_circular_buffer<T, S, IT>::shift() {
  if (count == 0) return *head;
  T result = *head++;
  if (head >= buffer + capacity) {
    head = buffer;
  }
  count--;
  return result;
}

template <typename T, size_t S, typename IT>
T canlib_circular_buffer<T, S, IT>::pop() {
  if (count == 0) return *tail;
  T result = *tail--;
  if (tail < buffer) {
    tail = buffer + capacity - 1;
  }
  count--;
  return result;
}

template <typename T, size_t S, typename IT>
T inline canlib_circular_buffer<T, S, IT>::first() const {
  return *head;
}

template <typename T, size_t S, typename IT>
T inline canlib_circular_buffer<T, S, IT>::last() const {
  return *tail;
}

template <typename T, size_t S, typename IT>
const T& canlib_circular_buffer<T, S, IT>::start() const {
  return buffer[1];
}

template <typename T, size_t S, typename IT>
const T& canlib_circular_buffer<T, S, IT>::operator[](IT index) const {
  if (index >= count) return *tail;
  return *(buffer + ((head - buffer + index) % capacity));
}

template <typename T, size_t S, typename IT>
IT inline canlib_circular_buffer<T, S, IT>::size() const {
  return count;
}

template <typename T, size_t S, typename IT>
IT inline canlib_circular_buffer<T, S, IT>::available() const {
  return capacity - count;
}

template <typename T, size_t S, typename IT>
bool inline canlib_circular_buffer<T, S, IT>::empty() const {
  return count == 0;
}

template <typename T, size_t S, typename IT>
bool inline canlib_circular_buffer<T, S, IT>::full() const {
  return count == capacity;
}

template <typename T, size_t S, typename IT>
void inline canlib_circular_buffer<T, S, IT>::clear() {
  head = tail = buffer;
  count = 0;
}

template <typename T, size_t S, typename IT>
size_t inline canlib_circular_buffer<T, S, IT>::offset() const {
  return _offset;
}

#endif // CANLIB_CIRCULAR_BUFFER
'''

PROTO_INTERFACE = '''
#ifndef {db_name}_PROTO_INTERFACE_H
#define {db_name}_PROTO_INTERFACE_H

#include <string>
#include <unordered_map>
#include <functional>

#include "{db_name}.pb.h"

#ifdef {db_name}_IMPLEMENTATION
#undef {db_name}_IMPLEMENTATION
#define __{db_name}_IMPLEMENTATION
#endif

#include "../../lib/{db_name}/{db_name}_network.h"

#ifdef __{db_name}_IMPLEMENTATION
#undef __{db_name}_IMPLEMENTATION
#define {db_name}_IMPLEMENTATION
#endif

#ifndef CANLIB_MESSAGE_ID_TYPE
#define CANLIB_MESSAGE_ID_TYPE
typedef uint16_t canlib_message_id;
#endif // CANLIB_MESSAGE_ID_TYPE
{circular_buffer}
#ifndef CANLIB_CIRCULAR_BUFFER_SIZE
#define CANLIB_CIRCULAR_BUFFER_SIZE 2000
#endif // CANLIB_CIRCULAR_BUFFER_SIZE


#ifndef CANLIB_PROTO_INTERFACE_TYPES
#define CANLIB_PROTO_INTERFACE_TYPES

/**
*  Use network_<> to get all the values from the protobuffer.
*  Every network can be consensed into one network_<> as all the
*  messages names are unique.
**/

typedef std::string field_name;
typedef std::string messages_name;
typedef canlib_circular_buffer<double,      CANLIB_CIRCULAR_BUFFER_SIZE> double_buffer;
typedef canlib_circular_buffer<uint64_t,    CANLIB_CIRCULAR_BUFFER_SIZE> uint64_buffer;
typedef canlib_circular_buffer<std::string, CANLIB_CIRCULAR_BUFFER_SIZE> string_buffer;

// structure contains all the messages with a enum value associated
// the type is unified to uint64_t
typedef std::unordered_map<field_name,    uint64_buffer> message_enums;
typedef std::unordered_map<messages_name, message_enums> network_enums;

// structure contains all the messages with a signal associated
// the type is unified to double
typedef std::unordered_map<field_name,    double_buffer>   message_signals;
typedef std::unordered_map<messages_name, message_signals> network_signals;

// structure contains all the messages with a string associated
// the type is unified to string
typedef std::unordered_map<field_name,    string_buffer>   message_strings;
typedef std::unordered_map<messages_name, message_strings> network_strings;

#endif // CANLIB_PROTO_INTERFACE_TYPES

void {db_name}_proto_interface_serialize_from_id(canlib_message_id id, {db_name}::Pack* pack, device_t* device);
void {db_name}_proto_interface_deserialize({db_name}::Pack* pack, network_enums* net_enums, network_signals* net_signals, network_strings* net_strings, uint64_t resample_us);

#ifdef {db_name}_PROTO_INTERAFCE_IMPLEMENTATION

void {db_name}_proto_interface_deserialize({db_name}::Pack* pack, network_enums* net_enums, network_signals* net_signals, network_strings* net_strings, uint64_t resample_us) {{
    char buffer[1024];
    {deserialize}
}}

void {db_name}_proto_interface_serialize_from_id(canlib_message_id id, {db_name}::Pack* pack, device_t* device) {{
    int index = {db_name}_index_from_id(id);

    if (index == -1) return;

    switch(id) {{
        {serialize}
    }}
}}



#endif // {db_name}_PROTO_INTERAFCE_IMPLEMENTATION

#endif // {db_name}_PROTO_INTERFACE_H
'''

DESERIALIZE_MESSAGE = '''
    for(int i = 0; i < pack->{name}_size(); i++){{
#ifdef CANLIB_TIMESTAMP
        static uint64_t last_timestamp = 0;
        if(pack->{name}(i)._inner_timestamp() - last_timestamp < resample_us) continue;
        else last_timestamp = pack->{name}(i)._inner_timestamp();
        (*net_signals)["{name_m}"]["_timestamp"].push(pack->{name}(i)._inner_timestamp());
#endif // CANLIB_TIMESTAMP

{signals}
    }}
'''
DESERIALIZE_SIGNAL = '''\t\t(*net_signals)["{name_m}"]["{signal_name}"].push(pack->{name}(i).{signal_name}());
'''
DESERIALIZE_SIGNAL_ENUM = '''\t\t(*net_enums)["{name_m}"]["{signal_name}"].push(pack->{name}(i).{signal_name}());
\t\t{database_name}_{name}_{signal_name}_enum_to_string(({database_name}_{name}_{signal_name})pack->{name}(i).{signal_name}(), buffer);
\t\t(*net_strings)["{name_m}"]["{signal_name}"].push(buffer);
'''
DESERIALIZE_SIGNAL_BITSET = '''\t\t(*net_enums)["{name_m}"]["{signal_name}"].push(pack->{name}(i).{signal_name}());
'''

SERIALIZE_MESSAGE = '''
        case {id}: {{
            {db_name}_{name_m}_t* msg = ({db_name}_{name_m}_t*)(devices->raw);
            {db_name}::{name_m_U}* proto_msg = pack->add_{proto_name}();
{signals}
#ifdef CANLIB_TIMESTAMP
            proto_msg->set__inner_timestamp(msg->_timestamp);
#endif // CANLIB_TIMESTAMP
            break;
        }}
'''
SERIALIZE_SIGNAL = '''\t\t\tproto_msg->set_{name}(msg->{name});
'''
SERIALIZE_SIGNAL_TYPE = '''\t\t\tproto_msg->set_{name}(({type})msg->{name});
'''

def _generate_deserialize(database_name, messages):
    ret = ''
    for msg in messages:
        name = f'{msg.name}'.lower()
        name_m = name.upper()
        signals = ''
        for signal in msg.signals:
            if signal.is_enum:
                signals += DESERIALIZE_SIGNAL_ENUM.format(database_name=database_name, name_m=name_m, name=name, signal_name=signal.name.lower())
            elif signal.is_bool:
                signals += DESERIALIZE_SIGNAL_BITSET.format(database_name=database_name, name_m=name_m, name=name, signal_name=signal.name.lower())
            else:
                signals += DESERIALIZE_SIGNAL.format(name_m=name_m, name=name, signal_name=signal.name.lower())
        ret += DESERIALIZE_MESSAGE.format(name=name, name_m=name_m, signals=signals)
    return ret

def _generate_serialize(database_name, messages: List[Message]):
    ret = ''
    for msg in messages:
        name = msg.name.lower()
        name_m = name.upper()
        proto_name = name
        
        dev_name = "message"
        if msg.has_conversions:
            name += "_converted"
            dev_name += "_conversion"
        else:
            dev_name += "_raw"
        
        signals = ''
        for signal in msg.signals:
            if signal.choices is not None:
              signals += SERIALIZE_SIGNAL_TYPE.format(name=signal.name.lower(), type=f'{database_name}::{database_name}_{msg.name.lower()}_{signal.name.lower()}')
            else:
              signals += SERIALIZE_SIGNAL.format(name=signal.name.lower())
        ret += SERIALIZE_MESSAGE.format(db_name=database_name, id=msg.frame_id, name=name, name_m=name, signals=signals, name_m_U=name_m, dev_name=dev_name, proto_name=proto_name)
    return ret

def _get(value, default):
    if value is None:
        value = default

    return value

def generate_proto_interface(database, database_name):
    messages = [Message(message, database_name) for message in database.messages]

    return PROTO_INTERFACE.format(circular_buffer=CIRCULAR_BUFFER, db_name=database_name, deserialize=_generate_deserialize(database_name, messages),
                                    serialize=_generate_serialize(database_name, messages))