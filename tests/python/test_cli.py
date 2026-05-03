"""Tests for the CLI argument parser and config merge logic."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from stencilforge.cli import build_parser, _build_config_from_args, _guess_command, main as cli_main
from stencilforge.config import StencilConfig


class TestParserConstruction:
    def test_subcommands_registered(self) -> None:
        parser = build_parser()
        choices = parser._subparsers._group_actions[0].choices
        assert "generate" in choices
        assert "scan" in choices
        assert "validate" in choices
        assert "dump-default-config" in choices

    def test_generate_has_required_args(self) -> None:
        parser = build_parser()
        gen = parser._subparsers._group_actions[0].choices["generate"]
        pos = [a.dest for a in gen._actions if a.dest != "help" and not a.option_strings]
        assert "input_dir" in pos
        assert "output_stl" in pos

    def test_config_args_registered(self) -> None:
        parser = build_parser()
        gen = parser._subparsers._group_actions[0].choices["generate"]
        flags = [a.option_strings[0] for a in gen._actions if a.option_strings]
        assert "--thickness-mm" in flags
        assert "--printer-profile" in flags
        assert "--model-backend" in flags
        assert "--output-mode" in flags
        assert "--paste-patterns" in flags

    def test_dump_default_config_outputs_json(self, capsys) -> None:
        parser = build_parser()
        args = parser.parse_args(["dump-default-config"])
        assert args.command == "dump-default-config"

    def test_old_style_positional_parsed_as_generate(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["generate", "/tmp/in", "/tmp/out.stl"])
        assert args.command == "generate"
        assert args.input_dir == Path("/tmp/in")
        assert args.output_stl == Path("/tmp/out.stl")


class TestBackwardCompatibility:
    def test_two_positional_args_becomes_generate(self) -> None:
        result = _guess_command(["/tmp/in", "/tmp/out.stl"])
        assert result == ["generate", "/tmp/in", "/tmp/out.stl"]

    def test_subcommand_passthrough(self) -> None:
        assert _guess_command(["generate", "/tmp/in", "/tmp/out.stl"]) == ["generate", "/tmp/in", "/tmp/out.stl"]
        assert _guess_command(["scan", "/tmp/in"]) == ["scan", "/tmp/in"]
        assert _guess_command(["validate"]) == ["validate"]
        assert _guess_command(["dump-default-config"]) == ["dump-default-config"]

    def test_empty_args(self) -> None:
        assert _guess_command([]) == []

    def test_help_flag_passthrough(self) -> None:
        assert _guess_command(["--help"]) == ["--help"]
        assert _guess_command(["-h"]) == ["-h"]


class TestConfigMerge:
    def test_default_config_no_overrides(self) -> None:
        args = Namespace()
        # Set all config args to None (default via parser)
        parser = build_parser()
        gen = parser._subparsers._group_actions[0].choices["generate"]
        for action in gen._actions:
            if action.dest != "help":
                setattr(args, action.dest, None)
        args.config = None
        config = _build_config_from_args(args)
        assert isinstance(config, StencilConfig)
        assert config.thickness_mm == 0.12  # default

    def test_cli_override_thickness(self) -> None:
        args = Namespace()
        parser = build_parser()
        gen = parser._subparsers._group_actions[0].choices["generate"]
        for action in gen._actions:
            if action.dest != "help":
                setattr(args, action.dest, None)
        args.config = None
        args.thickness_mm = 0.25
        config = _build_config_from_args(args)
        assert config.thickness_mm == 0.25

    def test_cli_override_output_mode(self) -> None:
        args = Namespace()
        parser = build_parser()
        gen = parser._subparsers._group_actions[0].choices["generate"]
        for action in gen._actions:
            if action.dest != "help":
                setattr(args, action.dest, None)
        args.config = None
        args.output_mode = "holes_only"
        config = _build_config_from_args(args)
        assert config.output_mode == "holes_only"

    def test_cli_override_backend(self) -> None:
        args = Namespace()
        parser = build_parser()
        gen = parser._subparsers._group_actions[0].choices["generate"]
        for action in gen._actions:
            if action.dest != "help":
                setattr(args, action.dest, None)
        args.config = None
        args.model_backend = "cadquery"
        config = _build_config_from_args(args)
        assert config.model_backend == "cadquery"

    def test_cli_override_printer_profile(self) -> None:
        args = Namespace()
        parser = build_parser()
        gen = parser._subparsers._group_actions[0].choices["generate"]
        for action in gen._actions:
            if action.dest != "help":
                setattr(args, action.dest, None)
        args.config = None
        args.printer_profile = "fsm"
        config = _build_config_from_args(args)
        assert config.printer_profile == "fsm"
        assert config.arc_steps == 96
        assert config.curve_resolution == 24


class TestDumpDefaultConfig:
    def test_output_is_valid_json(self) -> None:
        config = StencilConfig.from_dict({})
        data = config.to_dict()
        assert isinstance(data, dict)
        assert "thickness_mm" in data
        # Round-trip
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed["thickness_mm"] == 0.12


class TestValidate:
    def test_default_config_is_valid(self) -> None:
        config = StencilConfig.from_dict({})
        config.validate()  # should not raise

    def test_invalid_thickness_raises(self) -> None:
        with pytest.raises(ValueError):
            StencilConfig.from_dict({"thickness_mm": -0.01}).validate()

    def test_invalid_output_mode_raises(self) -> None:
        with pytest.raises(ValueError):
            StencilConfig.from_dict({"output_mode": "nonsense"}).validate()
