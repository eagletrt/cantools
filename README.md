![appveyor](https://ci.appveyor.com/api/projects/status/github/eerimoq/cantools?svg=true)\_
![coverage](https://coveralls.io/repos/github/eerimoq/cantools/badge.svg?branch=master)\_
![nala](https://img.shields.io/badge/nala-test-blue.svg)\_

# EAGLE

## cantools

The old canlib allowed reading JSON files describing various messages
sent over CAN in different networks and generating corresponding code.
The code consisted of data structures to represent the messages and
functions capable of converting the messages from binary format to these
structures and vice versa. For various reasons, it was necessary to add
the ability to read DBC files in addition to JSON files. It was decided
to use [cantools](https://github.com/cantools/cantools) as the starting
point and add the functions present in canlib to it.

### Features:

-   Importing various files (JSON, DBC, \...) into a single network
-   Generating code
-   Exporting a network to DBC

### Code Generation

Normally, to generate and update the code for all, simply push to the
eagletrt/can repository. If instead you want to generate the code
locally, type the command:

``` bash
python3 -m cantools generate_c_source --use-float --infolder ./networks -o ./output_folder
```

Example folder structure for networks:

    .
    └── networks/
        ├── network1/
        │   └── a.dbc
        ├── network2/
        │   ├── a.json
        │   └── b.json
        └── network3/
            ├── a.json
            └── b.dbc

Output folder structure:

    .
    └── output_folder/
        ├── lib/
        │   ├── network1/
        │   ├── network2/
        │   └── network3/
        └── proto/
            ├── network1/
            ├── network2/
            └── network3/

For example, the lib/network1/ folder will contain the following files:

    .
    └── lib/network1/
       ├── network1_network.c
       ├── network1_network.h
       ├── network1_utils_c.c
       ├── network1_utils_c.h
       ├── network1_watchdog.c
       └── network1_watchdog.h

While the proto/network1 folder contains:

    .
    └── proto/network1/
        ├── network1.proto
        └── network1_proto_interface.h

### Exporting to DBC

To generate the DBC file, simply add the `--generate-dbc` parameter to
the code generation command:

``` bash
python3 -m cantools generate_c_source --use-float --generate-dbc --infolder ./networks -o ./output_folder
```

The dbc files will be inside the ./output_folder/dbc directory.

### Importing from code

``` python
>>> import cantools
>>> db = cantools.database.load_file('file.dbc')
>>> db.add_json_file('file.json')
>>> print(db.as_dbc_string())
```

# About

CAN BUS tools in Python 3.

-   [DBC](http://www.socialledge.com/sjsu/index.php?title=DBC_Format),
    [KCD](https://github.com/julietkilo/kcd), SYM, ARXML 3&4 and CDD
    file parsing.
-   CAN message encoding and decoding.
-   Simple and extended signal multiplexing.
-   Diagnostic DID encoding and decoding.
-   `candump` output decoder.
-   Node
    [tester](http://cantools.readthedocs.io/en/latest/#cantools.tester.Tester).
-   [C]{.title-ref} source code generator.
-   CAN bus monitor.
-   Graphical plots of signals.

Project homepage: <https://github.com/eerimoq/cantools>

Documentation: <https://cantools.readthedocs.io>

# Installation

``` bash
python3 -m pip install cantools
```

# Example usage

## Scripting

The example starts by parsing a [small
DBC-file](https://github.com/eerimoq/cantools/blob/master/tests/files/dbc/motohawk.dbc)
and printing its messages and signals.

``` python
>>> import cantools
>>> from pprint import pprint
>>> db = cantools.database.load_file('tests/files/dbc/motohawk.dbc')
>>> db.messages
[message('ExampleMessage', 0x1f0, False, 8, 'Example message used as template in MotoHawk models.')]
>>> example_message = db.get_message_by_name('ExampleMessage')
>>> pprint(example_message.signals)
[signal('Enable', 7, 1, 'big_endian', False, 1.0, 0, 0.0, 0.0, '-', False, None, {0: 'Disabled', 1: 'Enabled'}, None),
 signal('AverageRadius', 6, 6, 'big_endian', False, 0.1, 0, 0.0, 5.0, 'm', False, None, None, ''),
 signal('Temperature', 0, 12, 'big_endian', True, 0.01, 250, 229.53, 270.47, 'degK', False, None, None, None)]
```

The example continues
[encoding](http://cantools.readthedocs.io/en/latest/#cantools.database.can.Message.encode)
a message and sending it on a CAN bus using the
[python-can](https://python-can.readthedocs.io/en/master/) package.

``` python
>>> import can
>>> can_bus = can.interface.Bus('vcan0', bustype='socketcan')
>>> data = example_message.encode({'Temperature': 250.1, 'AverageRadius': 3.2, 'Enable': 1})
>>> message = can.Message(arbitration_id=example_message.frame_id, data=data)
>>> can_bus.send(message)
```

Alternatively, a message can be encoded using the
[encode_message()](http://cantools.readthedocs.io/en/latest/#cantools.database.can.Database.encode_message)
method on the database object.

The last part of the example receives and
[decodes](http://cantools.readthedocs.io/en/latest/#cantools.database.can.Database.decode_message)
a CAN message.

``` python
>>> message = can_bus.recv()
>>> db.decode_message(message.arbitration_id, message.data)
{'AverageRadius': 3.2, 'Enable': 'Enabled', 'Temperature': 250.09}
```

See [examples](https://github.com/eerimoq/cantools/blob/master/examples)
for additional examples.

## Command line tool

#### The decode subcommand

Decode CAN frames captured with the Linux program `candump`.

``` text
$ candump vcan0 | python3 -m cantools decode tests/files/dbc/motohawk.dbc
  vcan0  1F0   [8]  80 4A 0F 00 00 00 00 00 ::
ExampleMessage(
    Enable: 'Enabled' -,
    AverageRadius: 0.0 m,
    Temperature: 255.92 degK
)
  vcan0  1F0   [8]  80 4A 0F 00 00 00 00 00 ::
ExampleMessage(
    Enable: 'Enabled' -,
    AverageRadius: 0.0 m,
    Temperature: 255.92 degK
)
  vcan0  1F0   [8]  80 4A 0F 00 00 00 00 00 ::
ExampleMessage(
    Enable: 'Enabled' -,
    AverageRadius: 0.0 m,
    Temperature: 255.92 degK
)
```

Alternatively, the decoded message can be printed on a single line:

``` text
$ candump vcan0 | python3 -m cantools decode --single-line tests/files/dbc/motohawk.dbc
  vcan0  1F0   [8]  80 4A 0F 00 00 00 00 00 :: ExampleMessage(Enable: 'Enabled' -, AverageRadius: 0.0 m, Temperature: 255.92 degK)
  vcan0  1F0   [8]  80 4A 0F 00 00 00 00 00 :: ExampleMessage(Enable: 'Enabled' -, AverageRadius: 0.0 m, Temperature: 255.92 degK)
  vcan0  1F0   [8]  80 4A 0F 00 00 00 00 00 :: ExampleMessage(Enable: 'Enabled' -, AverageRadius: 0.0 m, Temperature: 255.92 degK)
```

#### The plot subcommand

The plot subcommand is similar to the decode subcommand but messages are
visualized using [matplotlib](https://matplotlib.org/) instead of being
printed to stdout.

``` bash
$ candump -l vcan0
$ cat candump-2021-01-04_180521.log
(1609779922.655421) vcan0 00000343#B204B9049C049C04
(1609779922.655735) vcan0 0000024A#120527052E051905
(1609779923.657524) vcan0 00000343#C404C404CB04C404
(1609779923.658086) vcan0 0000024A#8B058B058B059205
(1609779924.659912) vcan0 00000343#5C04790479045504
(1609779924.660471) vcan0 0000024A#44064B0659064406
(1609779925.662277) vcan0 00000343#15040704F203F203
(1609779925.662837) vcan0 0000024A#8B069906A706A706
(1609779926.664191) vcan0 00000343#BC03B503A703BC03
(1609779926.664751) vcan0 0000024A#A006A706C406C406

$ cat candump-2021-01-04_180521.log | python3 -m cantools plot tests/files/dbc/abs.dbc
```

![image](https://github.com/cantools/cantools/raw/master/docs/plot-1.png)

If you don\'t want to show all signals you can select the desired
signals with command line arguments. A `*` can stand for any number of
any character, a `?` for exactly one arbitrary character. Signals
separated by a `-` are displayed in separate subplots. Optionally a
format can be specified after a signal, separated by a colon.

``` bash
$ cat candump-2021-01-04_180521.log | python3 -m cantools plot tests/files/dbc/abs.dbc '*33.*fl:-<' '*33.*fr:->' - '*33.*rl:-<' '*33.*rr:->'
```

![image](https://github.com/cantools/cantools/raw/master/docs/plot-2-subplots.png)

Signals with a different range of values can be displayed in the same
subplot on different vertical axes by separating them with a comma.

``` bash
$ cat candump-2021-01-04_180521.log | cantools plot --auto-color tests/files/dbc/abs.dbc -- \
   --ylabel 'Bremse 33' '*_33.*fl*:-<' '*_33.*fr*:>' '*_33.*rl*:3' '*_33.*rr*:4' , \
   --ylabel 'Bremse 2' '*_2.*fl*:-<' '*_2.*fr*:>' '*_2.*rl*:3' '*_2.*rr*:4'
```

![image](https://github.com/cantools/cantools/raw/master/docs/plot-2-axes.png)

Matplotlib comes with different preinstalled styles that you can use:

``` bash
$ cat candump-2021-01-04_180521.log | cantools plot tests/files/dbc/abs.dbc --style seaborn
```

![image](https://github.com/cantools/cantools/raw/master/docs/plot-seaborn.png)

You can try all available styles with

``` bash
$ cantools plot --list-styles . | sed -n '/^- /s/^- //p' | while IFS= read -r style; do
      cat candump-2021-01-04_180521.log | cantools plot tests/files/dbc/abs.dbc --style "$style" --title "--style '$style'"
  done
```

For more information see

``` bash
$ python3 -m cantools plot --help
```

Note that by default matplotlib is not installed with cantools. But it
can be by specifying an extra at installation:

``` bash
$ python3 -m pip install cantools[plot]
```

#### The dump subcommand

Dump given database in a human readable format:

``` text
$ python3 -m cantools dump tests/files/dbc/motohawk.dbc
================================= Messages =================================

  ------------------------------------------------------------------------

  Name:       ExampleMessage
  Id:         0x1f0
  Length:     8 bytes
  Cycle time: - ms
  Senders:    PCM1
  Layout:

                          Bit

             7   6   5   4   3   2   1   0
           +---+---+---+---+---+---+---+---+
         0 |<-x|<---------------------x|<--|
           +---+---+---+---+---+---+---+---+
             |                       +-- AverageRadius
             +-- Enable
           +---+---+---+---+---+---+---+---+
         1 |-------------------------------|
           +---+---+---+---+---+---+---+---+
         2 |----------x|   |   |   |   |   |
     B     +---+---+---+---+---+---+---+---+
     y               +-- Temperature
     t     +---+---+---+---+---+---+---+---+
     e   3 |   |   |   |   |   |   |   |   |
           +---+---+---+---+---+---+---+---+
         4 |   |   |   |   |   |   |   |   |
           +---+---+---+---+---+---+---+---+
         5 |   |   |   |   |   |   |   |   |
           +---+---+---+---+---+---+---+---+
         6 |   |   |   |   |   |   |   |   |
           +---+---+---+---+---+---+---+---+
         7 |   |   |   |   |   |   |   |   |
           +---+---+---+---+---+---+---+---+

  Signal tree:

    -- {root}
       +-- Enable
       +-- AverageRadius
       +-- Temperature

  Signal choices:

    Enable
        0 Disabled
        1 Enabled

  ------------------------------------------------------------------------
```

#### The list subcommand

Print all information of a given database in a human readable format.
This is very similar to the \"dump\" subcommand, but the output is less
pretty, slightly more comprehensive and easier to parse by shell
scripts:

``` bash
$ python3 -m cantools list -a tests/files/dbc/motohawk.dbc
ExampleMessage:
  Comment[None]: Example message used as template in MotoHawk models.
  Frame ID: 0x1f0 (496)
  Size: 8 bytes
  Is extended frame: False
  Signals:
    Enable:
      Type: Integer
      Start bit: 7
      Length: 1 bits
      Unit: -
      Is signed: False
      Named values:
        0: Disabled
```

#### The generate C source subcommand

Generate [C]{.title-ref} source code from given database.

The generated code contains:

-   Message
    [structs](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk.h#L58).
-   Message
    [pack](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk.h#L88)
    and
    [unpack](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk.h#L102)
    functions.
-   Signal
    [encode](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk.h#L116)
    and
    [decode](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk.h#L125)
    functions.
-   Frame id, length, type, cycle time and signal choices
    [defines](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk.h#L42).

Known limitations:

-   The maximum signal size is 64 bits, which in practice is never
    exceeded.

Below is an example of how to generate C source code from a database.
The database is `tests/files/dbc/motohawk.dbc`.

``` text
$ python3 -m cantools generate_c_source tests/files/dbc/motohawk.dbc
Successfully generated motohawk.h and motohawk.c.
```

See
[motohawk.h](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk.h)
and
[motohawk.c](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk.c)
for the contents of the generated files.

In this example we use `--use-float` so floating point numbers in the
generated code are single precision (`float`) instead of double
precision (`double`).

``` text
$ python3 -m cantools generate_c_source --use-float tests/files/dbc/motohawk.dbc
Successfully generated motohawk.h and motohawk.c.
```

In the next example we use `--database-name` to set a custom namespace
for all generated types, defines and functions. The output file names
are also changed by this option.

``` text
$ python3 -m cantools generate_c_source --database-name my_database_name tests/files/dbc/motohawk.dbc
Successfully generated my_database_name.h and my_database_name.c.
```

See
[my_database_name.h](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/my_database_name.h)
and
[my_database_name.c](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/my_database_name.c)
for the contents of the generated files.

In the next example we use `--no-floating-point-numbers` to generate
code without floating point types, i.e. `float` and `double`.

``` text
$ python3 -m cantools generate_c_source --no-floating-point-numbers tests/files/dbc/motohawk.dbc
Successfully generated motohawk.h and motohawk.c.
```

See
[motohawk_no_floating_point_numbers.h](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk_no_floating_point_numbers.h)
and
[motohawk_no_floating_point_numbers.c](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk_no_floating_point_numbers.c)
for the contents of the generated files.

In the last example `--node` is used to generate message pack functions
only for messages sent by the specified node and unpack functions only
for messages with its signal receivers belonging to that node.

``` text
$ cantools generate_c_source tests/files/dbc/motohawk.dbc --node PCM1
Successfully generated motohawk.h and motohawk.c.
```

See
[motohawk_sender_node.h](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk_sender_node.h)
and
[motohawk_sender_node.c](https://github.com/eerimoq/cantools/blob/master/tests/files/c_source/motohawk_sender_node.c)
for the contents of the generated files.

Other C code generators:

-   <http://www.coderdbc.com>
-   <https://github.com/howerj/dbcc>
-   <https://github.com/lonkamikaze/hsk-libs/blob/master/scripts/dbc2c.awk>
-   <https://sourceforge.net/projects/comframe/>

#### The monitor subcommand

Monitor CAN bus traffic in a text based user interface.

``` text
$ python3 -m cantools monitor tests/files/dbc/motohawk.dbc
```

![image](https://github.com/cantools/cantools/raw/master/docs/monitor.png)

The menu at the bottom of the monitor shows the available commands.

-   Quit: Quit the monitor. Ctrl-C can be used as well.
-   Filter: Only display messages matching given regular expression.
    Press \<Enter\> to return to the menu from the filter input line.
-   Play/Pause: Toggle between playing and paused (or running and
    freezed).
-   Reset: Reset the monitor to its initial state.

# Contributing

1.  Fork the repository.

2.  Install prerequisites.

    ``` text
    python3 -m pip install -r requirements.txt
    ```

3.  Implement the new feature or bug fix.

4.  Implement test case(s) to ensure that future changes do not break
    legacy.

5.  Run the tests.

    ``` text
    make test
    ```

6.  Create a pull request.