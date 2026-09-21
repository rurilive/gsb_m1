"""测试辅助：在临时目录里造插件文件。"""

import os
import shutil
import tempfile
import unittest


def indent(text):
    """把多行代码块整体缩进四格。"""
    return "\n".join("    " + line for line in text.strip().splitlines())


def plugin_source(name, version, handle_body, init_body=None, manifest_extra=""):
    """拼一个最小插件模块的源码。"""
    manifest = 'PLUGIN = {"name": %r, "version": %r' % (name, version)
    if manifest_extra:
        manifest += ", " + manifest_extra
    manifest += "}"
    parts = [manifest]
    if init_body is not None:
        parts += ["", "def init(ctx):", indent(init_body)]
    parts += ["", "def handle(state, request):", indent(handle_body)]
    return "\n".join(parts) + "\n"


class PluginDir:
    """临时插件目录，with 退出时整个删掉，也可以手动 close。"""

    def __init__(self):
        self.path = tempfile.mkdtemp(prefix="replug-test-")

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def close(self):
        shutil.rmtree(self.path, ignore_errors=True)

    def write(self, name, version="1.0.0", handle_body="return request",
              init_body=None, manifest_extra=""):
        """写一个插件文件，返回文件路径。"""
        return self.write_source(
            name, plugin_source(name, version, handle_body,
                                init_body=init_body, manifest_extra=manifest_extra))

    def write_source(self, name, source):
        """按给定源码写一个插件文件，返回文件路径。"""
        path = os.path.join(self.path, name + ".py")
        with open(path, "w", encoding="utf-8") as stream:
            stream.write(source)
        return path


class RuntimeTestCase(unittest.TestCase):
    """带临时插件目录的用例基类。"""

    def setUp(self):
        self.plugins = PluginDir()
        self.addCleanup(self.plugins.close)
