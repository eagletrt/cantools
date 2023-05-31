import argparse
import os
import os.path

from .. import database
from ..database.can.c_source import generate
from ..database.can.c_source import camel_to_snake_case
from ..database.can.proto import generate_proto
from ..database.can.proto_interface import generate_proto_interface
from ..database.can.watchdog import generate_watchdog

LIBPATH = '/lib/{network}/'
PROTOPATH = '/proto/{network}/'

def _do_generate_c_source(args):
    dbase = database.load_file(args.infile,
                               encoding=args.encoding,
                               prune_choices=args.prune,
                               strict=not args.no_strict)
    if args.database_name is None:
        basename = os.path.basename(args.infile)
        database_name = os.path.splitext(basename)[0]
        database_name = camel_to_snake_case(database_name)
    else:
        database_name = args.database_name
    generate_from_db(dbase, database_name, args.no_floating_point_numbers, args.generate_fuzzer, args.bit_fields,
                     args.use_float, args.node, args.output_directory)


def generate_from_db(dbase, database_name, no_floating_point_numbers = False, generate_fuzzer = False, bit_fields=False,
                     use_float=True, node=None, output_directory='.'):

    filename_h = 'network.h'
    filename_c = 'network.c'
    fuzzer_filename_c = 'network_fuzzer.c'
    fuzzer_filename_mk = 'network_fuzzer.mk'
    filename_proto = "network.proto"
    filename_proto_interface = "network_proto_interface.h"
    file_name_watchdog = 'network_watchdog.h'

    proto = generate_proto(dbase, database_name)
    proto_interface = generate_proto_interface(dbase, database_name)
    watchdog = generate_watchdog(dbase, database_name)
    
    header, source, fuzzer_source, fuzzer_makefile = generate(
        dbase,
        database_name,
        filename_h,
        filename_c,
        fuzzer_filename_c,
        not no_floating_point_numbers,
        bit_fields,
        use_float,
        node)

    libpath = LIBPATH.format(network=database_name)
    protopath = PROTOPATH.format(network=database_name)

    os.makedirs(output_directory+libpath, exist_ok=True)
    os.makedirs(output_directory+protopath, exist_ok=True)
    
    path_h = os.path.join(output_directory+libpath, filename_h)
    
    with open(path_h, 'w') as fout:
        fout.write(header)

    path_c = os.path.join(output_directory+libpath, filename_c)

    with open(path_c, 'w') as fout:
        fout.write(source)

    path_proto = os.path.join(output_directory+protopath, filename_proto)

    with open(path_proto, 'w') as fout:
        fout.write(proto)

    path_proto_interface = os.path.join(output_directory+protopath, filename_proto_interface)

    with open(path_proto_interface, 'w') as fout:
        fout.write(proto_interface)

    path_watchdog = os.path.join(output_directory+libpath, file_name_watchdog)

    with open(path_watchdog, 'w') as fout:
        fout.write(watchdog)

    print(f'Successfully generated {path_h} and {path_c} and {path_proto} and {path_proto_interface}.')

    if generate_fuzzer:
        fuzzer_path_c = os.path.join(output_directory, fuzzer_filename_c)

        with open(fuzzer_path_c, 'w') as fout:
            fout.write(fuzzer_source)

        fuzzer_path_mk = os.path.join(output_directory, fuzzer_filename_mk)

        with open(fuzzer_filename_mk, 'w') as fout:
            fout.write(fuzzer_makefile)

        print('Successfully generated {} and {}.'.format(fuzzer_path_c,
                                                         fuzzer_path_mk))
        print()
        print(
            'Run "make -f {}" to build and run the fuzzer. Requires a'.format(
                fuzzer_filename_mk))
        print('recent version of clang.')


def add_subparser(subparsers):
    generate_c_source_parser = subparsers.add_parser(
        'generate_c_source',
        description='Generate C source code from given database file.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    generate_c_source_parser.add_argument(
        '--database-name',
        help=('The database name.  Uses the stem of the input file name if not'
              ' specified.'))
    generate_c_source_parser.add_argument(
        '--no-floating-point-numbers',
        action='store_true',
        default=False,
        help='No floating point numbers in the generated code.')
    generate_c_source_parser.add_argument(
        '--bit-fields',
        action='store_true',
        help='Use bit fields to minimize struct sizes.')
    generate_c_source_parser.add_argument(
        '-e', '--encoding',
        help='File encoding.')
    generate_c_source_parser.add_argument(
        '--prune',
        action='store_true',
        help='Try to shorten the names of named signal choices.')
    generate_c_source_parser.add_argument(
        '--no-strict',
        action='store_true',
        help='Skip database consistency checks.')
    generate_c_source_parser.add_argument(
        '-f', '--generate-fuzzer',
        action='store_true',
        help='Also generate fuzzer source code.')
    generate_c_source_parser.add_argument(
        '-o', '--output-directory',
        default='.',
        help='Directory in which to write output files.')
    generate_c_source_parser.add_argument(
        '--use-float',
        action='store_true',
        default=False,
        help='Use float instead of double for floating point generation.')
    generate_c_source_parser.add_argument(
        'infile',
        help='Input database file.')
    generate_c_source_parser.add_argument(
        '--node',
        help='Generate pack/unpack functions only for messages sent/received by the node.')
    generate_c_source_parser.set_defaults(func=_do_generate_c_source)
