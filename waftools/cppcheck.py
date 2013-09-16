#! /usr/bin/env python
# -*- encoding: utf-8 -*-
# Michel Mooij, michel.mooij7@gmail.com

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

import xml.sax
import pygments
from pygments import formatters
from pygments import lexers
from waflib import Task,TaskGen,Logs

def options(opt):
	opt.add_option('--cppcheck-skip', dest='cppcheck_skip', default=False, action='store_true', help='do not check C/C++ sources with cppcheck (default=False)')
	opt.add_option('--cppcheck-err-resume', dest='cppcheck_err_resume', default=False, action='store_true', help='continue in case of errors (default=False)')
	opt.add_option('--cppcheck-enable', dest='cppcheck_enable', default='all', action='store', help='cppcheck option --enable=<id> (default=all)')

def configure(conf):
	if conf.options.cppcheck_skip:
		conf.env.CPPCHECK_SKIP = [True]
	conf.find_program('cppcheck', var='CPPCHECK')

@TaskGen.feature('c')
@TaskGen.feature('c++')
def cppcheck_execute(self):
	if len(self.bld.env.CPPCHECK_SKIP) or self.bld.options.cppcheck_skip:
		return
	if getattr(self, 'cppcheck_skip', False):
		return

	cmd = [str(self.env.CPPCHECK), '-j 4', '--inconclusive','--max-configs=50', '--report-progress', '--verbose', '--xml','--xml-version=2']
	if 'c++' in getattr(self, 'features', ''):
		cmd.append('--language=c++')
		cmd.append('--std=c++03')
	else:
		cmd.append('--language=c')
		cmd.append('--std=c99')

	if self.bld.options.cppcheck_enable:
		cmd.append('--enable=%s' % self.bld.options.cppcheck_enable)

	cmd += _cppcheck_get_suppress_rules(self)

	sources = self.to_list(getattr(self, 'source', []))
	includes = self.to_incnodes(self.to_list(self.env.INCLUDES) + self.to_list(getattr(self, 'includes', [])))
	target = self.path.get_bld().find_or_declare('cppcheck.xml')

	task = self.create_task('cppcheck', src=sources, tgt=target)
	task.name = self.get_name()
	task.cmd = cmd
	task.includes = list(set(includes))
	task.fatal = []
	if not self.bld.options.cppcheck_err_resume:
		task.fatal.append('error')

def _cppcheck_get_suppress_rules(self):
	rules = []
	fname = getattr(self, 'cppcheck_suppress', None)
	if not fname:
		return rules
	fnode = self.path.find_resource(fname)
	if not fnode:
		return rules

	for line in fnode.read().split('\n'):
		if not len(line):
			continue
		rule = line.split(':')
		if len(rule) > 1:
			rule[1] = '%s/%s' %(self.path.get_src().abspath(), rule[1])
		rules.append('--suppress=%s' % ':'.join(rule))
	return rules

class cppcheck(Task.Task):
	def run(self):
		cmd = list(self.cmd)
		for source in self.inputs:
			cmd.append(source.abspath())
		for include in self.includes:
			cmd.append('-I')
			cmd.append(include.abspath())
		target = self.outputs[0]

		cmd = '%s 2> %s' % (' '.join(cmd), target.abspath())
		res = self.exec_command(cmd=cmd)
		if res != 0:
			return res

		reports = self._parse_xml_report(target.abspath())
		http_index = self._create_html_report(reports)
		self._errors_evaluate(reports, http_index)
		return 0

	def _parse_xml_report(self, fname):
		try:
			content = _CppCheckXmlContentHandler(self.master.bld)
			xml.sax.parse(open(fname), content)
		except xml.sax.SAXParseException as err:
			msg = "cppcheck: failed to parse file(%s), exception(%s)" % (fname, err)
			self.master.bld.fatal(msg)
		return content.get_errors()

	def _create_html_report(self, reports):
		http_dir = '%s/cppcheck' % self.generator.path.get_bld().abspath()
		http_index = self.generator.path.get_bld().find_or_declare('cppcheck/index.html')

		files = self._create_html_files(http_dir, reports)
		self._create_html_index(http_index, files)
		self._create_css_file(http_dir)

		return str(http_index.abspath())

	def _create_html_files(self, http_dir, reports):
		sources = {}
		reports = [r for r in reports if r.has_key('file')]
		for report in reports:
			name = report['file']
			if not sources.has_key(name):
				sources[name] = [report]
			else:
				sources[name].append(report)
		
		files = {}
		names = sources.keys()
		for n in range(0,len(names)):
			name = names[n]
			htmlfile = '%s/%i.html' % (http_dir, n)
			errors = sources[names[n]]
			files[name] = { 'htmlfile': htmlfile, 'errors':errors }
			self._create_html_file(name, htmlfile, errors)
		return files

	def _create_html_file(self, filename, htmlfile, errors):
		title = self.generator.get_name()
		lines = []
		for error in errors:
			lines.append(error['line'])

		stream = open(filename)
		content = stream.read()
		stream.close()

		formatter = _CppcheckHtmlFormatter(linenos=True, style='colorful', hl_lines=lines, lineanchors='line')
		formatter.errors = errors
		stream = open(htmlfile, 'w')

		stream.write(HTML_HEAD % (title, formatter.get_style_defs('.highlight'), title))
		lexer = pygments.lexers.guess_lexer_for_filename(filename, "")

		stream.write(pygments.highlight(content, lexer, formatter))
		stream.write(HTML_FOOTER)
		stream.close()

	def _create_html_index(self, http_index, files):
		title = self.generator.get_name()

		stream = open(http_index.abspath(), 'w')
		stream.write(HTML_HEAD % (title, "", title))
		stream.write("<table>")
		stream.write("<tr><th>Line</th><th>Id</th><th>Severity</th><th>Message</th></tr>")

		for filename, data in files.items():
			stream.write("<tr><td colspan='4'><a href=\"%s\">%s</a></td></tr>" % (data["htmlfile"], filename))
			for error in data["errors"]:
				if error['severity'] == 'error':
					error_class = 'class="error"'
				else:
					error_class = ''

				if error["id"] == "missingInclude":
					stream.write("<tr><td></td><td>%s</td><td>%s</td><td>%s</td></tr>" %
							(error["id"], error["severity"], error["msg"]))
				else:
					stream.write("<tr><td><a href='%s#line-%s'>%s</a></td><td>%s</td><td>%s</td><td %s>%s</td></tr>" %
							(data["htmlfile"], error["line"], error["line"], error["id"],
								error["severity"], error_class, error["msg"]))
		stream.write("</table>")
		stream.write(HTML_FOOTER)
		stream.close()

	def _create_css_file(self, http_dir):
		stream = open('%s/style.css' % http_dir, "w")
		stream.write(CSS_FILE)
		stream.close()

	def _errors_evaluate(self, errors, http_index):
		name = self.generator.get_name()			
		msg = 'file://%s' % http_index
		fatal = self.fatal

		severity = [err['severity'] for err in errors]
		if set(fatal) & set(severity):
			exc  = "\n"
			exc +=  "\nccpcheck detected fatal error(s) in task '%s', see report for details:" % name
			exc += "\n    file://%s" % (http_index)
			exc += "\n"
			self.generator.bld.fatal(exc)

		if len(errors):
			msg =  "\nccpcheck detected (possible) problem(s) in task '%s', see report for details:" % name
			msg += "\n    file://%s" % http_index
			msg += "\n"
			Logs.error(msg)

class _CppCheckXmlContentHandler(xml.sax.handler.ContentHandler):
	def __init__(self, bld):
		xml.sax.handler.ContentHandler.__init__(self)
		self._error = None
		self._errors = []
		self.bld = bld

	def get_errors(self):
		return self._errors

	def startElement(self, name, attributes):
		if name not in ('error', 'location'):
			return
		if name == 'error':
			self._error = dict()
		for key in attributes.keys():
			self._error[str(key)] = str(attributes[key])

	def endElement(self, name):
		if name == 'error':
			self._errors.append(self._error)
			self._error = None

class _CppcheckHtmlFormatter(pygments.formatters.HtmlFormatter):
	errors = []

	def wrap(self, source, outfile):
		line_no = 1
		for i, t in super(_CppcheckHtmlFormatter, self).wrap(source, outfile):
			# If this is a source code line we want to add a span tag at the end.
			if i == 1:
				for error in self.errors:
					if int(error['line']) == line_no:
						t = t.replace('\n', HTML_ERROR % error['msg'])
				line_no = line_no + 1
			yield i, t

CSS_FILE = """
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

HTML_HEAD = """
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
  <head>
    <title>CppCheck - Html report - %s</title>
    <link href="style.css" rel="stylesheet" type="text/css" />
    <style type="text/css">
%s
    </style>
  </head>
  <body class="body">
    <div id="page-header">
      &nbsp;
    </div>
    <div id="page">
      <div id="header">
        <h1>CppCheck report - %s</h1>
      </div>
      <div id="menu">
        <a href="index.html">Defect list</a>
      </div>
      <div id="content">
"""

HTML_FOOTER = """
      </div>
      <div id="footer">
        <div>
          CppCheck - a tool for static C/C++ code analysis
        </div>
        <div>
          Internet: <a href="http://cppcheck.sourceforge.net">http://cppcheck.sourceforge.net</a><br/>
          Forum: <a href="http://apps.sourceforge.net/phpbb/cppcheck/">http://apps.sourceforge.net/phpbb/cppcheck/</a><br/>
          IRC: #cppcheck at irc.freenode.net
        </div>
        &nbsp;
      </div>
      &nbsp;
    </div>
    <div id="page-footer">
      &nbsp;
    </div>
  </body>
</html>
"""

HTML_ERROR = "<span style=\"border-width: 2px;border-color: black;border-style: solid;background: #ffaaaa;padding: 3px;\">&lt;--- %s</span>\n"

