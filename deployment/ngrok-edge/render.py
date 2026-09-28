"""Render the domain-dependent files without changing a running service."""
import argparse
import ipaddress
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def domain_name(value):
    value = value.strip().lower()
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise argparse.ArgumentTypeError("Use an owned DNS name, not an IP address")
    labels = value.split(".")
    if len(value) > 253 or len(labels) < 2 or any(
        not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
        for label in labels
    ):
        raise argparse.ArgumentTypeError("Enter only the ASCII DNS name, without scheme or path")
    if value == "example.com" or value.endswith(".example.com"):
        raise argparse.ArgumentTypeError("Replace example.com with your actual domain")
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("domain", type=domain_name)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    conf = (HERE / "https.conf.template").read_text().replace("__COLLECT_DOMAIN__", args.domain)
    policy = json.loads((ROOT / "backend_server/ngrok-mtc-policy.json").read_text())
    policy["on_http_request"].append({
        "actions": [{"type": "add-headers", "config": {"headers": {"host": args.domain}}}]
    })
    outputs = {
        "hybridguard-https.conf": conf,
        "ngrok-edge-policy.json": json.dumps(policy, indent=2) + "\n",
        "endpoint.properties": "\n".join([
            "hybridguardRequirePublicEndpoints=true",
            f"hybridguardCollectEndpoint=https://{args.domain}/api/collect/fingerprint",
            f"hybridguardBrowserTicketEndpoint=https://{args.domain}/api/collect/browser-ticket",
            f"hybridguardBrowserPairPollBaseUrl=https://{args.domain}/api/collect/browser-pairs",
            f"hybridguardBrowserProbeBaseUrl=https://{args.domain}/",
            "",
        ]),
    }
    for name, content in outputs.items():
        with (args.output / name).open("x") as target:
            target.write(content)
    print(f"Prepared files in {args.output}; no services changed.")


if __name__ == "__main__":
    main()
