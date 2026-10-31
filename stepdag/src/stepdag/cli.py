"""`stepdag run` runs a graph in this process; `stepdag manifest` renders what Terraform deploys;
`stepdag report` writes a deployed graph's latest finished run as a run file (`stepdag.report`)."""

import argparse
import importlib
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from stepdag.assets import Definitions
from stepdag.execution import CheckFailed, PlanFailed, StepFailed, run
from stepdag.manifest import render
from stepdag.report import latest_finished, report


def load_definitions(reference: str) -> Definitions:
    """Import `module:attribute`, looking in the current directory first, as `python -m` does."""
    module_name, _, attribute = reference.partition(":")
    if not attribute:
        raise SystemExit(f"expected module:attribute, got {reference!r}")
    if "" not in sys.path:
        sys.path.insert(0, "")
    definitions = getattr(importlib.import_module(module_name), attribute)
    if not isinstance(definitions, Definitions):
        raise SystemExit(f"{reference} is not a stepdag Definitions")
    return definitions


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="stepdag")
    commands = parser.add_subparsers(dest="command", required=True)

    run_command = commands.add_parser("run", help="run a graph in this process")
    run_command.add_argument("definitions", help="module:attribute of the graph's Definitions")
    run_command.add_argument("--env", default="local", help="which environment's bindings to use (default: local)")
    run_command.add_argument("--config", default="{}", help="the run config, as JSON")
    run_command.add_argument("--select", nargs="+", metavar="ASSET", help="materialize only these assets")
    run_command.add_argument("--downstream", action="store_true", help="also materialize everything after the selection")
    run_command.add_argument("--force", action="store_true", help="skip nothing, and give the selected assets no previous")

    manifest_command = commands.add_parser("manifest", help="print the manifest Terraform deploys")
    manifest_command.add_argument("definitions", help="module:attribute of the graph's Definitions, as the Lambdas import it")

    report_command = commands.add_parser("report", help="write a deployed graph's latest finished run as a run file")
    report_command.add_argument("definitions", help="module:attribute of the graph's Definitions, as the Lambdas import it")
    report_command.add_argument("--state-machine", required=True, help="the state machine's ARN")
    report_command.add_argument("--execution", help="report this execution (its name) instead of the newest finished one")
    report_command.add_argument("--out", help="write the run file here instead of to stdout")

    args = parser.parse_args(argv)
    definitions = load_definitions(args.definitions)
    if args.command == "manifest":
        print(json.dumps(render(definitions, args.definitions), indent=2))
        return 0
    if args.command == "report":
        import boto3

        # The ARN names the region (arn:aws:states:<region>:…), so none needs configuring.
        client = boto3.client("stepfunctions", region_name=args.state_machine.split(":")[3])
        execution, history = latest_finished(client, args.state_machine, args.execution)
        run_file = json.dumps(report(definitions, args.definitions, execution, history), indent=2)
        if args.out:
            Path(args.out).parent.mkdir(parents=True, exist_ok=True)
            Path(args.out).write_text(run_file + "\n")
        else:
            print(run_file)
        return 0
    io_managers = definitions.bindings(args.env)
    try:
        result = run(
            definitions, io_managers, config=json.loads(args.config), select=args.select, downstream=args.downstream, force=args.force
        )
    except (CheckFailed, PlanFailed, StepFailed) as failure:
        print(f"{type(failure).__name__}: {failure}", file=sys.stderr)
        return 1
    values = {name: io_managers[p.io_manager].load(p) for name, p in result.pointers.items()}
    output = {"run_id": result.run_id, "computed": result.computed, "skipped": result.skipped, "values": values}
    # Values an IO manager loads as something other than JSON (a DataFrame, say) are shown by type.
    print(json.dumps(output, indent=2, default=lambda value: f"<{type(value).__name__}>"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
