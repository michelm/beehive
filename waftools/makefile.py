#! /usr/bin/env python
# -*- encoding: utf-8 -*-

"""
Tool Description
================
This waftool can be used for the export and conversion of all C/C++ tasks 
defined within a waf project into a single Makefile. 

When using the makefile all targets will be build and installed into the 
same location and using the same compiler and linker directives as they 
would have when using the waf build environment. 

The generated makefile supports following arguments:
	'make all'
	'make clean'
	'make install'
	'make uninstall'
	'make <target>'

Based on the example shown below, in which two build environments exist (one 
for native host compilation and one for cross-compilation for win32 targets),
two makefiles will be generated. The makefile for the native environment will
be named 'MakeFile' while the makefile for the cross compilation environment 
(i.e. being an variant) will be named; appname-variant.mk.

	.
	├── hello
	│   ├── hello.c
	│   └── wscript	-->	│#!/usr/bin/env python
	│					│
	│					│def build(bld):
	│					│	bld.program(target='hello', source='hello.c')
	│					└────────────────────────────────────────────────
	│
	├── bar.c
	├── wscript		-->	│#!/usr/bin/env python
	│					│
	│					│APPNAME='hello'
	│					│
	│					│def options(opt):
	│					│	opt.load('makefile')
	│					│	...
	│					│
	│					│def configure(conf):
	│					│	conf.setenv('win32')
	│					│	conf.load('makefile')
	│					│	...
	│					│	conf.setenv('')
	│					│	conf.load('makefile')
	│					│	...
	│					│
	│					│def build(bld):
	│					│	bld.program(target='foo', source='bar.c')
	│					│	bld.recurse('hello')
	│					└────────────────────────────────────────────────
	│
	├── Makefile		<-- exported makefile
	└── hello-win32.mk	<-- makefile for the variant named 'win32'

Remarks
-------
This module will ALLWAYS first remove any results from a previous build, i.e. 
it will allways start with a 'waf clean', after which a normal build will be 
started, during which the C/C++ tasks will be converted and exported. 

Usage
=====
In order to use this tool add the following to the 'options' and 'configure'
functions of the top wscript in the waf build environment:

	options(opt):
		opt.load('makefile')

	configure(conf):
		conf.load('makefile')

In order to generate the makefile issue the following command:
	'waf makefile'
Or
	'waf makefile_<variant>'

Once the makefile has been generated it can be used 'as-is' without using waf, for
example:
	'make -f hello-win32.mk PREFIX=~/win32'

Will start a cross-compilation build for the win32 environment using '~/win32'
as the installation root.
"""

import os, re, datetime
from waflib import Build, Logs, Scripting, Task, Node, Context

def options(opt): pass
def configure(conf): pass


def makefile_process(task):
	'''(pre)processes and prepares the commands being executed per task into 
	makefile targets and makefile commands.
	'''
	name = task.__class__.__name__
	if name in ('c','cxx'):
		makefile_compile(task)
	elif name in ('cprogram', 'cshlib', 'cstlib', 'cxxprogram', 'cxxshlib', 'cxxstlib'):
		makefile_link(task)


def makefile_compile(task):
	'''converts a compile task into a makefile target.'''
	bld = task.generator.bld
	top = bld.bldnode.path_from(bld.path)
	
	# create a list of makefile targets
	lst = ["%s/%s" % (top, o.relpath()) for o in task.outputs]
	bld.targets.extend(lst)

	# convert command_executed into a makefile command	
	try:
		if isinstance(task.command_executed, list):
			t = bld.path.abspath()
			inc = "-I%s" % t
			cmd = []
			for c in task.command_executed:
				if c.startswith(inc):
					c = "-I%s" % c[len(inc)+1:]
				elif c.startswith('../'):
					c = c.lstrip('../')
				if c.endswith('.o'):
					c = "%s/%s" % (top, c)
				cmd.append(c)
			task.command_executed = ' \\\n\t'.join(cmd)
	except Exception as exception:
		bld.export_exception = (exception, task, task.command_executed)
	else:
		target = lst.pop(0)
		bld.commands.append('%s:' % target)
		bld.commands.append('\tmkdir -p %s' % os.path.dirname(target))
		bld.commands.append('\t%s' % task.command_executed)


def makefile_link(task):
	'''converts a link task into a makefile target.'''
	bld = task.generator.bld
	top = bld.bldnode.path_from(bld.path)

	# create list of targets
	lst = ["%s/%s" % (top, o.relpath()) for o in task.outputs]
	bld.targets.extend(lst)

	# create list of dependencies
	deps = task.inputs + task.dep_nodes + bld.node_deps.get(task.uid(), [])
	lst += ["%s/%s" % (top, d.relpath()) for d in deps]

	# remove dll import libs (.dll.a); not needed when linking with gcc
	lst = [l for l in lst if not l.endswith('.dll.a')]

	# convert command_executed into a makefile command	
	try:
		if isinstance(task.command_executed, list):
			t = bld.path.abspath()
			cmd = []
			for c in task.command_executed:
				if c.startswith('../'):
					c = c.lstrip('../')
				elif c.startswith(t):
					c = c[len(t)+1:]
				if c.startswith('-L'):
					c = "-L%s/%s" % (top, c[2:])
				elif c.startswith('-Wl,--out-implib,'):
					c = '-Wl,--out-implib,%s/%s' % (top, c.split(',')[2])
				elif c.endswith('.a') or c.endswith('.o'):
					c = "%s/%s" % (top, c)
				cmd.append(c)
			task.command_executed = ' \\\n\t'.join(cmd)
	except Exception as e:
		bld.export_exception = (exception, task, task.command_executed)
	else:
		bld.commands.append('%s: \\' % os.path.basename(str(lst.pop(0))))
		bld.commands.append('\t%s' % ' \\\n\t'.join([str(l) for l in lst]))
		bld.commands.append('\t%s' % task.command_executed)


def makefile_show_failure(bld):
	(err, tsk, cmd) = bld.failure
	msg = "export failure:\n"
	msg += " tsk='%s'\n" % (str(tsk).replace('\n',''))
	msg += " err='%r'\n" % (err)
	msg += " cmd='%s'\n" % ('\n     '.join(cmd))
	bld.fatal(msg)


def makefile_export(bld):
	bindir = str(bld.env.BINDIR)
	libdir = str(bld.env.LIBDIR)
	lines = []

	# makefile 'all'
	tgt = [t for t in bld.targets if not t.endswith('.dll.a')]
	tgt = [t if t.endswith('.o') else os.path.basename(t) for t in tgt]
	lines.append("all: \\")
	lines.append("\t%s" % ' \\\n\t'.join(tgt))

	# makefile 'clean'
	lines.append("")
	lines.append("clean:")
	for tgt in bld.targets:
		lines.append("\trm -rf  %s" % tgt)

	# makefile 'install'
	lines.append("")
	lines.append("install:")
	lines.append("\tmkdir -p %s" % bindir)
	lines.append("\tmkdir -p %s" % libdir)
	for t in [t for t in bld.targets if t.split('.')[-1] not in ('a','o','so')]:
		lines.append("\tcp %s  %s/%s" % (t, bindir, os.path.basename(t)))
	for t in [t for t in bld.targets if t.endswith('so')]:
		lines.append("\tcp %s  %s/%s" % (t, libdir, os.path.basename(t)))

	# makefile 'uninstall'
	lines.append("")
	lines.append("uninstall:")
	for t in [t for t in bld.targets if t.split('.')[-1] not in ('a','o','so')]:
		lines.append("\trm -rf  %s/%s" % (bindir, os.path.basename(t)))
	for t in [t for t in bld.targets if t.endswith('so')]:
		lines.append("\trm -rf  %s/%s" % (libdir, os.path.basename(t)))

	# makefile <task.name>
	for cmd in bld.commands:
		if not cmd.startswith('\t'):
			lines.append("")
		lines.append(cmd)
	lines.append("\t\n")

	prefix = str(bld.env.PREFIX)
	appname = getattr(Context.g_module, Context.APPNAME, os.path.basename(bld.srcnode.abspath()))
	version = getattr(Context.g_module, Context.VERSION, os.path.basename(bld.srcnode.abspath()))
	header  = "# This makefile has been generated by waf.\n"
	header += "#\n"
	header += "# project : %s\n" % appname
	header += "# version : %s\n" % version
	header += "# waf     : %s\n" % Context.WAFVERSION
	header += "# time    : %s\n" % datetime.datetime.now()
	header += "#\n"
	header += "SHELL=/bin/sh\n"
	header += "PREFIX=%s\n" % re.sub('\A/home/.*/', '~/', prefix)
	header += "\n"
	content = "\n".join(lines)
	content = content.replace(prefix, "$(PREFIX)")

	if bld.variant:
		name = '%s-%s.mk' % (appname, bld.variant)
	else:
		name = 'Makefile'
	node = bld.path.make_node(name)
	node.write(header + content)
	Logs.warn('exported: %s' % node.abspath())


class MakefileContext(Build.BuildContext):
	'''exports and converts C/C++ tasks to MakeFile(s).'''
	fun = 'build'
	cmd = 'makefile'

	def execute(self, *k, **kw):
		self.failure = None
		self.commands = []
		self.targets = []

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
			makefile_process(self)
		Task.TaskBase.process = process

		# install post process that will export the processed and converted
		# task data into the requested export format.
		def postfun(self):
			if self.failure:
				makefile_show_failure(self)
			elif not len(self.targets):
				Logs.warn('makefile export failed: no suitable C/C++ targets found')
			else:
				makefile_export(self)
		super(MakefileContext, self).add_post_fun(postfun)

		# remove results form previous build (if any)
		Scripting.run_command('clean')

		# start export
		super(MakefileContext, self).execute(*k, **kw)

