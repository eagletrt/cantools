import re
import time
from decimal import Decimal

from ...version import __version__

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

#include "network.pb.h"

#ifdef {db_name}_IMPLEMENTATION
#undef {db_name}_IMPLEMENTATION
#define __{db_name}_IMPLEMENTATION
#endif

#include "../../lib/{db_name}/network.h"

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

void {db_name}_proto_interface_serialize_from_id(canlib_message_id id, {db_name}::Pack* pack, {db_name}_devices* map);
void {db_name}_proto_interface_deserialize({db_name}::Pack* pack, network_enums* net_enums, network_signals* net_signals, network_strings* net_strings, uint64_t resample_us);

#ifdef {db_name}_PROTO_INTERAFCE_IMPLEMENTATION

void {db_name}_proto_interface_deserialize({db_name}::Pack* pack, network_enums* net_enums, network_signals* net_signals, network_strings* net_strings, uint64_t resample_us) {{
    char buffer[1024];
    {deserialize}
}}

void {db_name}_proto_interface_serialize_from_id(canlib_message_id id, {db_name}::Pack* pack, {db_name}_devices* map) {{
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

SERIALIZE_MESSAGE = '''
        case {id}: {{
            {db_name}_{name_m}_converted_t* msg = ({db_name}_{name_m}_converted_t*)(&(*map)[index].message_conversion);
            {db_name}::{name_m}* proto_msg = pack->add_{name}();
{signals}
#ifdef CANLIB_TIMESTAMP
            proto_msg->set__inner_timestamp(msg->_timestamp);
#endif // CANLIB_TIMESTAMP
            break;
        }}
'''
SERIALIZE_SIGNAL = '''\t\t\tproto_msg->set_{name}(msg->{name});
'''

def _generate_deserialize(database_name, messages):
    ret = ''
    for msg in messages:
        name = f'{msg.name}'.lower()
        name_m = name.upper()
        signals = ''
        for signal in msg.signals:
            signals += DESERIALIZE_SIGNAL.format(name_m=name_m, name=name, signal_name=signal.name.lower())
        ret += DESERIALIZE_MESSAGE.format(name=name, name_m=name_m, signals=signals)
    return ret

def _generate_serialize(database_name, messages):
    ret = ''
    for msg in messages:
        name = f'{msg.name}'.lower()
        name_m = name.upper()
        signals = ''
        for signal in msg.signals:
            signals += SERIALIZE_SIGNAL.format(name=signal.name.lower())
        ret += SERIALIZE_MESSAGE.format(db_name=database_name, id=msg.frame_id, name=name, name_m=name_m.lower(), signals=signals)
    return ret

def generate_proto_interface(database, database_name):
    messages = database.messages
    return PROTO_INTERFACE.format(circular_buffer=CIRCULAR_BUFFER, db_name=database_name, deserialize=_generate_deserialize(database_name, messages),
                                    serialize=_generate_serialize(database_name, messages))