#!/usr/bin/env python3
"""Collect the frozen additional configurations through their original runners."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT/'deliverables/featureapp_webdriver_runtime_v1'))
from run_local_campaign import Campaign, load_config, write_json, read_jsonl, now
from runtime_analysis import smoke_plan, summarize_sessions

REGISTRY = {r['id']: r for r in json.loads((HERE/'CONFIGURATIONS.json').read_text())}
PORTS = {'cdp':9222, 'playwright':9223, 'puppeteer':9224, 'stealth':9226}


def plan(config):
    ids = config['additional_configurations']
    if len(ids) != len(set(ids)) or any(i not in REGISTRY for i in ids):
        raise ValueError('Invalid or duplicate configuration selection')
    result = []
    for cid in ids:
        for number in range(1, 4):
            for phase in ('clean_pre', 'attack', 'clean_post'):
                sid = f'{cid}-r{number}-{phase}'
                result.append({'step_id':sid, 'group':cid, 'round':number, 'phase':phase,
                               'configuration':cid if phase == 'attack' else None,
                               'debug_transport_only':False,
                               'runtime_context':config['campaign_id']+':'+sid})
    return result


class Expansion(Campaign):
    def freeze(self):
        if self.config['expected_collector_install_id'] == '':
            raise ValueError('An existing installation must be explicitly associated')
        path = self.output/'protocol_snapshot.json'
        expected = [smoke_plan(self.config['campaign_id'])] + plan(self.config)
        if path.exists():
            if json.loads(path.read_text()) != self.config or json.loads((self.output/'plan.json').read_text()) != expected:
                raise ValueError('Frozen protocol changed')
        else:
            write_json(path,self.config,exclusive=True)
            write_json(self.output/'release_snapshot.json',self.release,exclusive=True)
            write_json(self.output/'plan.json',expected,exclusive=True)
            write_json(self.output/'configurations_snapshot.json',REGISTRY,exclusive=True)
        if json.loads((self.output/'release_snapshot.json').read_text()) != self.release:
            raise ValueError('Release changed')

    def run_injection(self, step, step_dir):
        definition = REGISTRY[step['configuration']]
        original = self.paths['runner']
        override = self.config.get('runner_overrides',{}).get(step['configuration'])
        if override is not None:
            if not definition.get('cdpEmulation') or override != 'week10_cdp_emulation_runtime_v2.mjs':
                raise ValueError('Unregistered local runner override')
            self.paths['runner'] = str(HERE/override)
        else:
            self.paths['runner'] = str(ROOT/'hybridguard-browser-fingerprint-research/execution_log/tools'/definition['runner'])
        try:
            receipt = super().run_injection(step,step_dir)
        finally:
            self.paths['runner'] = original
        if (receipt['configId'] != definition['configId']
                or receipt['injected'] != definition['profile']
                or receipt['declaredObservableFields'] != definition['observableFields']
                or receipt.get('declaredStealthEvasions') != definition.get('stealthEvasions')):
            raise ValueError('Execution differs from frozen configuration')
        if definition.get('cdpEmulation') is not None:
            if (receipt.get('declaredCdpEmulation') != definition['cdpEmulation']
                    or receipt.get('cdpEmulation',{}).get('rollback',{}).get('rollback_verified') is not True):
                raise ValueError('CDP emulation rollback was not verified')
            if override and (receipt.get('measurementRevision') != 'cdp-runtime-rollback-plus-paired-restoration-v2'
                    or receipt['cdpEmulation']['rollback'].get('paired_payload_restoration_required') is not True):
                raise ValueError('Missing external paired-restoration requirement')
        return receipt

    def adb(self, args, step_dir, required=True):
        if self.config.get('fresh_launch_contract') == 'process-absent-then-am-start-S-W-v1' and args[:3] == ['shell','am','start']:
            args = [*args[:3],'-S','-W',*args[3:]]
        # Low-level runners normally remove their own forwarding. Only remove
        # a remaining port belonging to this dedicated device, using its client.
        if args[:2] == ['forward','--remove']:
            definition = REGISTRY.get(getattr(self,'active_configuration',None))
            port = 9333 if definition and definition.get('cdpEmulation') else PORTS[definition['executionClientId']] if definition else 9222
            listing = super().adb(['forward','--list'],step_dir,required=False)
            target = f'{self.config["serial"]} tcp:{port} '
            if not any(line.startswith(target) for line in listing.splitlines()):
                return 'Already removed by low-level runner'
            args = ['forward','--remove',f'tcp:{port}']
        return super().adb(args,step_dir,required)

    def collect(self, step):
        self.active_configuration = step['configuration']
        if self.config.get('fresh_launch_contract') == 'process-absent-then-am-start-S-W-v1':
            check_dir = self.output/'launch_checks'/step['step_id']
            check_dir.mkdir(parents=True,exist_ok=False)
            self.adb(['shell','am','force-stop','com.example.hybridguard.featureapp'],check_dir)
            stable = 0
            for _ in range(30):
                processes = self.adb(['shell','ps','-A','-o','PID,NAME'],check_dir)
                live = any(line.split()[-1:] == ['com.example.hybridguard.featureapp'] for line in processes.splitlines())
                stable = 0 if live else stable+1
                if stable == 2:break
                time.sleep(0.2)
            if stable != 2:raise RuntimeError('Previous FeatureApp process did not exit before new launch')
        super().collect(step)
        saved = read_jsonl(self.output/'sessions.jsonl')[-1][1]
        if saved['observation']['identity']['collector_install_id'] != self.config['expected_collector_install_id']:
            raise ValueError('Installation changed since source registration')

    def analyze(self):
        sessions = [r for _,r in read_jsonl(self.output/'sessions.jsonl')]
        attempts = [json.loads(p.read_text()) for p in (self.output/'attempts').glob('*/attempt.json')]
        total = 1+len(plan(self.config))
        summary = summarize_sessions(sessions,plan(self.config))
        summary.update(total_planned_sessions=total, attempts_started=len(attempts),
                       failed_attempts=sum(r['status']=='FAILED' for r in attempts),
                       incomplete_attempts=sum(r['status']=='STARTED' for r in attempts),
                       not_attempted_positions=total-len(attempts),
                       raw_archive_rows=len(read_jsonl(self.paths['raw_jsonl'])),
                       complete_configuration_triplets=dict(Counter(t['group'] for t in summary['triplets'] if t['status']=='COMPLETE')),
                       status='COMPLETE' if len(sessions)==total and all(r['accepted'] for r in sessions) and all(r['status']=='ACCEPTED' for r in attempts) else 'INCOMPLETE_OR_FAILED',
                       analyzed_at=now())
        write_json(self.output/'SUMMARY.json',summary)
        return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--stage',required=True,choices=['smoke','campaign','analyze'])
    args = parser.parse_args()
    campaign = Expansion(load_config(args.config))
    if args.stage == 'analyze':
        print(json.dumps(campaign.analyze(),indent=2));sys.exit(0)
    campaign.freeze()
    if args.stage == 'campaign':
        if json.loads((campaign.output/'attempts/smoke/attempt.json').read_text())['status'] != 'ACCEPTED':
            raise ValueError('Successful smoke required')
        first = read_jsonl(campaign.output/'sessions.jsonl')[0][1]['observation']['identity']
        if first['collector_install_id'] != campaign.config['expected_collector_install_id']:
            raise ValueError('Installation does not match existing environment')
    write_json(campaign.output/f'{args.stage.upper()}_STARTED.json',{'at':now()},exclusive=True)
    try:
        for step in ([smoke_plan(campaign.config['campaign_id'])] if args.stage=='smoke' else plan(campaign.config)):
            campaign.collect(step)
    finally:
        campaign.analyze()
