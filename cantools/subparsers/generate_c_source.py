import argparse
import os
import os.path

from .. import database
from ..database.can.c_source import generate
from ..database.can.c_source import camel_to_snake_case
from ..database.can.proto import generate_proto
from ..database.can.proto_interface import generate_proto_interface
from ..database.can.watchdog import generate_watchdog
from ..database.can.c_utils import generate_c_utils

LIBPATH = '/lib/{network}/'
PROTOPATH = '/proto/{network}/'
DBCPATH = '/dbc/{network}'

def load_database_folder(args, path):
    # Check if path is a folder
    if not os.path.isdir(path):
        raise argparse.ArgumentTypeError(f"{path} is not a folder")
    # Check if folder contains multiple subfolders (one for each network) but
    # with only no subsubfolder
    subfolders = [f.path for f in os.scandir(path) if f.is_dir()]
    if len(subfolders) == 0:
        raise argparse.ArgumentTypeError(f"{path} does not contain any subfolder")
    for subfolder in subfolders:
        subsubfolders = [f.path for f in os.scandir(subfolder) if f.is_dir()]
        if len(subsubfolders) != 0:
            raise argparse.ArgumentTypeError(f"{subfolder} contains subfolders")


    # Check for every subfolder if contains a .dbc file or .json file
    dbs = []
    dbs_names = []
    for subfolder in subfolders:
        dbs_names.append(camel_to_snake_case(os.path.basename(subfolder)))
        files = [(f.name, f.path) for f in os.scandir(subfolder) if f.is_file()]
        dbc_files = [f for f in files if f[1].endswith('.dbc')]
        json_files = [f for f in files if f[1].endswith('.json') and "network" in f[0]] # check if json and contains network
        if len(dbc_files) == 0 and len(json_files) == 0:
            raise argparse.ArgumentTypeError(f"{subfolder} does not contain a .dbc or .json file")
        # Load dbc files, then json files
        db = None
        for dbc_name, dbc_path in dbc_files:
            if db is None:
                db = database.load_file(dbc_path, encoding=args.encoding,
                                        prune_choices=args.prune,
                                        strict=not args.no_strict)
            else:
                db.add_dbc_file(dbc_path)
        for json_name, json_path in json_files:
            if db is None:
                db = database.load_file(json_path, encoding=args.encoding,
                                        prune_choices=args.prune,
                                        strict=not args.no_strict)
            else:
                db.add_json_file(json_path)
        dbs.append(db)
    return dbs, dbs_names

def _do_generate_c_source(args):
    dbases = []
    dbases_names = []
    if args.infile is None:
        dbase, dbase_name = load_database_folder(args, args.infolder)
        dbases.append(dbase)
        dbases_names.append(dbase_name)
    else:
        dbases.append(database.load_file(args.infile,
                                encoding=args.encoding,
                                prune_choices=args.prune,
                                strict=not args.no_strict))
        if args.database_name is None or len(dbases) > 1:
            basename = os.path.basename(args.infile)
            database_name = os.path.splitext(basename)[0]
            database_name = camel_to_snake_case(database_name)
        else:
            database_name = args.database_name
        dbases_names.append(database_name)

    # flatten list of lists
    dbases = [item for sublist in dbases for item in sublist]
    dbases_names = [item for sublist in dbases_names for item in sublist]
    
    for dbase, dbase_name in zip(dbases, dbases_names):
        generate_from_db(dbase, dbase_name, args.no_floating_point_numbers, args.generate_fuzzer, args.bit_fields,
                        args.use_float, args.node, args.output_directory, args.generate_dbc)


def generate_from_db(dbase, database_name, no_floating_point_numbers = False, generate_fuzzer = False, bit_fields=False,
                     use_float=True, node=None, output_directory='.', generate_dbc=False):

    filename_h = database_name + '_network.h'
    filename_c = database_name + '_network.c'
    fuzzer_filename_c = 'network_fuzzer.c'
    fuzzer_filename_mk = 'network_fuzzer.mk'
    file_name_watchdog = database_name + '_watchdog.h'
    file_name_watchdog_implementation = database_name + '_watchdog.c'
    filename_proto = database_name + ".proto"
    filename_proto_interface = database_name + "_proto_interface.h"
    filename_dbc = database_name + '.dbc'
    filename_utils_c = database_name + '_utils_c.h'
    filename_utils_c_implementation = database_name + '_utils_c.c'

    proto = generate_proto(dbase, database_name)
    proto_interface = generate_proto_interface(dbase, database_name)
    watchdog, watchdog_implementation = generate_watchdog(dbase, database_name)
    utils_c, utils_c_implementation = generate_c_utils(database_name, dbase)
    
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
    dbcpath = DBCPATH.format(network=database_name)

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
    
    path_watchdog_implementation = os.path.join(output_directory+libpath, file_name_watchdog_implementation)

    with open(path_watchdog_implementation, 'w') as fout:
        fout.write(watchdog_implementation)

    path_utils_c = os.path.join(output_directory+libpath, filename_utils_c)

    with open(path_utils_c, 'w') as fout:
        fout.write(utils_c)

    path_utils_c_implementation = os.path.join(output_directory+libpath, filename_utils_c_implementation)

    with open(path_utils_c_implementation, 'w') as fout:
        fout.write(utils_c_implementation)

    if generate_dbc:
        os.makedirs(output_directory+dbcpath, exist_ok=True)
        path_dbc = os.path.join(output_directory+dbcpath, filename_dbc)

        with open(path_dbc, 'w') as fout:
            fout.write(dbase.as_dbc_string(shorten_long_names=False))

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
        '--node',
        help='Generate pack/unpack functions only for messages sent/received by the node.')
    generate_c_source_parser.add_argument(
        '--generate-dbc',
        action='store_true',
        default=False,
        help='Generate the dbc file'
    )

    in_group = generate_c_source_parser.add_mutually_exclusive_group(required=True)
    in_group.add_argument(
        '--infile',
        help='Input database file.')
    in_group.add_argument(
        '--infolder',
        help='Input database folder.')

    generate_c_source_parser.set_defaults(func=_do_generate_c_source)
