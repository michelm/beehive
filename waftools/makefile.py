#! /usr/bin/env python
# -*- encoding: utf-8 -*-
# Michel Mooij, michel.mooij7@gmail.com

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
functions of the top level wscript in the waf build environment:

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

def options(opt):
	pass

def configure(conf): 
	pass

class MakefileContext(Build.BuildContext):
	'''exports and converts C/C++ tasks to MakeFile(s).'''
	fun = 'build'
	cmd = 'makefile'

	def execute(self, *k, **kw):
		self.failure = None
		self.commands = []
		self.targets = []

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

		old_process = Task.TaskBase.process
		def process(self):
			old_process(self)
			makefile_process(self)
		Task.TaskBase.process = process

		def postfun(self):
			if self.failure:
				makefile_show_failure(self)
			elif not len(self.targets):
				Logs.warn('makefile export failed: no suitable C/C++ targets found')
			else:
				makefile_export(self)
		super(MakefileContext, self).add_post_fun(postfun)

		Scripting.run_command('clean')
		super(MakefileContext, self).execute(*k, **kw)


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
	'''converts a compile task into a makefile target.

	extends list of makefile targets, converts the executed task command into
	a makefile command and appends it to the list of makefile commands
	'''
	bld = task.generator.bld
	top = bld.bldnode.path_from(bld.path)	
	lst = ["%s/%s" % (top, o.relpath()) for o in task.outputs]
	bld.targets.extend(lst)

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
		bld.failure = (exception, task, getattr(task,"command_executed",[]))
	else:
		target = lst.pop(0)
		bld.commands.append('%s:' % target)
		bld.commands.append('\tmkdir -p %s' % os.path.dirname(target))
		bld.commands.append('\t%s' % task.command_executed)


def makefile_link(task):
	'''converts a link task into a makefile target.

	extends list of makefile targets, converts the executed task command into
	a makefile command and appends it to the list of makefile commands
	
	also add dependencies to external task (e.g. object, shared libraries), but 
	excludes import libraries (ending with .dll.a).
	'''
	bld = task.generator.bld
	top = bld.bldnode.path_from(bld.path)
	lst = ["%s/%s" % (top, o.relpath()) for o in task.outputs]
	bld.targets.extend(lst)

	deps = task.inputs + task.dep_nodes + bld.node_deps.get(task.uid(), [])
	lst += ["%s/%s" % (top, d.relpath()) for d in deps]
	lst = [l for l in lst if not l.endswith('.dll.a')]

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
	except Exception as exception:
		bld.failure = (exception, task, getattr(task,"command_executed",[]))
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
	appname = getattr(Context.g_module, Context.APPNAME, os.path.basename(bld.srcnode.abspath()))
	version = getattr(Context.g_module, Context.VERSION, os.path.basename(bld.srcnode.abspath()))
	prefix = str(bld.env.PREFIX)
	bindir = str(bld.env.BINDIR)
	libdir = str(bld.env.LIBDIR)
	binaries = [t for t in bld.targets if t.split('.')[-1] not in ('a','o','so')] # treat dll as binary
	libraries = [t for t in bld.targets if t.endswith('.so')]

	tgt = [t if t.endswith('.o') else os.path.basename(t) for t in bld.targets if not t.endswith('.dll.a')]
	tgt_all = " \\\n\t".join(tgt)
	tgt_clean = "\n\t".join(["rm -rf %s" % t for t in bld.targets])

	bini = ["cp %s %s/%s" % (b, bindir, os.path.basename(b)) for b in binaries]
	libi = ["cp %s %s/%s" % (l, libdir, os.path.basename(l)) for l in libraries]
	tgt_install = "\n\t".join(bini+libi)

	binu = ["rm -rf %s/%s" % (bindir, os.path.basename(b)) for b in binaries]
	libu = ["rm -rf %s/%s" % (libdir, os.path.basename(l)) for l in libraries]
	tgt_uninstall = "\n\t".join(binu+libu)

	tgt = [c if c.startswith('\t') else "\n%s" % (c) for c in bld.commands]
	targets = str("\n".join(tgt)).lstrip('\n')

	content = str(MAKEFILE_TEMPLATE)
	content = re.sub('\$\(APPNAME\)', appname, content)
	content = re.sub('\$\(VERSION\)', version, content)
	content = re.sub('\$\(WAFVERSION\)', Context.WAFVERSION, content)
	content = re.sub('\$\(DATETIME\)', str(datetime.datetime.now()), content)
	content = re.sub('\$\(PREFIX\)', re.sub('\A/home/.*?/','~/',prefix), content)
	content = re.sub('\$\(BINDIR\)', bindir, content)
	content = re.sub('\$\(LIBDIR\)', libdir, content)
	content = re.sub('\$\(TGT_ALL\)', tgt_all, content)
	content = re.sub('\$\(TGT_CLEAN\)', tgt_clean, content)
	content = re.sub('\$\(TGT_INSTALL\)', tgt_install, content)
	content = re.sub('\$\(TGT_UNINSTALL\)', tgt_uninstall, content)
	content = re.sub('\$\(TARGETS\)', targets, content)
	content = re.sub(prefix, '$PREFIX', content)

	if bld.variant:
		name = '%s-%s.mk' % (appname, bld.variant)
	else:
		name = 'Makefile'
	node = bld.path.make_node(name)
	node.write(content)
	Logs.warn('exported: %s' % node.abspath())


MAKEFILE_TEMPLATE = '''# This makefile has been generated by waf.
#
# project : $(APPNAME)
# version : $(VERSION)
# waf     : $(WAFVERSION)
# time    : $(DATETIME)
#
SHELL=/bin/sh
PREFIX=$(PREFIX)

all: \\
	$(TGT_ALL)

clean:
	$(TGT_CLEAN)

install:
	mkdir -p $(BINDIR)
	mkdir -p $(LIBDIR)
	$(TGT_INSTALL)

uninstall:
	$(TGT_UNINSTALL)

$(TARGETS)

'''


