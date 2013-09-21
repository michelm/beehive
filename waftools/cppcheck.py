#! /usr/bin/env python
# -*- encoding: utf-8 -*-
# Michel Mooij, michel.mooij7@gmail.com
#
# TODO: 
# add buildin include paths from gcc itself:
#	echo | gcc -v -x c -E -
#
# query stdout and look for:
#	'#include "..." search starts here:'				<-- start
#	'#include <...> search starts here:'				<-- skip
#	'/usr/lib/gcc/x86_64-redhat-linux/4.8.1/include'	<-- use this one (startswith '/')
#	'/usr/local/include'								<-- use this one (startswith '/')
#	'/usr/include'										<-- use this one (startswith '/')
#	'End of search list.'								<-- end (does not startwith '/' nor with '#')

"""
Tool Description
================
This module provides a waf wrapper (i.e. waftool) around the C/C++ source code 
checking tool 'cppcheck'.

See http://cppcheck.sourceforge.net/ for more information on the cppcheck tool
itself. 
Note that many linux distributions already provide a ready to install version 
of cppcheck. On fedora, for instance, it can be installed using yum:

	'sudo yum install cppcheck'


Usage
=====
In order to use this waftool simply add it to the 'options' and 'configure' 
functions of your main waf script as shown in the example below:

	def options(opt):
		opt.load('cppcheck', tooldir='./waftools')

	def configure(conf):
		conf.load('cppcheck')
		
Note that example shown above assumes that the cppcheck waftool is located in 
the sub directory named 'waftools'.

When configured as shown in the example above, cppcheck will automatically 
perform a source code analysis on all C/C++ build tasks that have been 
defined in your waf build system.

The example shown below for a C program will be used as input for cppcheck when
building the task.

	def build(bld):
		bld.program(
				name='foo', 
				src='foobar.c'
		)

The result of the source code analysis will be stored both as xml and html 
files in the build location for the task. Should any error be detected by 
cppcheck the build will be aborted and a link to the html report will be shown.

When needed source code checking by cppcheck can be disabled per task, per 
detected error or warning for a particular task. It can be also be disbled for 
all tasks.

In order to exclude a task from source code checking add the skip option to the
task as shown below:	

	def build(bld):
		bld.program(
				name='foo',
				src='foobar.c'
				cppcheck_skip=True 	# skip source code checking
		)

When needed problems detected by cppcheck may be suppressed using a file 
containing a list of suppression rules. The relative or absolute path to this 
file can added to the build task as shown in the example below:

		bld.program(
				name='bar',
				src='foobar.c',
				cppcheck_suppress='bar.suppress'
		)

A cppcheck suppress file should contain one suppress rule per line. Each of 
these rules will be passed as an '--suppress=<rule>' argument to cppcheck.


Note: The generation of the html report is based on the cppcheck-htmlreport.py 
script that comes shipped with the cppcheck tool.
"""

import os, sys
import xml.etree.ElementTree as ElementTree
import pygments
from pygments import formatters, lexers
from waflib import Task, TaskGen, Logs, Context


def options(opt):
	opt.add_option('--cppcheck-skip', dest='cppcheck_skip', 
		default=False, action='store_true', 
		help='do not check C/C++ sources (default=False)')

	opt.add_option('--cppcheck-err-resume', dest='cppcheck_err_resume', 
		default=False, action='store_true', 
		help='continue in case of errors (default=False)')

	opt.add_option('--cppcheck-enable', dest='cppcheck_enable', 
		default='all', action='store', 
		help='cppcheck option --enable=<id> (default=all)')

	opt.add_option('--cppcheck-std-c', dest='cppcheck_std_c', 
		default='c99', action='store', 
		help='cppcheck standard to use when checking C files (default=c99)')

	opt.add_option('--cppcheck-std-cxx', dest='cppcheck_std_cxx', 
		default='c++03', action='store', 
		help='cppcheck standard to use when checking C files (default=c++03)')

	opt.add_option('--cppcheck-check-config', dest='cppcheck_check_config', 
		default=False, action='store_true', 
		help='forced check for missing buildin include files, e.g. stdio.h (default=False)')


def configure(conf):
	if conf.options.cppcheck_skip:
		conf.env.CPPCHECK_SKIP = [True]
	conf.find_program('cppcheck', var='CPPCHECK')


@TaskGen.feature('c')
@TaskGen.feature('cxx')
def cppcheck_execute(self):
	if len(self.bld.env.CPPCHECK_SKIP) or self.bld.options.cppcheck_skip:
		return
	if getattr(self, 'cppcheck_skip', False):
		return

	task = self.create_task('cppcheck')
	task.cmd = _tgen_create_cmd(self)
	task.fatal = []
	if not self.bld.options.cppcheck_err_resume:
		task.fatal.append('error')


def _tgen_create_cmd(self):
	'''creates cppcheck command string to be executed.

	note that the function uses several fixed flags for the command line;
	these are nessecary in order to create the correct cppcheck xml report.
	'''
	cmd  = '%s' % self.env.CPPCHECK
	args = ['--inconclusive','--max-configs=50','--report-progress','--verbose','--xml','--xml-version=2']

	if 'cxx' in getattr(self, 'features', []):
		args.append('--language=c++')
		args.append('--std=%s' % self.bld.options.cppcheck_std_cxx)
	else:
		args.append('--language=c')
		args.append('--std=%s' % self.bld.options.cppcheck_std_c)

	if self.bld.options.cppcheck_check_config:
		args.append('--check-config')

	if self.bld.options.cppcheck_enable:
		args.append('--enable=%s' % self.bld.options.cppcheck_enable)

	for src in self.to_list(getattr(self, 'source', [])):
		args.append('%r' % src)
	for inc in self.to_incnodes(self.to_list(getattr(self, 'includes', []))):
		args.append('-I%r' % inc)
	for inc in self.to_incnodes(self.to_list(self.env.INCLUDES)):
		args.append('-I%r' % inc)
	return '%s %s' % (cmd, ' '.join(args))


class cppcheck(Task.Task):
	color = 'PINK'
	quiet = True

	def run(self):
		stderr = self.generator.bld.cmd_and_log(self.cmd, quiet=Context.STDERR, output=Context.STDERR)
		check = '%s<command>\n  %s\n</command>\n' % (stderr, '\n  '.join(self.cmd.split(' ')))
		node = self.generator.path.get_bld().find_or_declare('cppcheck.xml')
		node.write(check)
		report = self._get_report(stderr)
		index = self._create_html_report(report)
		self._errors_evaluate(report, index)
		return 0

	def _get_report(self, xml_string):
		report = []
		for error in ElementTree.fromstring(xml_string).iter('error'):
			defect = {}
			defect['id'] = error.get('id')
			defect['severity'] = error.get('severity')
			defect['msg'] = str(error.get('msg')).replace('<','&lt;')
			defect['verbose'] = error.get('verbose')
			for location in error.findall('location'):
				defect['file'] = location.get('file')
				defect['line'] = location.get('line')
			report.append(defect)
		return report

	def _create_html_report(self, report):
		files = self._create_html_files(report)
		index = self._create_html_index(files)
		self._create_css_file()
		return index

	def _create_html_files(self, reports):
		sources = {}
		reports = [r for r in reports if r.has_key('file')]
		for report in reports:
			name = report['file']
			if not sources.has_key(name):
				sources[name] = [report]
			else:
				sources[name].append(report)
		
		files = {}
		bpath = self.generator.path.get_bld().abspath()
		names = sources.keys()
		for i in range(0,len(names)):
			name = names[i]
			htmlfile = 'cppcheck/%i.html' % (i)
			errors = sources[name]
			files[name] = { 'htmlfile': '%s/%s' % (bpath, htmlfile), 'errors': errors }
			self._create_html_file(name, htmlfile, errors)
		return files

	def _create_html_file(self, sourcefile, htmlfile, errors):
		name = self.generator.get_name()
		root = ElementTree.fromstring(CPPCHECK_HTML_FILE)
		title = root.find('head/title')
		title.text = 'cppcheck - report - %s' % name

		body = root.find('body')
		for div in body.findall('div'):
			if div.get('id') == 'page':
				page = div
				break
		for div in page.findall('div'):
			if div.get('id') == 'header':
				h1 = div.find('h1')
				h1.text = 'cppcheck report - %s' % name
			if div.get('id') == 'content':
				content = div
				srcnode = self.generator.bld.root.find_node(sourcefile)
				hl_lines = [e['line'] for e in errors if e.has_key('line')]
				formatter = CppcheckHtmlFormatter(linenos=True, style='colorful', hl_lines=hl_lines, lineanchors='line')
				formatter.errors = [e for e in errors if e.has_key('line')]
				lexer = pygments.lexers.guess_lexer_for_filename(sourcefile, "")
				s = "%s" % pygments.highlight(srcnode.read(), lexer, formatter)
				table = ElementTree.fromstring(s)
				content.append(table)

		s = ElementTree.tostring(root, method="html")
		s = CCPCHECK_HTML_TYPE + s
		node = self.generator.path.get_bld().find_or_declare(htmlfile)
		node.write(s)

	def _create_html_index(self, files):
		name = self.generator.get_name()
		root = ElementTree.fromstring(CPPCHECK_HTML_FILE)
		title = root.find('head/title')
		title.text = 'cppcheck - report - %s' % name

		body = root.find('body')
		for div in body.findall('div'):
			if div.get('id') == 'page':
				page = div
				break
		for div in page.findall('div'):
			if div.get('id') == 'header':
				h1 = div.find('h1')
				h1.text = 'cppcheck report - %s' % name
			if div.get('id') == 'content':
				content = div
				self._create_html_table(content, files)

		s = ElementTree.tostring(root, method="html")
		s = CCPCHECK_HTML_TYPE + s
		node = self.generator.path.get_bld().find_or_declare('cppcheck/index.html')
		node.write(s)
		return node

	def _create_html_table(self, content, files):
		table = ElementTree.fromstring(CPPCHECK_HTML_TABLE)
		for name, val in files.items():
			f = val['htmlfile']
			s = '<tr><td colspan="4"><a href="%s">%s</a></td></tr>\n' % (f,name)
			row = ElementTree.fromstring(s)
			table.append(row)

			errors = sorted(val['errors'], key=lambda e: int(e['line']) if e.has_key('line') else sys.maxint)
			for e in errors:
				if not e.has_key('line'):
					s = '<tr><td></td><td>%s</td><td>%s</td><td>%s</td></tr>\n' % (e['id'], e['severity'], e['msg'])
				else:
					attr = ''
					if e['severity'] == 'error':
						attr = 'class="error"'
					s = '<tr><td><a href="%s#line-%s">%s</a></td>' % (f, e['line'], e['line'])
					s+= '<td>%s</td><td>%s</td><td %s>%s</td></tr>\n' % (e['id'], e['severity'], attr, e['msg'])
				row = ElementTree.fromstring(s)
				table.append(row)
		content.append(table)

	def _create_css_file(self):
		node = self.generator.path.get_bld().find_or_declare('cppcheck/style.css')
		node.write(CPPCHECK_CSS_FILE)

	def _errors_evaluate(self, errors, http_index):
		name = self.generator.get_name()			
		fatal = self.fatal
		severity = [err['severity'] for err in errors]

		if set(fatal) & set(severity):
			exc  = "\n"
			exc += "\nccpcheck detected fatal error(s) in task '%s', see report for details:" % name
			exc += "\n    file://%r" % (http_index)
			exc += "\n"
			self.generator.bld.fatal(exc)

		elif len(errors):
			msg =  "\nccpcheck detected (possible) problem(s) in task '%s', see report for details:" % name
			msg += "\n    file://%r" % http_index
			msg += "\n"
			Logs.error(msg)


class CppcheckHtmlFormatter(pygments.formatters.HtmlFormatter):
	errors = []

	def wrap(self, source, outfile):
		line_no = 1
		for i, t in super(CppcheckHtmlFormatter, self).wrap(source, outfile):
			# If this is a source code line we want to add a span tag at the end.
			if i == 1:
				for error in self.errors:
					if int(error['line']) == line_no:
						t = t.replace('\n', CPPCHECK_HTML_ERROR % error['msg'])
				line_no = line_no + 1
			yield i, t


CCPCHECK_HTML_TYPE = \
'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">\n'

CPPCHECK_HTML_FILE = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd" [<!ENTITY nbsp "&#160;">]>
<html>
	<head>
		<title>cppcheck - report - XXX</title>
		<link href="style.css" rel="stylesheet" type="text/css" />
		<style type="text/css">
		</style>
	</head>
	<body class="body">
		<div id="page-header">&nbsp;</div>
		<div id="page">
			<div id="header">
				<h1>cppcheck report - XXX</h1>
			</div>
			<div id="menu">
				<a href="index.html">Defect list</a>
			</div>
			<div id="content">
			</div>
			<div id="footer">
				<div>cppcheck - a tool for static C/C++ code analysis</div>
				<div>
				Internet: <a href="http://cppcheck.sourceforge.net">http://cppcheck.sourceforge.net</a><br/>
          		Forum: <a href="http://apps.sourceforge.net/phpbb/cppcheck/">http://apps.sourceforge.net/phpbb/cppcheck/</a><br/>
				IRC: #cppcheck at irc.freenode.net
				</div>
				&nbsp;
			</div>
      		&nbsp;
		</div>
		<div id="page-footer">&nbsp;</div>
	</body>
</html>
"""

CPPCHECK_HTML_TABLE = """
<table>
	<tr>
		<th>Line</th>
		<th>Id</th>
		<th>Severity</th>
		<th>Message</th>
	</tr>
</table>
"""

CPPCHECK_HTML_ERROR = \
'<span style="background: #ffaaaa;padding: 3px;">&lt;--- %s</span>\n'

CPPCHECK_CSS_FILE = """
body.body {
	font-family: Arial;
    font-size: 13px;
    background-color: black;
    padding: 0px;
    margin: 0px;
}

.error {
    font-family: Arial;
    font-size: 13px;
    background-color: #ffb7b7;
    padding: 0px;
    margin: 0px;
}

th, td {
	min-width: 100px;
	text-align: left;
}

#page-header {
	clear: both;
	width: 900px;
	margin: 20px auto 0px auto;
	height: 10px;
	border-bottom-width: 2px;
	border-bottom-style: solid;
	border-bottom-color: #aaaaaa;
}

#page {
	width: 860px;
	margin: auto;
	border-left-width: 2px;
	border-left-style: solid;
	border-left-color: #aaaaaa;
	border-right-width: 2px;
	border-right-style: solid;
	border-right-color: #aaaaaa;
	background-color: White;
	padding: 20px;
}

#page-footer {
	clear: both;
	width: 900px;
	margin: auto;
	height: 10px;
	border-top-width: 2px;
	border-top-style: solid;
	border-top-color: #aaaaaa;
}

#header {
	width: 100%;
	height: 70px;
	background-image: url(logo.png);
	background-repeat: no-repeat;
	background-position: left top;
	border-bottom-style: solid;
	border-bottom-width: thin;
	border-bottom-color: #aaaaaa;
}

#menu {
	margin-top: 5px;
	text-align: left;
	float: left;
	width: 100px;
	height: 300px;
}

#menu > a {
	margin-left: 10px;
	display: block;
}

#content {
	float: left;
	width: 720px;
	margin: 5px;
	padding: 0px 10px 10px 10px;
	border-left-style: solid;
	border-left-width: thin;
	border-left-color: #aaaaaa;
}

#footer {
	padding-bottom: 5px;
	padding-top: 5px;
	border-top-style: solid;
	border-top-width: thin;
	border-top-color: #aaaaaa;
	clear: both;
	font-size: 10px;
}

#footer > div {
	float: left;
	width: 33%;
}
"""






