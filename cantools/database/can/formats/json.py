from ..signal import Signal, Decimal
from ..message import Message
from ..node import Node
from ....errors import Error
from ..internal_database import InternalDatabase
from collections import OrderedDict
import json
import math

from ...utils import (
    type_sort_signals,
    type_sort_attributes,
    type_sort_choices,
    sort_signals_by_start_bit,
    sort_signals_by_start_bit_reversed,
    SORT_SIGNALS_DEFAULT
)

# Little change to allow generation for new CAN library, TODO: restore the previous configuration 
MESSAGE_BITS = 8 # old = 6
TOPIC_BITS = 3 # old = 5

MAX_PRIORITY = 3

MESSAGES_PER_PRIORITY = int(2**MESSAGE_BITS / (MAX_PRIORITY + 1))


class IdGenerator:
    def __init__(self, topic: int, blacklist=set()):
        self.ids_per_priority = [0] * (MAX_PRIORITY + 1)
        self.topic = topic
        self.blacklist = blacklist

    def next(self, priority: int) -> int:
        item_id = self.ids_per_priority[priority]
        while True:
            self.ids_per_priority[priority] += 1
            start = MESSAGES_PER_PRIORITY * (MAX_PRIORITY - priority)
            if item_id >= MESSAGES_PER_PRIORITY:
                raise Exception(f"No more messages (>{MESSAGES_PER_PRIORITY})")

            scoped_id = item_id + start
            global_id = (scoped_id << TOPIC_BITS) + self.topic

            if global_id not in self.blacklist:
                return global_id

            item_id += 1  # next one

def get_messages_by_topic(db, topic):
    ret = []
    for message in db['messages']:
        if 'topic' in message and message['topic'] == topic:
            ret.append(message)
    return ret

def generate_ids(db, blacklist=set()):
    ids = {}
    topics = generate_topics_id(db)
    for name, id in topics.items():
        if name == "FIXED_IDS":
            continue

        messages = get_messages_by_topic(db, name)
        message_ids = generate_messages_id(messages, id, blacklist)

        ids[name] = {"id": id, "messages": message_ids}

    return ids

def bit_to_bytes(bits):
    return (bits+7)//8

def generate_messages_id(topic_messages, topic: int, blacklist=set()):
    generator = IdGenerator(topic, blacklist)

    message_ids = {}
    for message in topic_messages:
        message_name = message['name']
        message_priority = message["priority"]
        
        message_priority = MAX_PRIORITY - message_priority

        if message_priority > MAX_PRIORITY or message_priority < 0:
            raise Exception(f'"{message_name}" out of range (0-{MAX_PRIORITY})')

        if len(message["sending"]) > 1:
            multiple_ids = {}
            for device_name in message["sending"]:
                generated_message_name = f"{message_name}_{device_name}"
                multiple_ids[generated_message_name] = generator.next(message_priority)
            message_ids[message_name] = multiple_ids
        else:
            global_id = generator.next(message_priority)
            message_ids[message_name] = {message_name: global_id}
    return message_ids


def generate_topics_id(db):
    topics = set()
    for message in db['messages']:
        if 'topic' in message:
            topics.add(message['topic'])
    ids = {topic: index for index, topic in enumerate(sorted(topics))}

    if len(ids) >= 2**TOPIC_BITS:
        raise Exception(f"No more topics (>{2**TOPIC_BITS})")

    return ids


lengths = {'bool': 1, 'uint8': 8, 'int8': 8, 'uint16': 16, 'int16': 16, 'uint32': 32, 'int32': 32,
            'uint64': 64, 'int64': 64, 'float32': 32, 'float64': 64}
types_size = [1, 8, 16, 32, 64]

def get_length(range, precision):
    return math.ceil(math.log2(range//precision))

def get_signal(name, signal, offset: int, types, endianness):
    is_float = False
    choices = None
    is_signed = False
    optimize = True
    precision = 1
    if isinstance(signal, dict):
        optimize = signal.get("optimize", True)
        is_signed = signal.get("signed", False)
        if signal['type'][:5] == 'float':
            is_float = True
        if 'force' in signal:
            type = lengths[signal['force']]
            if 'range' in signal:
                maximum = signal['range'][0]
                minimum = signal['range'][1]
            else:
                minimum = 0
                maximum = 1<<type
        else:
            maximum = signal['range'][0]
            minimum = signal['range'][1]
            range = maximum - minimum
            precision = signal['precision'] if 'precision' in signal else 1
            type = get_length(abs(range), precision)
    else:
        if signal in types:
            if types[signal]['type'] == 'enum':
                type = get_length(len(types[signal]['items']), 1)
                choices = OrderedDict([(i,j) for i, j in enumerate(types[signal]['items'])])
            else:       #bitset
                ret = []
                for item in types[signal]['items']:
                    ret.append(Signal(name + '_' + item, offset, 1, is_float=False, minimum=0, maximum=1, decimal=Decimal(1, 0, 0, 1), byte_order=endianness))
                    offset += 1
                return (offset, ret)
        else:
            if signal not in lengths:
                print(f'missing definition of type: {signal}')
            type = lengths[signal]

        if "int" in signal and signal[0] == 'i':
            is_signed = True
        if is_signed:
            maximum = (1<<(type-1))-1
            minimum = -(1<<(type-1))
        else:
            minimum = 0
            maximum = (1<<type)-1

    if maximum < minimum:
        maximum, minimum = minimum, maximum
    if is_float:
        if optimize:
            precision = abs(maximum-minimum) / ((1<<type)-1)
    if is_float:
        for i in types_size:
            if i >= type:
                type = i
                break
    
    start = offset
    if endianness == 'big_endian':
        start = offset+7
    
    return (offset+type, [Signal(name, start, type, is_float=False, minimum=minimum, maximum=maximum, offset=(minimum), scale=precision, is_signed=is_signed,
                            decimal=Decimal(precision, (minimum), minimum, maximum), choices=choices, byte_order=endianness)])

def get_reserved_ids(db, messages) -> set:
    ret = set()
    for message in messages:
        ret.add(message.frame_id)
    for message in db['messages']:
        if 'fixed_id' in message:
            ret.add(message['fixed_id'])
    return ret

def load_string(string: str, strict: bool = True,
                sort_signals: type_sort_signals = sort_signals_by_start_bit, messages = []) -> InternalDatabase:
    db = json.loads(string)

    nodes = set()

    for i in db['messages']:
        for j in i['sending']:
            nodes.add(Node(j))
        for j in i['receiving']:
            nodes.add(Node(j))
    msgs = []
    reserved_ids = get_reserved_ids(db, messages)
    ids = generate_ids(db, reserved_ids)
    for message in db['messages']:
        comment = ''
        cycle_time = None
        if 'interval' in message:
            if message['interval'] == 'oneshot':
                cycle_time = None
            else:
                cycle_time = message['interval']
        if 'description' in message:
            comment = message['description']
        endianness = 'little_endian'
        if 'endianness' in message:
            if message['endianness'] == 'bigAss':
                endianness = 'big_endian'
        id = None
        msg_name = message['name']
        topic_name = None
        topic_id = None
        for sending in message['sending']:
            if 'topic' in message:
                if len(message['sending']) > 1:
                    id = ids[message['topic']]['messages'][message['name']][f"{message['name']}_{sending}"]
                    msg_name = f"{message['name']}_{sending}"
                else:
                    id = ids[message['topic']]['messages'][message['name']][message['name']]
                topic_id = ids[message['topic']]['id']
                topic_name = message['topic']
            else:
                if 'fixed_id' not in message:
                    print(f'missing topic in message {message["name"]}')
                id = message['fixed_id']
                topic_id = None
                topic_name = 'FIXED_IDS'
            signals = []
            offset = 0
            for signal in message['contents']:
                offset, s = get_signal(signal, message['contents'][signal], offset, db['types'], endianness=endianness)
                signals += s
            if offset > 64:
                print(offset)
                raise Exception(f'the payload of {msg_name} is too BIG🍆')
            msgs.append(Message(id, msg_name, bit_to_bytes(offset), signals, comment=comment, cycle_time=cycle_time, topic_name=topic_name, topic_id=topic_id))
    return InternalDatabase(msgs, list(nodes), [], "1")