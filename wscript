#! /usr/bin/env python
# -*- encoding: utf-8 -*-

import os

top = '.'
out = 'build'
prefix = 'output'

VERSION = '0.0.2'
APPNAME = 'beehive'
VARIANTS = {}

def options(opt):
	opt.add_option('--check_c_compiler', dest='check_c_compiler', default='gcc', action='store', help='Selects C compiler type.')
	opt.add_option('--check_cxx_compiler', dest='check_cxx_compiler', default='gxx', action='store', help='Selects C++ compiler type.')
	opt.add_option('--prefix', dest='prefix', default=prefix, help='installation prefix [default: %r]' % prefix)
	opt.add_option('--debug', dest='debug', default=False, action='store_true', help='Build with debug information.')
	opt.load('cppcheck', tooldir='./waftools')
	opt.load('makefile', tooldir='./waftools')
	opt.load('codeblocks', tooldir='./waftools')


def configure(conf):
	conf.check_waf_version(mini='1.7.0')
	conf.load('compiler_c')
	conf.load('compiler_cxx')
	conf.load('cppcheck')
	conf.load('makefile')
	conf.load('codeblocks')
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


def build(bld):
	def get_scripts(root, script):
		scripts = []
		for path, _dirs, files in os.walk(root):
			if script in files and not any(path.startswith(s) for s in scripts):
				scripts.append(path)
		return scripts
	scripts = get_scripts('packages', 'wscript')
	for script in scripts:
		bld.recurse(script)


def dist(ctx):
	ctx.algo = 'tar.gz'
	ctx.excl = ' **/*~ **/.lock-w* **/CVS/** **/.svn/** downloads/** ext/** build/** tmp/**'



