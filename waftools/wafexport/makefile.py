#! /usr/bin/env python
# -*- encoding: utf-8 -*-

import os, datetime
from waflib import Logs, Node, Context


def init(bld):
	if not _selected(bld):
		return
	bld.makefile_commands = []
	bld.makefile_targets = []


def process(task):
	if not _selected(task.generator.bld):
		return

	Logs.warn('inp: %s' % task.inputs)
	Logs.warn('out: %s' % task.outputs)
	Logs.info('cmd: %s' % task.command_executed)

	name = task.__class__.__name__
	if name in ['c','cxx']:
		_compile_task(task)
	elif name in ['cprogram', 'cshlib', 'cstlib', 'cxxprogram', 'cxxshlib', 'cxxstlib']:
		_link_task(task)


def postfun(bld):
	if not _selected(bld):
		return
	_export_makefile(bld)


def _selected(bld):
	return (set(bld.export_to) & set(['all','makefile']))


def _compile_task(task):
	bld = task.generator.bld
	top = str(bld.bldnode.path_from(bld.path))
	lst = []
	for x in task.outputs:
		lst.append("%s/%s" % (top, x.relpath()))
	bld.makefile_targets.extend(lst)

	try:
		if isinstance(task.command_executed, list):
			t = str(bld.path.abspath())
			cmd = []
			for c in task.command_executed:
				if c.startswith('../'):
					c = c.lstrip('../')
				if c.endswith('.o'):
					c = "%s/%s" % (top, c)
				if c.startswith("-I%s" % t):
					c = "-I%s" % c[len(t)+3:]
				cmd.append(c)
			task.command_executed = ' \\\n\t'.join(cmd)
	except Exception as e:
		print(str(e))
	else:
		target = str(lst.pop(0))
		bld.makefile_commands.append('%s:' % target)
		bld.makefile_commands.append('\tmkdir -p %s' % os.path.dirname(target))
		bld.makefile_commands.append('\t%s' % task.command_executed)


def _link_task(task):
	bld = task.generator.bld
	top = str(bld.bldnode.path_from(bld.path))

	# create list of targets
	lst = ["%s/%s" % (top, o.relpath()) for o in task.outputs]
	bld.makefile_targets.extend(lst)

	# create list of dependencies
	deps = task.inputs + task.dep_nodes + bld.node_deps.get(task.uid(), [])
	lst += ["%s/%s" % (top, d.relpath()) for d in deps]

	# remove dll import libs (.dll.a); not needed when linking with gcc
	lst = [l for l in lst if not l.endswith('.dll.a')]

	try:
		if isinstance(task.command_executed, list):
			t = str(bld.path.abspath())
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
		print(str(e))
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

	tall = [t for t in targets if not t.endswith('.dll.a')]
	lines.append("all: \\")
	lines.append("\t%s" % ' \\\n\t'.join([t if t.endswith('.o') else os.path.basename(t) for t in tall]))

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

	if bld.variant:
		name = '%s-%s.mk' % (appname, bld.variant)
	else:
		name = 'Makefile'
	node = bld.path.make_node(name)
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
	node.write(header + content)
	Logs.warn('exported: %s' % node.abspath())







	


