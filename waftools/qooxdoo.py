#! /usr/bin/env python
# -*- encoding: utf-8 -*-
# Michel Mooij, michel.mooij7@gmail.com

"""

Tool Description
================
This module provides a waf wrapper (i.e. waftool) around the javascript web 
framework 'qooxdoo'.

See http://http://qooxdoo.org// for more information on the qooxdoo framework
itself. 


Usage
=====
In order to use this waftool simply add it to the 'options' and 'configure' 
functions of your main waf script as shown in the example below:

	def options(opt):
		opt.load('qooxdoo', tooldir='./waftools')

	def configure(conf):
		conf.load('qooxdoo')
		
Note that the example shown above assumes that the qooxdoo waftool is located 
in the sub directory named 'waftools'.

In the build function of the wscript add a build task containing the 'qooxdoo'
feature as shown below:

	def build(bld):
		tgen = bld(
			name='web-desktop', 
			features='qooxdoo', 
			cwd='desktop', 
			install_path = '${PREFIX}/var/www/')
		tgen.qooxdoo_clean()

Where 'web-desktop' is the unique build task name within the waf build system, 
'desktop' is the top level directory of the qooxdoo web application (containing
the generate.py script) and '${PREFIX}/var/www/' is the location to store the 
resulting web pages. 

	.
	├── desktop		<-- qooxdoo application directory
	│   ├── config.json
	│   ├── generate.py
	│   ├── Manifest.json
	│   ├── readme.txt
	│   └── source
	│       ├── class
	│       ├── index.html
	│       ├── resource
	│       └── translation
	│
	└── wscript		<-- build script containing the qooxdoo taskgen

Note that a special call 'qooxdoo_clean()' is required for build task in order 
to call a 'generate.py clean' when calling the waf clean command.
"""

import sys
from waflib import Task,TaskGen

def options(opt):
	opt.add_option('--qooxdoo-cmd', dest='qooxdoo_cmd', default=None, action='store', help='qooxdoo generate.py <command>.')
	opt.add_option('--qooxdoo-skip', dest='qooxdoo_skip', default=False, action='store_true', help='skip qooxdoo tasks (default=False).')

def configure(conf):
	if conf.options.qooxdoo_skip:
		conf.env.QOOXDOO_SKIP = [True]

class qooxdoo(Task.Task):
	def run(self):
		src = self.inputs[0].abspath()
		tgt = self.outputs[0].abspath()
		cmd = "python %s %s -I -l %s" % (src, self.cmd, tgt)
		return self.exec_command(cmd)

@TaskGen.feature('qooxdoo')
def qooxdoo_generate(self):
	if len(self.bld.env.QOOXDOO_SKIP) or self.bld.options.qooxdoo_skip:
		return
	cmd = 'build'
	if self.bld.options.qooxdoo_cmd:
		cmd = self.bld.options.qooxdoo_cmd
	elif 'NDEBUG' not in self.bld.env.DEFINES:
		cmd = 'source-all'

	name, top, source = _qooxdoo_get_attributes(self)

	dependencies = []
	dependencies += top.ant_glob('*.json')
	dependencies += top.ant_glob('source/class/**/*.js')
	dependencies += top.ant_glob('source/translation/**/*')
	dependencies += top.ant_glob('source/resource/**/*')
	for depends in dependencies:
		self.bld.add_manual_dependency(source,depends)

	target = self.path.get_bld().find_or_declare('%s-%s.log' % (name, cmd))
	task = self.create_task('qooxdoo', src=source, tgt=target)
	task.cwd = top
	task.cmd = cmd

	if _qooxdoo_selected(self, name):
		_qooxdoo_install(self)

@TaskGen.taskgen_method
def qooxdoo_clean(self):
	if not self.bld.cmd.startswith('clean'):
		return

	name, top, source = _qooxdoo_get_attributes(self)

	if not _qooxdoo_selected(self,name):
		return

	try:
		targets = self.path.get_bld().ant_glob('%s-*.log' % name)
	except OSError:
		return
	else:
		if len(targets):
			cmd = "python %s clean" % source.abspath()
			self.bld.exec_command(cmd)

def _qooxdoo_selected(self, name):
	targets = self.bld.targets
	return not len(targets) or name in targets.split(',')

def _qooxdoo_get_attributes(self):
	name = self.get_name()
	script = '%s/wscript' % self.path.abspath()

	cwd = getattr(self, 'cwd', None)
	if not cwd:
		self.bld.fatal("'cwd' not specified. task='%s', script='%s'" % (name, script))

	top = self.path.find_dir(cwd)
	if not top:
		self.bld.fatal("cwd='%s' does not exist. task='%s', script='%s'" % (cwd, name, script))

	source = top.find_resource('generate.py')
	if not source:
		self.bld.fatal("qooxdoo generate.py not found in '%s'. task='%s', script='%s'" % (top.abspath(), name, script))
	return (name, top, source)

def _qooxdoo_install(self):
	name, top, source = _qooxdoo_get_attributes(self)

	dst = getattr(self, 'install_path', None)
	if not dst:
		return

	if 'NDEBUG' in self.bld.env.DEFINES:
		cwd = top.find_dir('build')
	else:
		cwd = top.find_dir('source')

	if cwd:
		src = cwd.ant_glob('index.html') + cwd.ant_glob('script/*.*') + cwd.ant_glob('resource/**/*.*')
		inst = self.bld.install_files(dst, src, cwd=cwd, relative_trick=True)
		if inst:
			for task in self.tasks:
				inst.set_run_after(task)

