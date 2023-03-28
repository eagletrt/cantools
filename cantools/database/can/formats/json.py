from ..signal import Signal
from ..message import Message
from ..node import Node
from ....errors import Error
from ..internal_database import InternalDatabase
import json

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


lenghts = {'uint8': 8, 'int8': 8, 'uint16': 16, 'int16': 16, 'uint32': 32, 'int32': 32,
            'uint64': 64, 'int64': 64}

def get_signal(name, signal, offset: int, types):
    if name in types:
        type = types['name'][type]
    else:
        if isinstance(signal, dict):
            type = signal
        elif 'force' in signal:
            type = signal['force']
        else:
            #range and precision
            return None
    return (offset+1, Signal(name, offset, 1))

def get_reserved_ids(db) -> set:
    ret = set()
    for message in db['messages']:
        if 'fixed_id' in message:
            ret.add(message['fixed_id'])
    return ret

def load_string(string: str, strict: bool = True,
                sort_signals: type_sort_signals = sort_signals_by_start_bit) -> InternalDatabase:
    db = json.loads(string)

    reserved_ids = get_reserved_ids(db)
    ids = generate_ids(db, reserved_ids)
    for message in db['messages']:
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
                offset, s = get_signal(signal, message['contents'][signal], offset)
                signals.append(s)
            msg = Message(id, message['name'], len(signals), signals)