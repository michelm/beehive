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
	'waf clean export --export-to=makefile,codeblocks'

Note that a clean is required in order for the export function to work.

"""

from waflib import Build, Logs, Scripting, Task
from wafexport import makefile
from wafexport import codeblocks


def options(opt):
	opt.add_option('--export-to', 
		dest='export_to', 
		default='makefile', 
		action='store', 
		help='export waf C/C++ components to etxternal formats, e.g. makefile, codeblocks (default=makefile)')


class ExportContext(Build.BuildContext):
	'''exports and converts projects into other formats (e.g. Makefiles).'''
	fun = 'build'
	cmd = 'export'
	exporters = ('all', 'makefile', 'codeblocks')

	def execute(self, *k, **kw):
		self.export_to = self.options.export_to.split(',')
		Logs.info('executing: %s --export-to=%s' % (self.cmd, ','.join(self.export_to)))
		exporters = ExportContext.exporters
		if not (set(self.export_to) & set(exporters)):
			msg = 'Invalid export format(s); '
			msg += 'selected(%s), supported(%s)' % (','.join(self.export_to), ','.join(exporters))
			self.fatal(msg)

		# install special task.exec_command that will store the actual
		# command that has been executed (self.command_executed) as well 
		# as the working directory (self.path)
		old_exec = Task.TaskBase.exec_command
		def exec_command(self, *k, **kw):
			ret = old_exec(self, *k, **kw)
			try:
				cmd = k[0]
			except IndexError:
				cmd = ''
			finally:
				self.command_executed = cmd
			try:
				cwd = kw['cwd']
			except KeyError:
				cwd = self.generator.bld.cwd
			finally:
				self.path = cwd
			return ret
		Task.TaskBase.exec_command = exec_command

		# install special task.process that will process/convert the stored
		# executed command srting and working directory
		old_process = Task.TaskBase.process
		def process(self):
			old_process(self)
			makefile.process(self)
			codeblocks.process(self)
		Task.TaskBase.process = process

		# install post process that will export the processed and converted
		# task data into the requested export format.
		def postfun(self):
			makefile.postfun(self)
			codeblocks.postfun(self)
		super(ExportContext, self).add_post_fun(postfun)

		# remove previous build results
		Scripting.run_command('clean')

		# initialize exporters		
		makefile.init(self)
		codeblocks.init(self)

		# start export
		super(ExportContext, self).execute(*k, **kw)



