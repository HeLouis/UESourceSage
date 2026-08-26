import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "ue-source-sage" / "scripts" / "sage.py"


class SageFixtureTest(unittest.TestCase):
    def setUp(self):
        self.temp = Path(tempfile.mkdtemp(prefix="ue-source-sage-fixture-"))
        shutil.copytree(ROOT / "skills" / "ue-source-sage", self.temp / "skills" / "ue-source-sage")
        engine = self.temp / "FakeEngine"
        source = engine / "Plugins" / "Runtime" / "TestPlugin" / "Source" / "TestCore"
        source.mkdir(parents=True)
        (engine / "Plugins" / "Runtime" / "TestPlugin" / "TestPlugin.uplugin").write_text("{}\n", encoding="utf-8")
        (source / "TestCore.Build.cs").write_text("PublicDependencyModuleNames.Add(\"Other\");\n", encoding="utf-8")
        (source / "TestCore.h").write_text("struct FTestCore {};\n", encoding="utf-8")
        (source / "TestCore.cpp").write_text("#include \"TestCore.h\"\n", encoding="utf-8")
        config = (ROOT / "config" / "global.yaml").read_text(encoding="utf-8")
        config = config.replace('source_root: ""', f'source_root: {json.dumps(str(engine).replace(chr(92), "/"))}')
        (self.temp / "config").mkdir()
        (self.temp / "config" / "global.yaml").write_text(config, encoding="utf-8")
        (self.temp / "modules").mkdir()
        (self.temp / "modules" / "index.md").write_text(
            "# UE Source Module Index\n\n| Module id | Name | Status | UE version | Submodules | Router |\n|---|---|---|---|---|---|\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp, ignore_errors=True)

    def run_sage(self, *args, expect=0):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(self.temp), *args],
            text=True,
            capture_output=True,
        )
        if result.returncode != expect:
            self.fail(f"command failed: {args}\nstdout={result.stdout}\nstderr={result.stderr}")
        return result

    def test_isolated_learning_lifecycle_and_boundaries(self):
        self.run_sage("preflight")
        discovery = self.run_sage("discover", "build-cs", "Test")
        self.assertIn("TestCore.Build.cs", discovery.stdout)
        self.run_sage("module", "create", "Test Domain", "--id", "test-domain", "--from-discovery")
        build_cs = "Plugins/Runtime/TestPlugin/Source/TestCore/TestCore.Build.cs"
        self.run_sage("module", "confirm", "test-domain", "--build-cs", build_cs)
        self.run_sage("route", "activate", "test-domain", "testcore", "--intent", "explain", "--topic", "core")
        self.run_sage("source", "check", "test-domain", "testcore", "Plugins/Runtime/TestPlugin/Source/TestCore/TestCore.h")
        self.run_sage(
            "source", "check", "test-domain", "testcore", "Plugins/Runtime/TestPlugin/Source/Other/Other.h", expect=2
        )
        self.run_sage(
            "knowledge", "create", "test-domain", "--submodule", "testcore", "--id", "core",
            "--title", "Core model", "--answer", "The core model is a test fixture.",
            "--source", "Plugins/Runtime/TestPlugin/Source/TestCore/TestCore.h:1",
            "--evidence-status", "verified_source",
        )
        self.run_sage("route", "activate", "test-domain", "testcore", "--intent", "explain", "--topic", "core")
        self.run_sage("source", "read", "test-domain", "testcore", "Plugins/Runtime/TestPlugin/Source/TestCore/TestCore.h")
        self.run_sage("knowledge", "update", "test-domain", "core", "--submodule", "testcore", "--title", "Core model updated")
        self.run_sage("source", "check", "test-domain", "testcore", "Plugins/Runtime/TestPlugin/Source/TestCore/TestCore.h", expect=2)
        self.run_sage("process", "start", "test-domain", "--submodule", "testcore")
        self.run_sage(
            "process", "advance", "test-domain", "--submodule", "testcore",
            "--summary", "Scope is bounded.", "--work-completed", "Mapped the Build.cs parent.",
            "--exit-assessment", "The source boundary is explicit.", "--next-handoff", "Map directories next.",
            "--deliverable", "source_boundary", "--deliverable", "engine_version", "--deliverable", "learning_goal",
            "--evidence", build_cs,
        )
        self.run_sage("process", "advance", "test-domain", "--submodule", "testcore",
                      "--summary", "incomplete", "--work-completed", "directories",
                      "--exit-assessment", "not ready", "--next-handoff", "retry",
                      "--deliverable", "directories", "--evidence", "fixture", expect=2)
        self.run_sage("question", "add", "test-domain", "--submodule", "testcore", "--text", "Why is this bounded?", "--why", "It tests provenance.")
        self.run_sage("question", "answer", "test-domain", "Q-0001", "--submodule", "testcore", "--answer", "Because the Build.cs parent is the allowlist.", "--evidence", build_cs, "--document", "references/knowledge/core.md", "--verified")
        self.run_sage("question", "promote", "test-domain", "Q-0001", "--from-submodule", "testcore", "--reason", "Domain routing needs this boundary.")
        self.run_sage("validate")
        self.run_sage("knowledge", "archive", "test-domain", "core", "--submodule", "testcore", "--reason", "Superseded fixture document")
        self.run_sage("validate")
        config_path = self.temp / "config" / "global.yaml"
        config_path.write_text(config_path.read_text(encoding="utf-8").replace('version: "5.6"', 'version: "5.7"'), encoding="utf-8")
        self.run_sage("source", "check", "test-domain", "testcore", "Plugins/Runtime/TestPlugin/Source/TestCore/TestCore.h", expect=2)
        self.run_sage("version", "migrate", "test-domain", "--reason", "Fixture engine upgrade")
        self.run_sage("version", "status", "test-domain")
        self.run_sage("validate")


if __name__ == "__main__":
    unittest.main()
