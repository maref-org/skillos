"""Tests for protocol.skill_importer — cross-platform skill import"""

import json

from skillos.protocol.skill_importer import (
    AnthropicSkillConverter,
    ImportSource,
    OpenSkillManifest,
    SkillImporter,
    YAMLSkillConverter,
)

ANTHROPIC_SAMPLE = {
    "skill_id": "sk_123",
    "name": "Data Analyzer",
    "description": "Analyze datasets and generate reports",
    "author": "test_user",
    "tags": ["analysis", "data"],
    "functions": [
        {"name": "analyze", "type": "function", "params": {"dataset": "string"}},
        {"name": "visualize", "type": "function", "params": {"chart_type": "string"}},
    ],
    "triggers": ["analyze data", "run analysis"],
}

YAML_SAMPLE = """
name: yaml-skill
description: A YAML-based skill
version: 2.0.0
author: yaml_author
tags: [yaml, test]
category: utility
steps:
  - type: action
    name: step1
    params: {key: value}
triggers:
  - do something
  - run task
"""


class TestAnthropicSkillConverter:
    def setup_method(self):
        self.converter = AnthropicSkillConverter()

    def test_convert_anthropic_format(self):
        result = self.converter.convert(ANTHROPIC_SAMPLE)
        assert result.success
        assert result.manifest.name == "Data Analyzer"
        assert result.manifest.source == ImportSource.ANTHROPIC_JSON
        assert len(result.manifest.steps) == 2

    def test_missing_name_extracted(self):
        result = self.converter.convert({"description": "no name"})
        assert not result.manifest.name

    def test_triggers_extracted(self):
        result = self.converter.convert(ANTHROPIC_SAMPLE)
        assert "analyze data" in result.manifest.trigger_patterns

    def test_empty_data(self):
        result = self.converter.convert({})
        assert not result.manifest.name


class TestYAMLSkillConverter:
    def setup_method(self):
        self.converter = YAMLSkillConverter()

    def test_convert_valid_yaml(self):
        result = self.converter.convert(YAML_SAMPLE)
        assert result.success
        assert result.manifest.name == "yaml-skill"
        assert result.manifest.version == "2.0.0"
        assert result.manifest.category == "utility"

    def test_convert_invalid_yaml(self):
        result = self.converter.convert(b"{{invalid: yaml")
        assert not result.success
        assert len(result.errors) > 0

    def test_convert_empty_yaml(self):
        result = self.converter.convert(b"")
        assert not result.success

    def test_steps_converted(self):
        result = self.converter.convert(YAML_SAMPLE)
        assert len(result.manifest.steps) == 1
        assert result.manifest.steps[0]["name"] == "step1"

    def test_triggers_extracted(self):
        result = self.converter.convert(YAML_SAMPLE)
        assert "do something" in result.manifest.trigger_patterns


class TestSkillImporter:
    def setup_method(self):
        self.importer = SkillImporter()

    def test_import_from_dict_anthropic(self):
        result = self.importer.import_from_dict(ANTHROPIC_SAMPLE, source=ImportSource.ANTHROPIC_JSON)
        assert result.success
        assert result.manifest.name == "Data Analyzer"

    def test_import_from_dict_raw(self):
        result = self.importer.import_from_dict({"name": "raw-skill", "steps": [{"type": "action"}]})
        assert result.success
        assert result.manifest.name == "raw-skill"

    def test_import_from_dict_empty(self):
        result = self.importer.import_from_dict({})
        assert result.success
        assert result.manifest.name == "unnamed"

    def test_import_json_file_invalid(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("not json")
        result = self.importer.import_from_file(f)
        assert not result.success

    def test_import_json_file_valid(self, tmp_path):
        f = tmp_path / "skill.json"
        f.write_text(json.dumps(ANTHROPIC_SAMPLE))
        result = self.importer.import_from_file(f)
        assert result.success

    def test_import_yaml_file_valid(self, tmp_path):
        f = tmp_path / "skill.yaml"
        f.write_text(YAML_SAMPLE)
        result = self.importer.import_from_file(f)
        assert result.success
        assert result.manifest.name == "yaml-skill"

    def test_import_unsupported_format(self, tmp_path):
        f = tmp_path / "skill.txt"
        f.write_text("unsupported")
        result = self.importer.import_from_file(f)
        assert not result.success

    def test_to_manifest_json(self):
        manifest = OpenSkillManifest(name="test-skill", description="test desc")
        output = self.importer.to_manifest_json(manifest)
        parsed = json.loads(output)
        assert parsed["name"] == "test-skill"
        assert parsed["description"] == "test desc"
