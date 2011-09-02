#!/usr/bin/env python

from __future__ import with_statement
from string import Template
import re, fnmatch, os

VERSION = "0.3.0"

TEST_FUNC_REGEX = r"^(void\s+(test_%s__(\w+))\(\s*(void)?\s*\))\s*\{"

CLAY_FILE_CORE = r"""abcd"""
CLAY_FILE_HEADER = r"""header"""

TEMPLATE_MAIN = Template(
r"""
/*
 * Clay v${version}
 *
 * This is an autogenerated file. Do not modify.
 * To add new unit tests or suites, regenerate the whole
 * file with `./clay`
 */

${clay_core}

${clay_sandbox}

${extern_declarations}

${test_callbacks}

static const struct clay_suite _all_suites[] = {
	${test_suites}
};

int main(int argc, char *argv[])
{
	return clay_test(
		argc, argv, _all_suites,
		sizeof(_all_suites)/sizeof(_all_suites[0]));
}
""")

TEMPLATE_CALLBACKS = Template(
r"""
static const struct clay_func _${suite_name}_tests[] = {
	${callbacks}
};
""")

TEMPLATE_SUITE = Template(
r"""
	{
		"${clean_name}",
		${initialize},
		${cleanup},
		_${suite_name}_tests,
		${test_count}
	}
""")

class ClayTestBuilder:
	def __init__(self, folder_name, clay_path = None):
		self.declarations = []
		self.callbacks = []
		self.suites = {}

		self.clay_path = clay_path or os.path.join(folder_name, "clay")
		self.output = os.path.join(folder_name, "clay_main.c")

		if not os.path.exists(self.clay_path) or not \
			os.path.exists(os.path.join(self.clay_path, "clay.h")):
			raise Exception(
				"The `clay` folder could not be found. "
				"Clay sources are expected to be in a subfolder "
				"under your test suite folder.")

		self.test_files = []

		file_list = os.listdir(folder_name)
		for fname in fnmatch.filter(file_list, "*.c"):
			with open(fname) as f:
				if self._process_test_file(fname, f.read()):
					self.test_files.append(fname)

	def _load_file(self, filename):
		filename = os.path.join(self.clay_path, filename)
		with open(filename) as cfile:
			return cfile.read()

	def render(self):
		template = TEMPLATE_MAIN.substitute(
			clay_core = self._load_file("clay.c"),
			clay_sandbox = self._load_file("clay_sandbox.c"),
			extern_declarations = "\n".join(self.declarations),
			test_callbacks = "\n".join(self.callbacks),
			test_suites = ",\n\t".join(self.suites.values()),
			version = VERSION
		)

		with open(self.output, "w") as out:
			out.write(template)
			print ('Written test suite to "%s"' % self.output)
			print ('Suite file list: [%s]' % ", ".join(["clay_main.c"] + self.test_files))

	def _cleanup_name(self, name):
		words = name.split("_")
		return " ".join(words).capitalize()

	def _process_test_file(self, file_name, contents):
		file_name = os.path.basename(file_name)
		file_name, _ = os.path.splitext(file_name)

		regex_string = TEST_FUNC_REGEX % file_name
		regex = re.compile(regex_string, re.MULTILINE)

		callbacks = {}

		for (declaration, symbol, short_name, _) in regex.findall(contents):
			self.declarations.append("extern %s;" % declaration)

			callbacks[short_name] = '{"%s [%s]", &%s}' % (
				self._cleanup_name(short_name), symbol, symbol
			)

		initialize = callbacks.pop("initialize", "NULL")
		cleanup = callbacks.pop("cleanup", "NULL")

		if not callbacks:
			return False

		self.callbacks.append(TEMPLATE_CALLBACKS.substitute(
			suite_name = file_name,
			callbacks = ",\n\t".join(callbacks.values())
		).strip())

		self.suites[file_name] = TEMPLATE_SUITE.substitute(
			clean_name = self._cleanup_name(file_name),
			suite_name = file_name,
			initialize = initialize,
			cleanup = cleanup,
			test_count = len(callbacks)
		).strip()

		return True

if __name__ == '__main__':
	builder = ClayTestBuilder('.', '.')
	builder.render()