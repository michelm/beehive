#! /usr/bin/env python
# -*- encoding: utf-8 -*-

'''This module contains an export formatter for converting C/C++ tasks
into makefiles.
'''

import os, datetime
from waflib import Logs, Node, Context

def init(bld):
	'''initalizes the makefile export formatter'''
	if not _selected(bld):
		return
	bld.makefile_commands = []
	bld.makefile_targets = []


def process(task):
	'''(pre)processes and prepares the commands being executed per task into 
	makefile targets and makefile commands.
	'''
	bld = task.generator.bld
	if not _selected(bld):
		return
	name = task.__class__.__name__
	if name in ('c','cxx'):
		_compile_task(task)
	elif name in ('cprogram', 'cshlib', 'cstlib', 'cxxprogram', 'cxxshlib', 'cxxstlib'):
		_link_task(task)


def postfun(bld):
	'''combines all preprocessed makefile targets and commands of all tasks
	into a single makefile.
	'''
	if not _selected(bld):
		return
	_export_makefile(bld)


def _selected(bld):
	'''returns True when this export formatter has been selected.'''
	return (set(bld.export_to) & set(['all','makefile']))


def _compile_task(task):
	'''converts a compile task into a makefile target.'''
	bld = task.generator.bld
	top = bld.bldnode.path_from(bld.path)
	
	# create a list of makefile targets
	lst = ["%s/%s" % (top, o.relpath()) for o in task.outputs]
	bld.makefile_targets.extend(lst)

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
	except Exception as e:
		bld.export_exception = (__file__, e, task)
	else:
		target = lst.pop(0)
		bld.makefile_commands.append('%s:' % target)
		bld.makefile_commands.append('\tmkdir -p %s' % os.path.dirname(target))
		bld.makefile_commands.append('\t%s' % task.command_executed)


def _link_task(task):
	'''converts a link task into a makefile target.'''
	bld = task.generator.bld
	top = bld.bldnode.path_from(bld.path)

	# create list of targets
	lst = ["%s/%s" % (top, o.relpath()) for o in task.outputs]
	bld.makefile_targets.extend(lst)

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
		bld.export_exception = (__file__, e, task)
	else:
		bld.makefile_commands.append('%s: \\' % os.path.basename(str(lst.pop(0))))
		bld.makefile_commands.append('\t%s' % ' \\\n\t'.join([str(l) for l in lst]))
		bld.makefile_commands.append('\t%s' % task.command_executed)


def _export_makefile(bld):
	targets = list(bld.makefile_targets)
	if not len(targets):
		return

	bindir = str(bld.env.BINDIR)
	libdir = str(bld.env.LIBDIR)
	lines = []

	tgt = [t for t in targets if not t.endswith('.dll.a')]
	tgt = [t if t.endswith('.o') else os.path.basename(t) for t in tgt]
	lines.append("all: \\")
	lines.append("\t%s" % ' \\\n\t'.join(tgt))

	lines.append("")
	lines.append("clean:")
	for tgt in targets:
		lines.append("\trm -rf  %s" % tgt)

	lines.append("")
	lines.append("install:")
	lines.append("\tmkdir -p %s" % bindir)
	lines.append("\tmkdir -p %s" % libdir)
	for t in [t for t in targets if t.split('.')[-1] not in ('a','o','so')]:
		lines.append("\tcp %s  %s/%s" % (t, bindir, os.path.basename(t)))
	for t in [t for t in targets if t.endswith('so')]:
		lines.append("\tcp %s  %s/%s" % (t, libdir, os.path.basename(t)))

	lines.append("")
	lines.append("uninstall:")
	for t in [t for t in targets if t.split('.')[-1] not in ('a','o','so')]:
		lines.append("\trm -rf  %s/%s" % (bindir, os.path.basename(t)))
	for t in [t for t in targets if t.endswith('so')]:
		lines.append("\trm -rf  %s/%s" % (libdir, os.path.basename(t)))

	for cmd in bld.makefile_commands:
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
	header += "PREFIX=%s\n" % prefix
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


	


