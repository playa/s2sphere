#!/usr/bin/env python

'''Parse C++ header files to convert their comments into rst.'''

import argparse
import glob
import re


COMMENT_TAGS = ('//', '/*', ' *')


rst_header_template = '''.. _cpp:

.. This file is autogenerated using `python extract_from_cpp.py`.


C++ API
=======

This is the API documentation of the original
`S2 geometry library <https://code.google.com/p/s2-geometry-library/>`_
extracted from its source code and included here for reference.

'''

class_template = '''
.. cpp:class:: {name}

{description}
'''

method_template = '''
.. cpp:function:: {name}

{description}
'''

type_template = '''
.. cpp:type:: {name}

{description}
'''


function_re = re.compile(
    '([A-Z][a-zA-Z0-9]+|int|double|bool|void|const)[\*&]{0,2} '
    '[a-z_A-Z0-9]+\(.*\).*[;\{]')
function_re_partial = re.compile(
    '([A-Z][a-zA-Z0-9]+|int|double|bool|void|const)[\*&]{0,2} '
    '[a-z_A-Z0-9]+\(')

special_cases = {
    '//  // is the planar centroid, which is simply the centroid of '
    'the ordinary':
    '// is the planar centroid, which is simply the centroid of '
    'the ordinary',

    '// ----------------': '// ',

    '//  (3) RobustCrossing(a,b,c,d) <= 0 if a==b or c==d':
    '//  (4) RobustCrossing(a,b,c,d) <= 0 if a==b or c==d',

    '//  (3) If exactly one of a,b equals one of c,d, then exactly one of':
    '//  (4) If exactly one of a,b equals one of c,d, then exactly one of',

    '// to be different than vertex(*next_vertex), so this will never '
    'result in':
    '// to be different than `vertex(*next_vertex)`, so this will never '
    'result in',

    '// Return true if lng_.lo() > lng_.hi(), i.e. the rectangle crosses':
    '// Return true if `lng_.lo() > lng_.hi()`, i.e. the rectangle crosses',
}


def extract(files, outfile):
    with open(outfile, 'w') as o:
        o.write(rst_header_template)
        for in_file in files:
            with open(in_file, 'r') as i:
                extract_file(i, o)


def extract_file(in_file, out_file):
    indent = 0
    cached_lines = []
    partial_function = ''
    is_private = False
    for line in in_file:
        while (len(line) > 1 and indent and
               not line.startswith(' ' * indent) and
               'public:' not in line and
               'private:' not in line and
               'protected:' not in line):
            indent -= 2
            is_private = False
        line = line[indent:]
        if line.startswith(('rivate:', 'rotected:')):
            is_private = True
        if line.startswith('ublic:'):
            is_private = False
        if is_private:
            continue

        line = line.rstrip()

        if line in special_cases:
            line = special_cases[line]

        if line.strip().startswith(COMMENT_TAGS):
            cached_lines.append(line)
            continue

        if line.startswith('class') and '{' in line:
            name = line[6:]
            if '{' in name:
                name, _, _ = name.partition('{')
            name = name.replace(';', '')
            name = name.strip()
            formatter = Formatter(indent)
            txt = class_template.format(
                name=name,
                description=formatter.comment(cached_lines),
            )
            for l in txt.splitlines():
                out_file.write((' ' * indent + l).rstrip() + '\n')
            indent += 2
        elif line.startswith('typedef') and line.endswith(';'):
            name = line[8:]
            name = name.replace(';', '')
            name = name.strip()
            formatter = Formatter(indent)
            txt = type_template.format(
                name=name,
                description=formatter.comment(cached_lines),
            )
            for l in txt.splitlines():
                out_file.write((' ' * indent + l).rstrip() + '\n')
            indent += 2
        elif line.startswith('template') and ('(' in line or '{' in line):
            name = line
            if '{' in name:
                name, _, _ = name.partition('{')
            name = name.replace(';', '')
            name = name.replace('> class ', '> ')
            name = name.replace('> struct ', '> ')
            name = name.strip()
            formatter = Formatter(indent)
            txt = class_template.format(
                name=name,
                description=formatter.comment(cached_lines),
            )
            for l in txt.splitlines():
                out_file.write((' ' * indent + l).rstrip() + '\n')
            indent += 2
        elif function_re.search(partial_function + line.strip()) is not None:
            name = partial_function + line.strip()
            if '//' in name:
                name, _, comment = name.partition('//')
                cached_lines.append('// ' + comment)
            if '{' in name:
                name, _, _ = name.partition('{')
            name = name.replace(';', '')
            name = name.strip()
            formatter = Formatter(indent)
            txt = method_template.format(
                name=name,
                description=formatter.comment(cached_lines),
            )
            for l in txt.splitlines():
                out_file.write((' ' * indent + l).rstrip() + '\n')
        elif function_re_partial.search(line) is not None:
            partial_function = line + ' '
            continue

        partial_function = ''
        if line:
            cached_lines = []


class Formatter(object):
    def __init__(self, indent=0):
        self.indent = indent

    def strip_comment_tags(self, line):
        return (
            line
            .replace('// ', '')
            .replace('//', '')
            .replace('/* ', '')
            .replace('/*', '')
            .replace(' * ', '')
            .replace(' *', '')
        )

    def detect_block(self, lines):
        inside_block = False
        inside_list = False  # unnumbered lists and numbered lists
        processed = []

        for l in lines:
            processed.append(l)

            # whitelist lists
            if inside_list:
                if l.startswith(' ') or len(l) <= 1 or \
                   '. ' in l[:5] or ') ' in l[:5]:
                    continue
                else:
                    inside_list = False
                    processed.insert(-1, '')
            if l.startswith((' -', '-', ' 1.', '1.', ' (1)', '(1)')):
                inside_list = True
                if len(processed) > 1 and processed[-2]:
                    processed.insert(-1, '')
                continue

            if inside_block:
                if l.startswith(' ') or not l or l.endswith(';'):
                    pass
                else:
                    inside_block = False
                    processed.insert(-1, '')
            elif (l.startswith('  ') or (l.endswith(';') and
                                         processed[-3].endswith(':')) or
                  (l.startswith(' ') and l.endswith(';'))):
                inside_block = True
                if len(processed) > 1 and processed[-2]:
                    processed.insert(-1, '')
                processed.insert(-1, '.. code-block:: cpp')
                processed.insert(-1, '')

            # ensure code-block indent
            if inside_block and not l.startswith('  '):
                processed[-1] = '  ' + processed[-1]

        return processed

    def comment(self, lines):
        processed = [self.strip_comment_tags(l) for l in lines]
        processed = self.detect_block(processed)
        return '\n'.join((' ' * 2) + l for l in processed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-i', '--inputs',
                        default='../../tests/s2-geometry/geometry/s2/*.h',
                        help='glob expression for input files')
    parser.add_argument('-o', '--output', default='cpp.rst',
                        help='output rst file')
    args = parser.parse_args()

    extract(glob.glob(args.inputs), args.output)