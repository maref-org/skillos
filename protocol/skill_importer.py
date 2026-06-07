#!/usr/bin/env python3
"""Skill Importer — 跨平台 Skill 导入器

支持:
  - Anthropic Claude for Work format → OpenSkill manifest
  - YAML-based skill format → OpenSkill manifest
  - Registry registration
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from skillos.kernel.logging_config import get_logger

logger = get_logger(__name__)


class ImportSource(StrEnum):
    ANTHROPIC_JSON = "anthropic_json"
    YAML = "yaml"
    RAW_JSON = "raw_json"


@dataclass
class OpenSkillManifest:
    name: str = ""
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    category: str = "general"
    trigger_patterns: list[str] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    output_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    source: ImportSource = ImportSource.RAW_JSON
    source_id: str = ""


@dataclass
class ImportResult:
    manifest: OpenSkillManifest
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    success: bool = True


class AnthropicSkillConverter:
    """Convert Anthropic Claude for Work skill format to OpenSkill manifest."""

    def convert(self, data: dict[str, Any]) -> ImportResult:
        warnings: list[str] = []
        errors: list[str] = []
        manifest = OpenSkillManifest(source=ImportSource.ANTHROPIC_JSON)
        try:
            manifest.name = self._extract_name(data)
            manifest.description = data.get("description", data.get("summary", ""))
            manifest.author = data.get("author", data.get("created_by", ""))
            manifest.tags = data.get("tags", [])
            manifest.source_id = data.get("id", data.get("skill_id", ""))
            manifest.steps = self._convert_steps(data)
            triggers = self._extract_triggers(data)
            if triggers:
                manifest.trigger_patterns = triggers
            if not manifest.name:
                errors.append("Missing skill name")
        except Exception as e:
            errors.append(f"Conversion failed: {e}")
        return ImportResult(
            manifest=manifest,
            warnings=warnings,
            errors=errors,
            success=len(errors) == 0,
        )

    @staticmethod
    def _extract_name(data: dict[str, Any]) -> str:
        name = data.get("name", "")
        if not name:
            name = data.get("title", data.get("display_name", ""))
        return re.sub(r"[^a-zA-Z0-9_\- ]", "", name).strip()

    @staticmethod
    def _convert_steps(data: dict[str, Any]) -> list[dict[str, Any]]:
        steps: list[dict[str, Any]] = []
        raw_steps = data.get("steps", data.get("actions", data.get("functions", [])))
        if isinstance(raw_steps, list):
            for s in raw_steps:
                if isinstance(s, dict):
                    steps.append({
                        "type": s.get("type", s.get("action", "unknown")),
                        "name": s.get("name", ""),
                        "params": s.get("params", s.get("parameters", s.get("args", {}))),
                    })
        return steps

    @staticmethod
    def _extract_triggers(data: dict[str, Any]) -> list[str]:
        triggers = data.get("triggers", data.get("prompts", []))
        if isinstance(triggers, list):
            return [str(t) for t in triggers]
        keys = data.get("trigger_patterns", data.get("keywords", []))
        if isinstance(keys, list):
            return [str(k) for k in keys]
        return []


class YAMLSkillConverter:
    """Convert YAML-based skill format to OpenSkill manifest."""

    def __init__(self, strict: bool = True):
        self._strict = strict

    def convert(self, content: str | bytes) -> ImportResult:
        warnings: list[str] = []
        errors: list[str] = []
        manifest = OpenSkillManifest(source=ImportSource.YAML)
        try:
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                errors.append("YAML content must be a mapping")
                return ImportResult(manifest=manifest, warnings=warnings, errors=errors, success=False)
            manifest.name = data.get("name", data.get("skill", data.get("id", "unnamed")))
            manifest.description = data.get("description", data.get("desc", ""))
            manifest.version = str(data.get("version", "1.0.0"))
            manifest.author = data.get("author", data.get("maintainer", ""))
            manifest.tags = data.get("tags", [])
            manifest.category = data.get("category", "general")
            manifest.steps = self._convert_steps(data)
            manifest.trigger_patterns = data.get("triggers", [])
            manifest.input_schema = data.get("input_schema", manifest.input_schema)
            manifest.output_schema = data.get("output_schema", manifest.output_schema)
            if not manifest.name or manifest.name == "unnamed":
                errors.append("Missing skill name in YAML")
        except yaml.YAMLError as e:
            errors.append(f"YAML parse error: {e}")
        except Exception as e:
            errors.append(f"Conversion failed: {e}")
        return ImportResult(
            manifest=manifest,
            warnings=warnings,
            errors=errors,
            success=len(errors) == 0,
        )

    @staticmethod
    def _convert_steps(data: dict[str, Any]) -> list[dict[str, Any]]:
        raw = data.get("steps", data.get("pipeline", []))
        if isinstance(raw, list):
            return [{"type": s.get("type", "action"), "name": s.get("name", ""), "params": s.get("params", {})} for s in raw]
        return []


class SkillImporter:
    """Aggregate importer — auto-detects format and dispatches to converter."""

    def __init__(self):
        self._converters: dict[ImportSource, Any] = {
            ImportSource.ANTHROPIC_JSON: AnthropicSkillConverter(),
            ImportSource.YAML: YAMLSkillConverter(),
        }

    def import_from_file(self, path: str | Path) -> ImportResult:
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix in (".json",):
            return self._import_json_file(p)
        elif suffix in (".yaml", ".yml"):
            return self._import_yaml_file(p)
        else:
            return ImportResult(
                manifest=OpenSkillManifest(name=p.stem),
                errors=[f"Unsupported file format: {suffix}"],
                success=False,
            )

    def import_from_dict(self, data: dict[str, Any], source: ImportSource = ImportSource.RAW_JSON) -> ImportResult:
        converter = self._converters.get(source)
        if source == ImportSource.ANTHROPIC_JSON and converter:
            return converter.convert(data)

        manifest = OpenSkillManifest(name=data.get("name", "unnamed"), source=source)
        manifest.description = data.get("description", data.get("desc", ""))
        manifest.tags = data.get("tags", [])
        manifest.steps = data.get("steps", [])
        manifest.trigger_patterns = data.get("triggers", [])
        return ImportResult(manifest=manifest)

    def _import_json_file(self, path: Path) -> ImportResult:
        try:
            data = json.loads(path.read_text())
            if not isinstance(data, dict):
                return ImportResult(
                    manifest=OpenSkillManifest(name=path.stem),
                    errors=["JSON root must be an object"],
                    success=False,
                )
            source = ImportSource.ANTHROPIC_JSON if {"skill_id", "functions"}.intersection(data) else ImportSource.RAW_JSON
            return self.import_from_dict(data, source=source)
        except json.JSONDecodeError as e:
            return ImportResult(
                manifest=OpenSkillManifest(name=path.stem),
                errors=[f"JSON decode error: {e}"],
                success=False,
            )

    def _import_yaml_file(self, path: Path) -> ImportResult:
        try:
            content = path.read_bytes()
            converter = self._converters[ImportSource.YAML]
            return converter.convert(content)
        except Exception as e:
            return ImportResult(
                manifest=OpenSkillManifest(name=path.stem),
                errors=[f"YAML import error: {e}"],
                success=False,
            )

    def to_manifest_json(self, manifest: OpenSkillManifest) -> str:
        return json.dumps({
            "name": manifest.name,
            "version": manifest.version,
            "description": manifest.description,
            "author": manifest.author,
            "tags": manifest.tags,
            "category": manifest.category,
            "triggers": manifest.trigger_patterns,
            "steps": manifest.steps,
            "input_schema": manifest.input_schema,
            "output_schema": manifest.output_schema,
            "source": manifest.source.value,
        }, indent=2, ensure_ascii=False)
