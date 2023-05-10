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

MESSAGE_BITS = 6
TOPIC_BITS = 5

MAX_PRIORITY = 7

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


def generate_messages_id(topic_messages, topic: int, blacklist=set()):
    generator = IdGenerator(topic, blacklist)

    message_ids = {}
    for message in topic_messages:
        message_name = message['name']
        message_priority = message["priority"]

        if message_priority > MAX_PRIORITY:
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
    ids = {topic: index for index, topic in enumerate(topics)}

    if len(ids) >= 2**TOPIC_BITS:
        raise Exception(f"No more topics (>{2**TOPIC_BITS})")

    return ids


lengths = {'bool': 1, 'uint8': 8, 'int8': 8, 'uint16': 16, 'int16': 16, 'uint32': 32, 'int32': 32,
            'uint64': 64, 'int64': 64, 'float32': 32}
types_size = [1, 8, 16, 32, 64]

def get_length(range, precision):
    return math.ceil((math.log2(range//precision)+1)/8)

def get_signals(name, signal, offset: int, types):
    is_float = False
    choices = None
    precision = 1
    if isinstance(signal, dict):
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
                    ret.append(Signal(name + '_' + item, offset, 1, is_float=False, minimum=0, maximum=0, decimal=Decimal(1, 0, 0, 1)))
                    offset += 1
                return (offset, ret)
        else:
            type = lengths[signal]
        minimum = 0
        maximum = 1<<type
    if maximum < minimum:
        maximum, minimum = minimum, maximum
    if is_float:
        precision = abs(maximum-minimum) / ((1<<type)-1)
    for i in types_size:
        if i > type:
            type = i
            break
    return (offset+type, [Signal(name, offset, type, is_float=False, minimum=minimum, maximum=maximum, offset=(minimum), scale=precision,
                            decimal=Decimal(precision, (minimum), minimum, maximum), choices=choices)])

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
    comment = ''
    for message in db['messages']:
        if 'description' in message:
            comment = message['description']
        for sending in message['sending']:
            if 'topic' in message:
                if len(message['sending']) > 1:
                    id = ids[message['topic']]['messages'][message['name']][f"{message['name']}_{sending}"]
                else:
                    id = ids[message['topic']]['messages'][message['name']][message['name']]
            else:
                id = message['fixed_id']
            signals = []
            offset = 0
            for signal in message['contents']:
                offset, s = get_signals(signal, message['contents'][signal], offset, db['types'])
                signals += s
        msgs.append(Message(id, message['name'], offset, signals, comment=comment))
    return InternalDatabase(msgs, list(nodes), [], "1")