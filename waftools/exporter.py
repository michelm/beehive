#! /usr/bin/env python
# -*- encoding: utf-8 -*-
# Michel Mooij, michel.mooij7@gmail.com

"""
Tool Description
================
This waftool can be used for the export and conversion of C/C++ task into
one of the following:
	- Makefile
	- Codeblocks

Makefile
--------
When exporting to a Makefile all C/C++ tasks will be exported into one single
makefile using all the compiler and linker directives as defined within the
waf build environment. All tasks will be build and installed in the same
location as they would when using the waf build environment. 
The makefile support following arguments:
	'make all'
	'make clean'
	'make install'
	'make uninstall'
	'make <target>'

Note that the makefile will use the PREFIX variable allowing the users to
specify a different install location, for example:
	'make install PREFIX=/home/john'

Codeblocks
----------
When exporting to codeblocks a project file will be created for each C/C++ link
task (i.e. programs, static- and shared libraries). Dependencies between 
projects will be stored in a single codeblocks workspace file. Both the 
resulting workspace and project files will be stored in a codeblocks directory
located in the top level directory of your waf build environment.

REMARK
Note that codeblocks files uses absolute paths and so can be run from any 
location, but you will have to regenerate the files whenever the location of your
waf build environment and/or install location has changed.

Usage
=====
In order for this waftool to work a special export function must be added to
each single wscript within your waf build environment as presented in the 
example below:

	.
	├── hello
	│   ├── hello.c
	│   └── wscript	-->	│#!/usr/bin/env python
	│					│
	│					│def export(bld):
	│					│	build(bld)
	│					│
	│					│def build(bld):
	│					│	bld.program(target='hello', source='hello.c')
	│					└────────────────────────────────────────────────
	│
	├── skipme
	│   └── wscript -->	│#!/usr/bin/env python
	│					│
	│					│def export(bld):
	│					│	pass
	│					│
	│					│def build(bld):
	│					│	bld(rule='touch $TGT', target='skipme')
	│					└────────────────────────────────────────────────
	│
	├── bar.c
	├── wscript		-->	│#!/usr/bin/env python
	│					│
	│					│def options(opt):
	│					│	opt.load('exporter')
	│					│
	│					│def configure(conf):
	│					│	conf.load('exporter')
	│					│
	│					│def build(bld):
	│					│	bld.program(target='foo', source='bar.c')
	│					│	bld.recurse('hello')
	│					│	bld.recurse('skipme')
	│					│
	│					│def export(bld):
	│					│	exporter.execute(build, bld)
	│					└────────────────────────────────────────────────
	│
	├── Makefile	<-- exported makefile
	└── codeblocks	<-- exported codeblocks project files

Note that if the export should be skipped for specific wscript file you can 
also use an empty export function, containing only a pass statement.

To actually trigger the export use the following command:
	'waf clean export --export-makefile'

Note that a clean is required in order for the export function to work.

"""

from waflib import Build, Logs, Scripting
from wafexport import makefile
from wafexport import codeblocks

def options(opt):
	opt.add_option('--export-makefile', dest='export_makefile', default=False, action='store_true', help='export waf c/c++ components to a makefile.')
	opt.add_option('--export-codeblocks', dest='export_codeblocks', default=False, action='store_true', help='export waf c/c++ components to codeblocks projects.')

class Exporter(Build.BuildContext):
	'''export and convert waf project data (components) into the requested format (e.g. to a Makefile).'''
	fun = 'export'
	cmd = 'export'

def execute(build, bld):
	'''performs a clean build and passes the resulting build context to the selected export module.
	'''
	if bld.options.export_makefile:
		pass
	elif bld.options.export_codeblocks:
		pass
	else:
		bld.fatal('no export format selected!')
	
	Scripting.run_command("clean")
	build(bld)

	if bld.options.export_makefile:
		makefile.export(bld)
	elif bld.options.export_codeblocks:
		codeblocks.export(bld)


