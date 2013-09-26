#! /usr/bin/env python
# -*- encoding: utf-8 -*-
#
# TODO: detect and export cross-compile settings

import os
import xml.etree.ElementTree as ElementTree
from xml.dom import minidom
from waflib import Build, Logs, Task


def selected(bld):
	return (set(bld.export_to) & set(['all','codeblocks']))

def init(bld):
	if not selected(bld):
		return
	Logs.warn('--> codeblocks.init(%s)' % type(bld))

def process(task):
	if not selected(task.generator.bld):
		return
	Logs.warn('--> codeblocks.process(%s)' % type(task))

def postfun(bld):
	if not selected(bld):
		return
	Logs.warn('--> codeblocks.postfun(%s)' % type(bld))





#------------------------------------------------
class Component(object):
	pass

def export(bld):
	bld.components = {}

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

	def exec_task(self):
		key = self.outputs[0].abspath()
		c = Component()
		c.name = os.path.basename(key)
		c.type = self.__class__.__name__
		c.inputs = [x.abspath() for x in self.inputs]
		c.outputs = [x.abspath() for x in self.outputs]
		c.depends = [x.abspath() for x in list(self.dep_nodes + self.generator.bld.node_deps.get(self.uid(), []))]
		c.command = [str(x) for x in self.command_executed]
		c.compiler = os.path.basename(c.command[0])
		bld.components[key] = c

	old_process = Task.TaskBase.process
	def process(self):
		old_process(self)
		if self.__class__.__name__ not in ['c','cxx', 'cprogram', 'cshlib', 'cstlib', 'cxxprogram', 'cxxshlib', 'cxxstlib']:
			return
		exec_task(self)
	Task.TaskBase.process = process

	def codeblocks_project(bld, path, component):
		# determine compile options and include path
		cflags = []
		includes = []
		for key in component.inputs:
			obj = bld.components[key]
			for cmd in obj.command:
				if cmd.startswith('-I'):
					includes.append(cmd.lstrip('-I'))
				elif cmd.startswith('-') and cmd not in ['-c','-o']:
					cflags.append(cmd)
		cflags = list(set(cflags))
		includes = list(set(includes))

		# determine link options, libs and link paths
		lflags = [c for c in component.command if c.startswith('-Wl')]
		lflags = list(set(lflags))
		libs = []
		libpaths = []
		for cmd in component.command:
			if cmd.startswith('-l'):
				libs.append(cmd.lstrip('-l'))
			elif cmd.startswith('-L'):
				libpaths.append('%s/%s' % (bld.path.get_bld().abspath(), cmd.lstrip('-L')))
		libs = list(set(libs))
		libpaths = list(set(libpaths))
		depends = list(libs)

		# open existing project or create new one from template
		name = str(component.name).split('.')[0]
		fname = '%s/%s.cbp' % (path, name)
		if os.path.exists(fname):
			root = ElementTree.parse(fname).getroot()
		else:
			root = ElementTree.fromstring(_cb_project)

		# set project title
		project = root.find('Project')
		for option in project.iter('Option'):
			if option.get('title'):
				option.set('title', name)

		# define target name
		build = project.find('Build')
		title = "%s-%s" % (bld.env.DEST_OS, bld.env.DEST_CPU)

		# remove existing (similar) targets
		for target in build.findall('Target'):
			name = str(target.get('title'))
			if name.startswith(title):
				build.remove(target)				

		# inform user: add debug extension in title
		if '-ggdb' in cflags:
			title += '-debug'

		# add build target and set compiler and linker options
		target = ElementTree.fromstring(_cb_target)
		target.set('title', title)
		for option in target.iter('Option'):
			if option.get('output'):
				option.set('output', component.outputs[0])
			if option.get('object_output'):
				option.set('object_output', '%s' % os.path.dirname(component.outputs[0]))
			if option.get('type'):
				cb_type = { 'cprogram': '1', 'cshlib': '3', 'cstlib': '2', 'cxxprogram': '1', 'cxxshlib': '3', 'cxxstlib': '2' }
				option.set('type', cb_type[component.type])
			if option.get('compiler'):
				option.set('compiler', component.compiler)

		compiler = target.find('Compiler')
		for cflag in cflags:
			ElementTree.SubElement(compiler, 'Add', attrib={'option':cflag})
		for include in includes:
			ElementTree.SubElement(compiler, 'Add', attrib={'directory':include})
		if len(lflags) or len(libs) or len(libpaths):
			linker = ElementTree.SubElement(target, 'Linker')
			for lflag in lflags:
				ElementTree.SubElement(linker, 'Add', attrib={'option':lflag})
			for lib in libs:
				ElementTree.SubElement(linker, 'Add', attrib={'library':lib})
			for libpath in libpaths:
				ElementTree.SubElement(linker, 'Add', attrib={'directory':libpath})		
		build.append(target)

		# add (new) source file(s)
		sources = []
		for key in component.inputs:
			obj = bld.components[key]
			for src in obj.inputs:
				sources.append(src)
		for unit in project.iter('Unit'):
			src = str(unit.get('filename'))
			sources.remove(src)
		for src in sources:
			unit = ElementTree.fromstring(_cb_unit)
			unit.set('filename', src)
			project.append(unit)

		if not project.find('Extensions'):
			extension = ElementTree.fromstring(_cb_extension)
			project.append(extension)

		# prettify and export project data
		codeblocks_save(fname, root)
		return (fname, depends)

	def codeblocks_save(fname, root):
		s = ElementTree.tostring(root)
		content = minidom.parseString(s).toprettyxml(indent="\t")
		lines = [l for l in content.splitlines() if not l.isspace() and len(l)]
		lines[0] = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
		with open(fname, 'w') as f:
			f.write('\n'.join(lines))

	def codeblocks_workspace(path, projects):
		# open existing workspace or create a new one from template
		fname = '%s/codeblocks.workspace' % path
		if os.path.exists(fname):
			root = ElementTree.parse(fname).getroot()
		else:
			root = ElementTree.fromstring(_cb_workspace)
		workspace = root.find('Workspace')

		# check if the project already exist; if so only update dependencies
		for project in workspace.iter('Project'):
			name = project.get('filename')
			if projects.has_key(name):
				depends = projects[name]
				for depend in project.iter('Depends'):
					dep = str(depend.get('filename'))
					depends.remove(dep)
				for depend in depends:
					ElementTree.SubElement(project, 'Depends', attrib={'filename':depend})
				del projects[name]

		# add new projects including its dependencies
		for name, depends in projects.items():
			project = ElementTree.SubElement(workspace, 'Project', attrib={'filename':name})
			if len(depends):
				for depend in depends:
					ElementTree.SubElement(project, 'Depends', attrib={'filename':depend})
		codeblocks_save(fname, root)
		return fname

	def output_codeblocks(bld):
		path = "%s/codeblocks" % bld.path.abspath()
		projects = {}
		if not os.path.exists(path):
			os.makedirs(path)
		for key, component in bld.components.items():
			if component.type in ['cprogram', 'cshlib', 'cstlib', 'cxxprogram', 'cxxshlib', 'cxxstlib']:
				(fname, depends) = codeblocks_project(bld, path, component)
				Logs.warn('exported: %s, dependencies: %s' % (fname,depends))
				projects[os.path.basename(fname)] = depends
		fname = codeblocks_workspace(path, projects)
		Logs.warn('exported: %s' % fname)
	bld.add_post_fun(output_codeblocks)

_cb_project = '''
<CodeBlocks_project_file>
	<FileVersion major="1" minor="6" />
	<Project>
		<Option title="cprogram" />
		<Option pch_mode="2" />
		<Build>
		</Build>
	</Project>
</CodeBlocks_project_file>
'''

_cb_target = '''
<Target title="Debug">
	<Option output="bin/Debug/cprogram" prefix_auto="1" extension_auto="1" />
	<Option object_output="obj/Debug/" />
	<Option type="1" />
	<Option compiler="gcc" />
	<Compiler>
	</Compiler>
</Target>
'''

_cb_unit = '''
<Unit filename="main.c">
	<Option compilerVar="CC" />
</Unit>
'''

_cb_extension = '''
<Extensions>
	<code_completion />
	<debugger />
</Extensions>
'''

_cb_workspace = '''
<CodeBlocks_workspace_file>
	<Workspace title="Workspace">
	</Workspace>
</CodeBlocks_workspace_file>
'''



