#! /usr/bin/env python
# -*- encoding: utf-8 -*-
#
# TODO: detect and export cross-compile settings

import os
import xml.etree.ElementTree as ElementTree
from xml.dom import minidom
from waflib import Build, Logs, Task

class Component(object): pass


def init(bld):
	if not _selected(bld):
		return
	bld.codeblocks_components = {}


def process(task):
	bld = task.generator.bld
	if not _selected(bld):
		return
	cls = task.__class__.__name__
	if cls not in ('c','cxx', 'cprogram', 'cshlib', 'cstlib', 'cxxprogram', 'cxxshlib', 'cxxstlib'):
		return
	key = task.outputs[0].abspath()
	c = Component()
	c.name = os.path.basename(key)
	c.type = cls
	c.inputs = [x.abspath() for x in task.inputs]
	c.outputs = [x.abspath() for x in task.outputs]
	c.depends = [x.abspath() for x in list(task.dep_nodes + bld.node_deps.get(task.uid(), []))]
	c.command = [str(x) for x in task.command_executed]
	c.compiler =  _codeblocks_get_compiler(bld, c.command[0])
	bld.codeblocks_components[key] = c


def postfun(bld):
	if not _selected(bld):
		return
	path = "%s/codeblocks" % bld.path.abspath()
	if not os.path.exists(path):
		os.makedirs(path)

	components = bld.codeblocks_components
	projects = {}

	for key, component in components.items():
		if component.type in ('cprogram', 'cshlib', 'cstlib', 'cxxprogram', 'cxxshlib', 'cxxstlib'):
			(fname, depends) = _codeblocks_project(bld, path, component)
			Logs.warn('exported: %s, dependencies: %s' % (fname,depends))
			projects[os.path.basename(fname)] = depends
	fname = _codeblocks_workspace(path, projects)
	Logs.warn('exported: %s' % fname)


def _selected(bld):
	'''returns True when this export formatter has been selected.'''
	return (set(bld.export_to) & set(['all','codeblocks']))


def _codeblocks_get_compiler(bld, cc):
	dest_os = bld.env.DEST_OS
	dest_cpu = bld.env.DEST_CPU
	cc = os.path.basename(cc)
	if 'mingw32' in cc:
		cc = 'mingw32gcc'
	elif dest_cpu == 'arm':
		cc = 'armelfgcc'
	return cc


def _codeblocks_project(bld, path, component):
	# determine compile options and include path
	cflags = []
	includes = []
	for key in component.inputs:
		obj = bld.codeblocks_components[key]
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
		root = ElementTree.fromstring(CODEBLOCKS_CBP_PROJECT)

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

	ctypes = { 'cprogram': '1', 'cshlib': '3', 'cstlib': '2', 'cxxprogram': '1', 'cxxshlib': '3', 'cxxstlib': '2' }
	ctype = ctypes[component.type]
	coutput = str(component.outputs[0])

	# add build target and set compiler and linker options
	target = ElementTree.fromstring(CODEBLOCKS_CBP_TARGET)
	target.set('title', title)
	for option in target.iter('Option'):
		if option.get('output'):
			option.set('output', coutput)
		if option.get('object_output'):
			option.set('object_output', '%s' % os.path.dirname(coutput))
		if option.get('type'):
			option.set('type', ctype)
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
		obj = bld.codeblocks_components[key]
		for src in obj.inputs:
			sources.append(src)
	for unit in project.iter('Unit'):
		src = str(unit.get('filename')).replace('\\','/')
		if src.startswith('../'):
			src = '%s%s' % (bld.path.abspath(), src[2:])
		sources.remove(src)

	for src in sources:
		unit = ElementTree.fromstring(CODEBLOCKS_CBP_UNIT)
		unit.set('filename', src)
		project.append(unit)

	if project.find('Extensions') is None:
		extension = ElementTree.fromstring(CODEBLOCKS_CBP_EXTENSION)
		project.append(extension)

	# prettify and export project data
	_codeblocks_save(fname, root)
	return (fname, depends)


def _codeblocks_save(fname, root):
	s = ElementTree.tostring(root)
	content = minidom.parseString(s).toprettyxml(indent="\t")
	lines = [l for l in content.splitlines() if not l.isspace() and len(l)]
	lines[0] = '<?xml version="1.0" encoding="UTF-8" standalone="yes" ?>'
	with open(fname, 'w') as f:
		f.write('\n'.join(lines))


def _codeblocks_workspace(path, projects):
	# open existing workspace or create a new one from template
	fname = '%s/codeblocks.workspace' % path
	if os.path.exists(fname):
		root = ElementTree.parse(fname).getroot()
	else:
		root = ElementTree.fromstring(CODEBLOCKS_WORKSPACE)
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
	_codeblocks_save(fname, root)
	return fname


CODEBLOCKS_CBP_PROJECT = '''
<CodeBlocks_project_file>
	<FileVersion major="1" minor="6" />
	<Project>
		<Option title="cprogram" />
		<Option pch_mode="2" />
		<Option compiler="gcc" />
		<Build>
		</Build>
	</Project>
</CodeBlocks_project_file>
'''

CODEBLOCKS_CBP_TARGET = '''
<Target title="Debug">
	<Option output="bin/Debug/cprogram" prefix_auto="1" extension_auto="1" />
	<Option object_output="obj/Debug/" />
	<Option type="1" />
	<Option compiler="gcc" />
	<Compiler>
	</Compiler>
</Target>
'''

CODEBLOCKS_CBP_UNIT = '''
<Unit filename="main.c">
	<Option compilerVar="CC" />
</Unit>
'''

CODEBLOCKS_CBP_EXTENSION = '''
<Extensions>
	<code_completion />
	<debugger />
</Extensions>
'''

CODEBLOCKS_WORKSPACE = '''
<CodeBlocks_workspace_file>
	<Workspace title="Workspace">
	</Workspace>
</CodeBlocks_workspace_file>
'''

