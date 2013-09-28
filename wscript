#! /usr/bin/env python
# -*- encoding: utf-8 -*-

import os, sys
from waflib.Build import BuildContext, CleanContext, InstallContext, UninstallContext
from waftools import makefile

top = '.'
out = 'build'
prefix = 'output'

VERSION = '0.0.1'
APPNAME = 'beehive'
VARIANTS = {}

def options(opt):
	opt.add_option('--check_c_compiler', dest='check_c_compiler', default='gcc', action='store', help='Selects C compiler type.')
	opt.add_option('--check_cxx_compiler', dest='check_cxx_compiler', default='gxx', action='store', help='Selects C++ compiler type.')
	opt.add_option('--prefix', dest='prefix', default=prefix, help='installation prefix [default: %r]' % prefix)
	opt.add_option('--debug', dest='debug', default=False, action='store_true', help='Build with debug information.')
	opt.load('cppcheck', tooldir='./waftools')
	opt.load('makefile', tooldir='./waftools')

def configure(conf):
	conf.check_waf_version(mini='1.7.0')
	for name, cc_prefix in VARIANTS.items():
		_configure(conf, name, cc_prefix)
	_configure(conf, None, None)

def build(bld):
	def get_scripts(root, script):
		scripts = []
		for path, dirs, files in os.walk(root):
			if script in files and not any(path.startswith(s) for s in scripts):
				scripts.append(path)
		return scripts
	scripts = get_scripts('packages', 'wscript')
	for script in scripts:
		bld.recurse(script)

def dist(ctx):
	ctx.algo = 'tar.gz'
	ctx.excl = ' **/*~ **/.lock-w* **/CVS/** **/.svn/** downloads/** ext/** build/** tmp/**'

def _configure(conf, variant, cc_prefix):
	conf.msg('Creating environment', variant if variant else sys.platform, color='YELLOW')
	if variant:
		conf.setenv(variant)
		prefix = '%s/opt/%s' % (conf.env.PREFIX.replace('\\', '/').rstrip('/'), variant)
		conf.env.PREFIX = prefix
		conf.env.BINDIR = '%s/bin' % (prefix)
		conf.env.LIBDIR = '%s/lib' % (prefix)
		conf.find_program('%s-gcc' % (cc_prefix), var='CC')
		conf.find_program('%s-g++' % (cc_prefix), var='CXX')
		conf.find_program('%s-ar'  % (cc_prefix), var='AR')
	else:
		conf.setenv('')
	conf.load('compiler_c')
	conf.load('compiler_cxx')
	conf.load('makefile')
	conf.load('cppcheck')
	conf.env.CFLAGS = ['-Wall']
	conf.env.CXXFLAGS = ['-Wall']
	conf.env.RPATH = ['/lib', '/usr/lib', '/usr/local/lib']
	conf.env.append_unique('RPATH', '%s/lib' % conf.env.PREFIX)
	if conf.options.debug:
		conf.env.append_unique('CFLAGS', '-ggdb')
		conf.env.append_unique('CFLAGS', '-g')
		conf.env.append_unique('CXXFLAGS', '-ggdb')
		conf.env.append_unique('CXXFLAGS', '-g')
	else:
		conf.env.append_unique('CFLAGS', '-O3')
		conf.env.append_unique('CXXFLAGS', '-O3')
		conf.env.append_unique('DEFINES', 'NDEBUG')

if sys.platform in ['linux', 'linux2']:
	VARIANTS = { 'win32' : 'x86_64-w64-mingw32' }
	CONTEXTS = ( BuildContext, CleanContext, InstallContext, UninstallContext, makefile.MakefileContext)
	for name in VARIANTS.keys():
		for context in CONTEXTS:
			command = context.__name__.replace('Context', '').lower()
			class tmp(context):
				__doc__ = '%ss the project for %s' % (command, name)
				cmd = '%s_%s' % (command, name)
				variant = name



