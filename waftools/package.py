#!/usr/bin/env python

import shutil, os, sys
from waflib import Build, Context, Scripting, Logs


def options(opt):
    opt.add_option('--package_types', dest='package_types', default='all',
                   action='store', help='package types to create (default=all)')


def configure(conf):
	conf.env.PACKAGE_TYPES = conf.options.package_types.split(',')

	if conf.env.DEST_OS == 'win32':
		try:
			conf.find_program('makensis', var='NSIS')
		except conf.errors.ConfigurationError:
			conf.to_log('makensis was not found (ignoring)')


class PackageContext(Build.InstallContext):
	cmd = 'package'
	fun = 'build'

	def init_dirs(self, *k, **kw):
		super(PackageContext, self).init_dirs(*k, **kw)
		self._package = self.bldnode.make_node('.wafpackage')
		try:
			shutil.rmtree(self._package.abspath())
		except:
			pass
		if os.path.exists(self._package.abspath()):
			self.fatal('Could not remove temporary directory %r' % self._package)
		self._package.mkdir()
		self.options.destdir = self._package.abspath()

	def execute(self, *k, **kw):
		'''executes normal 'install' into a special, temporary, package directory
		and creates a package (e.g. tar.bz2 or rpm) file containing all installed
		files into this package directory.
		'''		
		super(PackageContext, self).execute(*k, **kw)

		version = getattr(Context.g_module, Context.VERSION, self.top_dir)
		appname = getattr(Context.g_module, Context.APPNAME, self.top_dir)
		variant = self.variant if self.variant else ''
		pkgtype = self.env.PACKAGE_TYPES
		files = self._get_files()

		if set(pkgtype) & set(['all', 'ls']):
			self._package_ls(appname, variant, version, files)
		
		if set(pkgtype) & set(['all', 'tar.bz2']):
			self._package_tar_bz2(appname, variant, version)

		if set(pkgtype) & set(['all', 'nsis']):
			if self.env.DEST_OS == 'win32':
				self._package_nsis(appname, variant, version, files)

		shutil.rmtree(self._package.abspath())

	def _get_files(self):
		'''returns a list of file names to be packaged from which the PREFIX
		path has been stripped.		
		'''
		files = []
		prefix = str(self.env.PREFIX)
		i = prefix.find(':')
		if i >= 0 and (i+1) < len(prefix):
			prefix = prefix[i+1:]
		i = len(self._package.relpath()) + len(prefix)

		for f in self._package.ant_glob('**'):
			files.append(str(f.relpath()[i:]).replace('\\','/'))
		return files

	def _package_ls(self, appname, variant, version, files):
		'''just print all files that will be packaged.'''
		p = Logs.info
		p('')
		p('=======================')
		p('PACKAGE (ls)')
		p('=======================')
		for f in files:
			p('$PREFIX%s' % f)
		p('-----------------------')
		
	def _package_tar_bz2(self, appname, variant, version):
		name = '%s-%s-%s' % (appname, variant, version)
		p = Logs.info
		p('')
		p('=======================')
		p('PACKAGE (tar.bz2)')
		p('=======================')
		p('PREFIX=%s' % self.env.PREFIX)	
		ctx = Scripting.Dist()
		ctx.arch_name = '%s.tar.bz2' % (name)
		ctx.files = self._package.ant_glob('**')
		ctx.tar_prefix = ''
		ctx.base_path = self._package
		ctx.archive()
		p('-----------------------')

	def _package_nsis(self, appname, variant, version, files):
		nsis = self.env.NSIS
		if isinstance(nsis, list):
			if not len(nsis):
				Logs.warn('NSIS not available, skipping')
				return
			nsis = nsis[0]
		p = Logs.info
		p('')
		p('=======================')
		p('PACKAGE (nsis)')
		p('=======================')

		# TODO:
		# - use .nsi from command line or create .nsi script on the fly
		# - copy .nsi to build dir
		# - exec makensis
		# what about defines?

		if sys.platform == 'win32':
			cmd = '%s /VERSION' % nsis
		else:
			cmd = '%s -VERSION' % nsis
		stdout = self.cmd_and_log(cmd, output=Context.STDOUT, quiet=Context.STDOUT)
		p('VERSION=%s' % stdout)
		p('-----------------------')
		

	
	
	
	
